import os
import subprocess
import re

SANITIZER_PATTERN = re.compile(
    r"AddressSanitizer|UndefinedBehaviorSanitizer|runtime error:|LeakSanitizer",
    re.IGNORECASE,
)

EXIT_ACCEPTED = 0
EXIT_REJECTED = 50
EXIT_HARNESS_ERROR = 51

HARNESS = "./harness/harness_asan"
TIMEOUT_SECONDS = 5

SANITIZER_ENV = {
    "ASAN_OPTIONS": "detect_leaks=0:abort_on_error=1",
    "UBSAN_OPTIONS": "print_stacktrace=1:report_error_type=1:halt_on_error=1",
}


def run_once(data: bytes) -> dict:
    """Feed `data` to the harness on stdin. Report what came back."""
    env = dict(os.environ)
    env.update(SANITIZER_ENV)

    try:
        proc = subprocess.run(
            [HARNESS],
            input=data,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
        return {
            "returncode": proc.returncode,
            "stderr": proc.stderr.decode("utf-8", errors="replace"),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": None,
            "stderr": "",
            "timed_out": True,
        }
def classify(result: dict) -> str:
    """Turn a raw run result into one of five outcomes.
    The ORDER of these checks is the design - see comments."""

    # 1. A hang is a hang regardless of what it printed.
    if result["timed_out"]:
        return "HANG"

    # 2. Sanitizer text is authoritative. It can appear even when the
    #    exit code looks perfectly healthy - which is exactly the
    #    failure this ordering exists to prevent.
    if SANITIZER_PATTERN.search(result["stderr"]):
        return "CRASH"

    # 3. Killed by a signal. Python reports these as negative.
    rc = result["returncode"]
    if rc is not None and rc < 0:
        return "CRASH"

    # 4-5. The two outcomes our harness explicitly promises.
    if rc == EXIT_ACCEPTED:

        return "ACCEPTED"

    if rc == EXIT_REJECTED:

        return "REJECTED"

    if rc == EXIT_HARNESS_ERROR:

        return "HARNESS_ERROR"


    # 6. Surprises surface. They are never silently filed as "fine".

    return "UNKNOWN"

if __name__ == "__main__":
    for label, payload in [
        ("valid", b'name = "test"\n'),
        ("garbage", b'garbage ===\n'),
        ("deep", b'a = ' + b'[' * 100000 + b'1' + b']' * 100000),
        ("empty", b''),
        ("binary", bytes(range(256))),
    ]:
        result = run_once(payload)
        outcome = classify(result)
        print(f"{outcome:10s} {label}")