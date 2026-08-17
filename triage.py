import json
import os
import re

CRASH_DIR = "crashes"

# Match lines like: "in parse_array /work/tomlc99/toml.c:1075"
FRAME_RE = re.compile(r"in (\w+) /work/tomlc99/toml\.c:(\d+)")


def fingerprint(stderr: str) -> tuple:
    """Reduce a crash's stderr to a stable signature: the SET of
    tomlc99 functions appearing in the stack. This ignores the exact
    exhaustion point (which varies) and captures the recursion cycle."""
    funcs = set()
    for match in FRAME_RE.finditer(stderr):
        func = match.group(1)
        funcs.add(func)
    if not funcs:
        return ("UNSYMBOLICATED",)
    return tuple(sorted(funcs))


def main():
    groups = {}
    for fname in sorted(os.listdir(CRASH_DIR)):
        crash = json.load(open(f"{CRASH_DIR}/{fname}"))
        fp = fingerprint(crash["stderr"])
        if fp not in groups:
            groups[fp] = {"count": 0, "example": fname, "example_input": crash["input"][:50]}
        groups[fp]["count"] += 1

    print(f"Total crashes: {sum(g['count'] for g in groups.values())}")
    print(f"Distinct bugs: {len(groups)}")
    print()
    for fp, info in sorted(groups.items(), key=lambda x: -x[1]["count"]):
        print(f"--- {info['count']} crashes")
        print(f"    functions: {fp}")
        print(f"    example input: {info['example_input']}")
        print()


if __name__ == "__main__":
    main()