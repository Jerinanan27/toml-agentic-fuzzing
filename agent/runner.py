import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import depth, node_types, to_toml, ALL_PRODUCTIONS
from oracle import run_once, classify
from triage import fingerprint

WALL_CLOCK_CAP_SECONDS = 600   # spec: 10-minute backstop per run


def run_round(strategy, n_examples=500, wall_clock_cap=WALL_CLOCK_CAP_SECONDS):
    """Generate n_examples inputs from `strategy`, test each one,
    and return a summary of what happened.

    Stops early if `wall_clock_cap` seconds elapse. The cap exists to
    catch a strategy that has gone pathological - e.g. one generating
    inputs so large that serialisation or process spawning dominates -
    rather than to bound normal runs, which take well under a minute.
    """

    started = time.time()
    stopped_early = False

    outcomes = {}
    depths = []
    seen_productions = set()   # accumulate coverage, not the structures
    error_messages = {}
    crashes = []

    for i in range(n_examples):
        if time.time() - started > wall_clock_cap:
            stopped_early = True
            break

        structure = strategy.example()

        # Measure immediately, then drop the structure. Retaining 500 deep
        # structures at once exhausts memory and gets the process OOM-killed;
        # a set union gives identical coverage for constant memory.
        d = depth(structure)
        depths.append(d)
        seen_productions |= node_types(structure)

        text = to_toml(structure)
        del structure
        payload = text.encode("utf-8", errors="replace")

        result = run_once(payload)
        outcome = classify(result)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

        if outcome == "REJECTED":
            msg = result["stderr"].strip()[:100]
            error_messages[msg] = error_messages.get(msg, 0) + 1

        if outcome in ("CRASH", "HANG"):
            # Hangs have no stack trace, so they get their own signature
            # scheme based on input shape rather than stack frames.
            if outcome == "HANG":
                sig = ("HANG", f"depth_{d // 10000}0k")
            else:
                sig = fingerprint(result["stderr"])

            crashes.append({
                "outcome": outcome,
                "input": text,
                "input_len": len(text),
                "input_preview": text[:200],
                "depth": d,
                "returncode": result["returncode"],
                "stderr": result["stderr"],
                "signature": list(sig),
            })

    # Group crashes by signature - this is what the LLM needs to know
    signatures = {}
    for c in crashes:
        key = " + ".join(c["signature"])
        signatures[key] = signatures.get(key, 0) + 1

    covered = seen_productions & ALL_PRODUCTIONS
    coverage = {
        "covered": len(covered),
        "total": len(ALL_PRODUCTIONS),
        "missing": sorted(ALL_PRODUCTIONS - covered),
    }

    total = sum(outcomes.values())
    accepted = outcomes.get("ACCEPTED", 0)

    return {
        "total": total,
        "outcomes": outcomes,
        "acceptance_rate": round(accepted / total, 3) if total else 0,
        "depth_max": max(depths) if depths else 0,
        "depth_avg": round(sum(depths) / len(depths), 1) if depths else 0,
        "productions_covered": coverage["covered"],
        "productions_total": coverage["total"],
        "productions_missing": coverage["missing"],
        "distinct_errors": len(error_messages),
        "top_errors": sorted(error_messages.items(), key=lambda x: -x[1])[:5],
        "crash_signatures": signatures,
        "crashes": crashes,
        "elapsed_seconds": round(time.time() - started, 1),
        "stopped_early": stopped_early,
    }


def format_feedback(summary: dict) -> str:
    """Turn a round summary into a feedback message for the LLM.

    This is the ONLY thing the LLM sees about its own performance,
    so it states each measurement, its target, and the gap.
    """
    lines = []
    lines.append("RESULTS FROM YOUR LAST STRATEGY")
    lines.append("")
    lines.append(f"Inputs tested: {summary['total']}")
    lines.append(f"Outcomes: {summary['outcomes']}")
    lines.append("")
    lines.append("MEASURED AGAINST THE OBJECTIVE:")
    lines.append("")

    # 1. Grammar production coverage
    cov = summary["productions_covered"]
    tot = summary["productions_total"]
    lines.append(f"1. Grammar production coverage: {cov} of {tot}")
    if summary["productions_missing"]:
        lines.append("   NOT COVERED - these grammar productions never appeared,")
        lines.append("   so the parser code handling them was never reached:")
        lines.append(f"     {', '.join(summary['productions_missing'])}")
        lines.append("   Generate inputs that exercise them.")
    else:
        lines.append("   OK - full grammar coverage. Keep it there.")
    lines.append("")

        # 2. Nesting depth - the PRIMARY objective
    lines.append(f"2. Nesting depth: max {summary['depth_max']}, "
                 f"average {summary['depth_avg']}")
    lines.append("   This is the PRIMARY objective. The parser's known defect")
    lines.append("   class is unbounded recursion, reachable only past roughly")
    lines.append("   15,000 (arrays), 52,000 (inline tables) and 87,000")
    lines.append("   (dotted keys) levels.")
    if summary["depth_max"] < 100000:
        lines.append(f"   TOO SHALLOW - max {summary['depth_max']}. Some inputs")
        lines.append("   must exceed 100,000 levels. Do NOT reduce depth to")
        lines.append("   improve acceptance rate; depth takes priority.")
    else:
        lines.append("   OK - reaching crash territory. Do not reduce it.")
    lines.append("")

    # 3. Acceptance rate - SECONDARY, and only via shallow statements
    rate = summary["acceptance_rate"]
    lines.append(f"3. Acceptance rate: {rate}   TARGET: 0.3 to 0.7")
    lines.append("   SECONDARY to depth. Note acceptance is measured per")
    lines.append("   document: one malformed line rejects the whole file.")
    lines.append("   Raise it by making the SHALLOW statements valid, not by")
    lines.append("   removing deep ones.")
    if rate > 0.7:
        lines.append("   TOO HIGH - add near-valid-but-malformed inputs:")
        lines.append("   unterminated strings, duplicate keys, trailing '='.")
    elif rate < 0.3:
        lines.append("   TOO LOW - most documents rejected. Make the ordinary")
        lines.append("   key-value lines well-formed while keeping one deep value.")
    else:
        lines.append("   OK - in the target band.")
    lines.append("")
    # 4. Rejection diversity
    lines.append(f"4. Distinct rejection messages: {summary['distinct_errors']}")
    if summary["top_errors"]:
        lines.append("   Most common rejections:")
        for msg, count in summary["top_errors"]:
            lines.append(f"     {count}x  {msg}")
    else:
        lines.append("   None - nothing was rejected.")
    lines.append("")

    # Crash signatures (spec step 4.4: unique crash signatures so far)
    n_crashes = len(summary["crashes"])
    lines.append(f"Crashes found: {n_crashes}")
    if summary["crash_signatures"]:
        lines.append("Unique crash signatures (recursion cycles):")
        for sig, count in sorted(summary["crash_signatures"].items(),
                                 key=lambda x: -x[1]):
            lines.append(f"  {count}x  {sig}")
        lines.append("Signatures already found are not new information -")
        lines.append("target grammar productions that have NOT yet crashed.")

    return "\n".join(lines)