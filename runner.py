import json
from hypothesis import given, settings, HealthCheck
from oracle import run_once, classify
from strategies.baseline import baseline

LOG_FILE = "logs/baseline_run.jsonl"

counts = {}


@settings(
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(baseline)
def test(payload):
    if isinstance(payload, str):
        payload = payload.encode("utf-8", errors="surrogatepass")

    result = run_once(payload)
    outcome = classify(result)

    counts[outcome] = counts.get(outcome, 0) + 1

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps({
            "outcome": outcome,
            "returncode": result["returncode"],
            "input_len": len(payload),
        }) + "\n")


if __name__ == "__main__":
    open(LOG_FILE, "w").close()
    test()
    print("\n--- Summary ---")
    for outcome, n in sorted(counts.items()):
        print(f"{outcome:15s} {n}")