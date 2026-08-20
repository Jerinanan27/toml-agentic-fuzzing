import json
import os
import re
from collections import Counter

CRASH_DIRS = ["crashes", "crashes_exp2", "crashes_exp4"]
FRAME_RE = re.compile(r"in (\w+) /work/tomlc99/toml\.c")


def fingerprint(stderr: str) -> tuple:
    """The recursion cycle = functions that repeat in the stack.
    Functions appearing only once or twice are the exhaustion point
    (STRNDUP, expand, etc.), which varies run to run and is noise.
    Keeping only frequently-repeating frames isolates the actual bug."""
    funcs = FRAME_RE.findall(stderr)
    if not funcs:
        return ("UNSYMBOLICATED",)
    counts = Counter(funcs)
    cycle = {f for f, n in counts.items() if n >= 3}
    if not cycle:
        cycle = set(funcs)
    return tuple(sorted(cycle))


def triage(crash_dir: str) -> dict:
    groups = {}
    if not os.path.isdir(crash_dir):
        return groups
    for fname in sorted(os.listdir(crash_dir)):
        crash = json.load(open(f"{crash_dir}/{fname}"))
        fp = fingerprint(crash["stderr"])
        if fp not in groups:
            groups[fp] = {
                "count": 0,
                "example_input": crash["input"][:45],
                "example_file": f"{crash_dir}/{fname}",
                "min_depth": crash["depth"],
            }
        groups[fp]["count"] += 1
        groups[fp]["min_depth"] = min(groups[fp]["min_depth"], crash["depth"])
    return groups


def main():
    for crash_dir in CRASH_DIRS:
        groups = triage(crash_dir)
        if not groups:
            continue
        total = sum(g["count"] for g in groups.values())
        print(f"\n{'='*55}")
        print(f"{crash_dir}: {total} crashes -> {len(groups)} distinct bugs")
        print(f"{'='*55}")
        for fp, info in sorted(groups.items(), key=lambda x: -x[1]["count"]):
            print(f"\n  {info['count']} crashes | min depth {info['min_depth']}")
            print(f"  cycle: {fp}")
            print(f"  input: {info['example_input']}")


if __name__ == "__main__":
    main()