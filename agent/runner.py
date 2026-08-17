import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import depth, node_types, to_toml
from oracle import run_once, classify


def run_round(strategy, n_examples=500):
    """Generate n_examples inputs from `strategy`, test each one,
    and return a summary of what happened."""

    outcomes = {}
    depths = []
    types_seen = set()
    error_messages = {}
    crashes = []

    for i in range(n_examples):
        structure = strategy.example()

        d = depth(structure)
        depths.append(d)
        types_seen |= node_types(structure)

        text = to_toml(structure)
        payload = text.encode("utf-8", errors="replace")

        result = run_once(payload)
        outcome = classify(result)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

        if outcome == "REJECTED":
            msg = result["stderr"].strip()[:100]
            error_messages[msg] = error_messages.get(msg, 0) + 1

        if outcome == "CRASH":
            crashes.append({
                "input": text[:200],
                "input_len": len(text),
                "depth": d,
                "stderr": result["stderr"][:2000],
            })

    total = sum(outcomes.values())
    accepted = outcomes.get("ACCEPTED", 0)

    return {
        "total": total,
        "outcomes": outcomes,
        "acceptance_rate": round(accepted / total, 3) if total else 0,
        "depth_max": max(depths) if depths else 0,
        "depth_avg": round(sum(depths) / len(depths), 1) if depths else 0,
        "types_seen": sorted(types_seen),
        "n_types": len(types_seen),
        "distinct_errors": len(error_messages),
        "top_errors": sorted(error_messages.items(), key=lambda x: -x[1])[:5],
        "crashes": crashes,
    }

def format_feedback(summary: dict) -> str:
    """Turn a round summary into a feedback message for the LLM.

    This is the ONLY thing the LLM sees about its own performance,
    so it states the measurement, the target, and the gap.
    """
    lines = []
    lines.append("RESULTS FROM YOUR LAST STRATEGY")
    lines.append("")
    lines.append(f"Inputs tested: {summary['total']}")
    lines.append(f"Outcomes: {summary['outcomes']}")
    lines.append("")

    lines.append("MEASURED AGAINST THE OBJECTIVE:")
    lines.append("")

    n = summary["n_types"]
    lines.append(f"1. Type coverage: {n} of 6 types. Types seen: {summary['types_seen']}")
    if n >= 6:
        lines.append("   OK - target of 6 types is met. Keep it there.")
    else:
        lines.append("   TOO LOW - target is 6. Missing types must be generated.")
    lines.append("")

    lines.append(f"2. Nesting depth: max {summary['depth_max']}, average {summary['depth_avg']}")
    lines.append("   TARGET: the parser only crashes past roughly 100000 levels.")
    if summary["depth_max"] < 100000:
        lines.append(f"   TOO SHALLOW - max depth {summary['depth_max']} is far below 100000.")
        lines.append("   Some inputs must reach 100000+ levels of nesting.")
    else:
        lines.append("   OK - reaching crash territory.")
    lines.append("")

    rate = summary["acceptance_rate"]
    lines.append(f"3. Acceptance rate: {rate}")
    lines.append("   TARGET: between 0.3 and 0.7")
    if rate > 0.7:
        lines.append("   TOO HIGH - every input is valid TOML, so the parser's")
        lines.append("   error-handling code is never tested. Generate some")
        lines.append("   near-valid-but-malformed inputs: unescaped quotes inside")
        lines.append("   strings, missing brackets, duplicate keys, bad numbers.")
    elif rate < 0.3:
        lines.append("   TOO LOW - most inputs are rejected at the front door,")
        lines.append("   so the parser's real logic is never reached.")
    else:
        lines.append("   OK - in the target band.")
    lines.append("")

    lines.append(f"4. Distinct rejection messages: {summary['distinct_errors']}")
    if summary["top_errors"]:
        lines.append("   Most common rejections:")
        for msg, count in summary["top_errors"]:
            lines.append(f"     {count}x  {msg}")
    else:
        lines.append("   None - nothing was rejected.")
    lines.append("")

    n_crashes = len(summary["crashes"])
    lines.append(f"Crashes found: {n_crashes}")
    if n_crashes:
        for c in summary["crashes"][:3]:
            lines.append(f"  depth {c['depth']}, input length {c['input_len']}")

    return "\n".join(lines)