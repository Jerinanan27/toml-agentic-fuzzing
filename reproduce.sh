#!/bin/bash
# Verify all three defect classes reproduce against the pinned build.
# Run after ./build.sh, inside the pinned container.
set -e

[ -x harness/harness_asan ] || { echo "run ./build.sh first" >&2; exit 1; }

fail=0

# Depths are set above the measured thresholds (~14,850 / ~87,270 / ~52,360).
# A command written at the boundary fails on some runs, since the exact point
# of stack exhaustion varies by 6 to 25 levels with runtime memory state.
check() {
    python3 -c "$2" > /tmp/repro.toml
    if ./harness/harness_asan < /tmp/repro.toml >/dev/null 2>&1; then
        echo "FAIL  $1 did not crash"
        fail=1
    else
        echo "ok    $1"
    fi
}

check "deep arrays"        "print('a = ' + '['*20000 + '1' + ']'*20000)"
check "deep dotted keys"   "print('a' + '.a'*100000 + ' = 1')"
check "deep inline tables" "print('a = ' + '{ k = '*60000 + '1' + ' }'*60000)"

exit $fail
