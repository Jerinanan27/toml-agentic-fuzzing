import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics import to_toml, DottedKey
from oracle import run_once, classify


def make_input(kind: str, depth: int) -> bytes:
    """Build a crashing input of a given kind at a given depth."""
    if kind == "array":
        s = "a = " + "[" * depth + "1" + "]" * depth
    elif kind == "dotted":
        s = "a" + ".a" * depth + " = 1"
    elif kind == "inline_table":
        s = "a = " + "{ k = " * depth + "1" + " }" * depth
    else:
        raise ValueError(kind)
    return s.encode("utf-8")


def crashes(kind: str, depth: int) -> bool:
    payload = make_input(kind, depth)
    outcome = classify(run_once(payload))
    return outcome in ("CRASH", "HANG")


def find_threshold(kind: str, low: int = 1, high: int = 200000) -> int:
    """Binary search for the smallest depth that still crashes."""
    if not crashes(kind, high):
        return -1  # doesn't even crash at max

    while low < high:
        mid = (low + high) // 2
        if crashes(kind, mid):
            high = mid       # crashes here, try shallower
        else:
            low = mid + 1    # survives here, need deeper
    return low


if __name__ == "__main__":
    for kind in ["array", "dotted", "inline_table"]:
        print(f"Finding threshold for {kind}...")
        t = find_threshold(kind)
        if t == -1:
            print(f"  {kind}: no crash even at 200000")
        else:
            survives = "survives" if not crashes(kind, t - 1) else "still crashes"
            print(f"  {kind}: crashes at depth {t}, {t-1} {survives}")
        print()