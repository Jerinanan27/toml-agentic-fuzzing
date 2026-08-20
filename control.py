import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics import depth, node_types, to_toml, DottedKey
from oracle import run_once, classify

N = 500


def run_strategy(strategy, is_structured: bool):
    """Run a strategy 500 times, return outcome counts and max depth."""
    outcomes = {}
    depths = []

    for _ in range(N):
        value = strategy.example()

        if is_structured:
            depths.append(depth(value))
            text = to_toml(value)
            payload = text.encode("utf-8", errors="replace")
        else:
            # baseline produces raw str or bytes
            if isinstance(value, str):
                payload = value.encode("utf-8", errors="replace")
            else:
                payload = value
            depths.append(0)  # baseline has no structured depth

        outcome = classify(run_once(payload))
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    return {
        "outcomes": outcomes,
        "crashes": outcomes.get("CRASH", 0),
        "hangs": outcomes.get("HANG", 0),
        "depth_max": max(depths) if depths else 0,
    }


def load(path):
    ns = {}
    code = (
        "from hypothesis import strategies as st\n"
        "from metrics import DottedKey\n"
        + open(path).read()
    )
    exec(code, ns)
    return ns["strategy"]


if __name__ == "__main__":
    from strategies.baseline import baseline
    from agent.refine import load_strategy

    print("1/4 random baseline...")
    r_base = run_strategy(baseline, is_structured=False)

    print("2/4 grammar seed...")
    seed = load_strategy(open("strategies/seed_grammar.py").read())
    r_seed = run_strategy(seed, is_structured=True)

    print("3/4 exp3 final (flat objective)...")
    e3 = load_strategy(open("strategies/generated_exp3/iteration_5.py").read())
    r_e3 = run_strategy(e3, is_structured=True)

    print("4/4 exp4 final (depth primary)...")
    e4 = load_strategy(open("strategies/generated_exp4/iteration_5.py").read())
    r_e4 = run_strategy(e4, is_structured=True)

    print("\n" + "=" * 70)
    print(f"{'Arm':<28}{'Crashes':>10}{'Hangs':>8}{'Max depth':>12}")
    print("=" * 70)
    for name, r in [("Random baseline", r_base),
                    ("Grammar seed (iter 0)", r_seed),
                    ("Exp3 final (flat)", r_e3),
                    ("Exp4 final (depth primary)", r_e4)]:
        print(f"{name:<28}{r['crashes']:>10}{r['hangs']:>8}{r['depth_max']:>12}")
    print("=" * 70)