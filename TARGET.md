# Target

Library: tomlc99
Repo: https://github.com/cktan/tomlc99
Commit: 29076dfd095bbbbd50a3c1b2760d29f4b83e74ac

Environment:
- Base image: ubuntu:24.04
- Compiler: clang-18
- Stack limit: 8 MB (8388608 bytes)

Liveness check (8 Aug):
- Deep-nested-array input crashes toml_cat with SIGSEGV (exit 139)
- Confirms the recursion bug is present at this commit

## Exit code contract

| Code | Meaning |
|---|---|
| 0 | Library parsed the input successfully |
| 50 | Library cleanly rejected the input (correct behaviour, not a bug) |
| 51 | The harness itself failed (bad arguments, no input) |

Codes 1, 2, 126-165 and 255 are deliberately avoided:
- 1 and 2 are used by sanitizer runtimes and generic errors, so a real
  memory-safety bug would be indistinguishable from a normal rejection
- 126-165 are used by bash for "command not found" and "killed by signal"