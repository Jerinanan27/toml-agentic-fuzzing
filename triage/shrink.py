"""Spec Step 5.4: minimise each unique crash signature with Hypothesis's
shrinker, rather than keeping the first crashing input observed.

One test per signature. A test that failed on ANY crash would shrink
toward whichever defect is reachable at the shallowest depth (arrays),
collapsing five distinct bugs into one reproducer. Targeting a single
signature keeps the shrinker inside one defect class.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hypothesis import given, settings, strategies as st, HealthCheck, Phase
from metrics import to_toml, DottedKey
from oracle import run_once, classify
from triage import fingerprint


def crash_signature(payload: bytes):
    """Run one input. Return its signature, or None if it did not crash."""
    result = run_once(payload)
    outcome = classify(result)
    if outcome == "HANG":
        return ("HANG",)
    if outcome == "CRASH":
        return fingerprint(result["stderr"])
    return None


# Depth-parameterised generators. Depth is the shrink target: Hypothesis
# shrinks integers toward their minimum, so it walks the depth down to the
# smallest value that still crashes.
NESTERS = {
    "array":        lambda d: "a = " + "[" * d + "1" + "]" * d,
    "dotted":       lambda d: "a" + ".a" * d + " = 1",
    "inline_table": lambda d: "a = " + "{ k = " * d + "1" + " }" * d,
}


def shrink(kind: str, target_signature: tuple, max_depth: int = 200000):
    """Shrink `kind` inputs down to the smallest depth that still produces
    `target_signature`. Returns the minimised depth, or None."""

    build = NESTERS[kind]
    found = {}

    @settings(
        max_examples=60,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
        phases=[Phase.generate, Phase.shrink],
    )
    @given(st.integers(min_value=1, max_value=max_depth))
    def test_no_crash_at_depth(d):
        payload = build(d).encode("utf-8")
        sig = crash_signature(payload)
        if sig == target_signature:
            found["depth"] = d
            raise AssertionError(f"{kind} crashes at depth {d}")

    try:
        test_no_crash_at_depth()
    except AssertionError:
        return found.get("depth")
    return None


if __name__ == "__main__":
    targets = {
        "array":        ("parse_array",),
        "dotted":       ("parse_keyval",),
        "inline_table": ("parse_inline_table", "parse_keyval"),
    }

    for kind, sig in targets.items():
        print(f"\nShrinking {kind} toward signature {sig} ...")
        d = shrink(kind, sig)
        if d is None:
            print(f"  no input matching that signature was found")
        else:
            print(f"  minimised depth: {d}")
            print(f"  reproducer: {NESTERS[kind](d)[:60]}...")