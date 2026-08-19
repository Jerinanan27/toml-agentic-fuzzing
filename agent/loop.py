import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.runner import run_round, format_feedback
from agent.refine import ask_for_improvement, load_strategy, validate_strategy

_TAG = os.environ.get("FUZZ_TAG", "exp2")
STRATEGY_DIR = f"strategies/generated_{_TAG}"
LOG_DIR = f"logs/iterations_{_TAG}"
CRASH_DIR = f"crashes_{_TAG}"

MAX_ITERATIONS = 5
EXAMPLES_PER_ROUND = 500
WAIT_BETWEEN_CALLS = 65


def save_strategy(code: str, n: int) -> str:
    path = f"{STRATEGY_DIR}/iteration_{n}.py"
    with open(path, "w") as f:
        f.write(code)
    return path


def save_log(record: dict, n: int) -> None:
    with open(f"{LOG_DIR}/round_{n}.json", "w") as f:
        json.dump(record, f, indent=2)


def save_crashes(crashes: list, n: int) -> None:
    for i, crash in enumerate(crashes):
        with open(f"{CRASH_DIR}/round{n}_crash{i}.json", "w") as f:
            json.dump(crash, f, indent=2)


def main():
    task = open("prompts/seed.txt").read()
    current_code = open("strategies/seed_v3.py").read()
    current_strategy = load_strategy(current_code)

    total_in = 0
    total_out = 0

    for n in range(MAX_ITERATIONS + 1):
        print(f"\n{'='*50}")
        print(f"ITERATION {n}")
        print(f"{'='*50}")

        save_strategy(current_code, n)

        print(f"Running {EXAMPLES_PER_ROUND} examples...")
        start = time.time()
        summary = run_round(current_strategy, n_examples=EXAMPLES_PER_ROUND)
        elapsed = round(time.time() - start, 1)

        print(f"  outcomes:   {summary['outcomes']}")
        print(f"  depth max:  {summary['depth_max']}")
        print(f"  acceptance: {summary['acceptance_rate']}")
        print(f"  types:      {summary['n_types']}/6")
        print(f"  crashes:    {len(summary['crashes'])}")
        print(f"  took:       {elapsed}s")

        if summary["crashes"]:
            save_crashes(summary["crashes"], n)

        feedback = format_feedback(summary)

        record = {
            "iteration": n,
            "elapsed_seconds": elapsed,
            "summary": {k: v for k, v in summary.items() if k != "crashes"},
            "n_crashes": len(summary["crashes"]),
            "feedback_sent": feedback,
        }

        if n == MAX_ITERATIONS:
            save_log(record, n)
            print("\nBudget reached. Stopping.")
            break

        print(f"\nWaiting {WAIT_BETWEEN_CALLS}s for rate limit...")
        time.sleep(WAIT_BETWEEN_CALLS)

        print("Asking the model to improve...")
        try:
            response = ask_for_improvement(task, current_code, feedback)
            total_in += response["prompt_tokens"]
            total_out += response["completion_tokens"]
            record["prompt_tokens"] = response["prompt_tokens"]
            record["completion_tokens"] = response["completion_tokens"]

            new_strategy = load_strategy(response["code"])
            validate_strategy(new_strategy)

            current_code = response["code"]
            current_strategy = new_strategy
            record["refine_status"] = "accepted"
            print("  new strategy accepted")

        except Exception as e:
            record["refine_status"] = "rejected"
            record["refine_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            print(f"  REJECTED: {type(e).__name__} - keeping previous strategy")

        save_log(record, n)

    print(f"\n{'='*50}")
    print(f"Total tokens: {total_in} in, {total_out} out")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()