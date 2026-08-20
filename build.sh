#!/bin/bash
# Build the sanitizer-instrumented harnesses.
# Run inside the pinned container:
#   docker run --rm -it -v "$PWD":/work --ulimit stack=8388608:8388608 fuzz:pinned
#   ./build.sh
set -e

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
fi

echo "Done."