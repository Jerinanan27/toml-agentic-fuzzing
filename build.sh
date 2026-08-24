#!/bin/bash
# Build the sanitizer-instrumented harnesses.
# Run inside the pinned container:
#   docker run --rm -it -v "$PWD":/work --ulimit stack=8388608:8388608 fuzz:pinned
#   ./build.sh
set -e

TOMLC99_COMMIT=29076dfd095bbbbd50a3c1b2760d29f4b83e74ac

# tomlc99 is gitignored, being an upstream repository rather than this
# project's code, so a fresh clone of this repo will not contain it.
# Fetch at the pinned commit when absent.
if [ ! -f tomlc99/toml.c ]; then
    echo "tomlc99 not found; cloning at ${TOMLC99_COMMIT}"
    rm -rf tomlc99
    git clone --quiet https://github.com/cktan/tomlc99.git tomlc99
    git -C tomlc99 checkout --quiet "${TOMLC99_COMMIT}"
fi

# The working tree is bind-mounted from the host, so git inside the container
# sees a directory owned by a different uid and refuses to read it. Marking
# the path as safe is what lets the pin check run in both places.
git config --global --add safe.directory "$(pwd)/tomlc99" >/dev/null 2>&1 || true
git config --global --add safe.directory /work/tomlc99 >/dev/null 2>&1 || true

# Verify the pin. Every depth threshold in the report is relative to this
# commit, so building against anything else produces numbers that will not
# match the report.
if ! ACTUAL=$(git -C tomlc99 rev-parse HEAD 2>&1); then
    echo "ERROR: cannot read the tomlc99 commit:" >&2
    echo "  ${ACTUAL}" >&2
    exit 1
fi

if [ "${ACTUAL}" != "${TOMLC99_COMMIT}" ]; then
    echo "ERROR: tomlc99 is at ${ACTUAL}, expected ${TOMLC99_COMMIT}" >&2
    exit 1
fi

SAN_FLAGS="-fsanitize=address,undefined -fno-sanitize-recover=all"
# -O1                     ASan's documented recommendation
# -g                      file/line info in stack traces
# -fno-omit-frame-pointer readable frames, required for crash dedup
# -fno-sanitize-recover   UBSan aborts instead of printing and continuing
COMMON="-O1 -g -fno-omit-frame-pointer"

echo "Building tomlc99 harness..."
clang $COMMON $SAN_FLAGS \
      -I tomlc99 \
      harness/harness.c tomlc99/toml.c \
      -o harness/harness_asan

if [ -d tomlc17/src ]; then
    echo "Building tomlc17 harness (differential test)..."
    clang $COMMON $SAN_FLAGS \
          -I tomlc17/src \
          harness/harness17.c tomlc17/src/tomlc17.c \
          -o harness/harness17_asan
else
    echo "tomlc17 not present; skipping differential harness."
    echo "  git clone https://github.com/cktan/tomlc17.git"
    echo "  (see FINDINGS.md for the commit the reported fault was observed at)"
fi

echo "Done."