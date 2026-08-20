"""Generate iteration 0 from the grammar, with automatic repair.

Spec Step 4.2 requires validating the generator before trusting it. A
first attempt frequently fails on a real API detail or a node type the
serialiser rejects, so the failure is fed back and a repair requested.
Repairs are logged and reported: they are part of the method, not
something done by hand off the record.
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import call_llm
from agent.refine import strip_fences, load_strategy, validate_strategy

MAX_REPAIRS = 3
SYSTEM = "You are an expert Python developer writing Hypothesis strategies."
TAIL = ("\n\nWrite the initial strategy now. Return ONLY Python code, "
        "no explanation, no markdown fences. Define a variable named `strategy`.")


def generate_seed(task: str) -> dict:
    prompt = task + TAIL
    attempts = []
    tokens_in = tokens_out = 0

    for attempt in range(MAX_REPAIRS + 1):
        response = call_llm(SYSTEM, prompt)
        tokens_in += response["prompt_tokens"]
        tokens_out += response["completion_tokens"]
        code = strip_fences(response["text"])

        try:
            strategy = load_strategy(code)
            validate_strategy(strategy)
            attempts.append({"attempt": attempt, "status": "accepted"})
            return {"code": code, "strategy": strategy, "attempts": attempts,
                    "tokens_in": tokens_in, "tokens_out": tokens_out}

        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            attempts.append({"attempt": attempt, "status": "rejected",
                             "error": error[:300]})
            print(f"  attempt {attempt} rejected: {error[:160]}")

            if attempt == MAX_REPAIRS:
                raise RuntimeError(f"seed failed after {MAX_REPAIRS} repairs")

            prompt = (
                task +
                "\n\n=== YOUR PREVIOUS ATTEMPT FAILED ===\n" + error +
                "\n\nCommon causes, in order of likelihood:\n"
                "  st.lists(elements, min_size=, max_size=)   NOT min_value\n"
                "  st.dictionaries(keys=, values=)            NOT key/value\n"
                "  st.integers(min_value=, max_value=)\n"
                "  st.text(alphabet=, min_size=, max_size=)\n"
                "Every value in Document.statements must be exactly one of "
                "Comment, KeyValue, TableHeader or ArrayTableHeader - never a "
                "tuple or list of them. Never emit NUL bytes.\n\n"
                "Write the strategy again, correctly. Return ONLY Python code, "
                "no explanation, no markdown fences. Define a variable named "
                "`strategy`."
            )
            time.sleep(65)   # free-tier rate limit

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    result = generate_seed(open("prompts/seed.txt").read())
    open("strategies/seed_grammar.py", "w").write(result["code"])
    with open("logs/seed_generation.json", "w") as f:
        json.dump({k: v for k, v in result.items() if k != "strategy"}, f, indent=2)
    print("\n" + result["code"])
    print(f"\nAccepted after {len(result['attempts'])} attempt(s). "
          f"tokens in {result['tokens_in']}, out {result['tokens_out']}")