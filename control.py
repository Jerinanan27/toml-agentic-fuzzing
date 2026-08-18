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
    print("Running control experiment (500 inputs each)...\n")

    # 1. Random baseline
    from strategies.baseline import baseline
    print("1/3 random baseline...")
    r_base = run_strategy(baseline, is_structured=False)

    # 2. Seed strategy (iteration 0)
    print("2/3 seed strategy...")
    seed = load("strategies/generated/iteration_0.py")
    r_seed = run_strategy(seed, is_structured=True)

    # 3. Evolved strategy (iteration 5)
    print("3/3 evolved strategy...")
    evolved = load("strategies/generated/iteration_5.py")
    r_evolved = run_strategy(evolved, is_structured=True)

    print("\n" + "=" * 60)
    print(f"{'Approach':<22}{'Crashes':>10}{'Hangs':>8}{'Max depth':>12}")
    print("=" * 60)
    print(f"{'Random baseline':<22}{r_base['crashes']:>10}{r_base['hangs']:>8}{r_base['depth_max']:>12}")
    print(f"{'Seed (iteration 0)':<22}{r_seed['crashes']:>10}{r_seed['hangs']:>8}{r_seed['depth_max']:>12}")
    print(f"{'Evolved (iteration 5)':<22}{r_evolved['crashes']:>10}{r_evolved['hangs']:>8}{r_evolved['depth_max']:>12}")
    print("=" * 60)