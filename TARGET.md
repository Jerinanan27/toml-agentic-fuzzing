# Target

Library: tomlc99
Repo: https://github.com/cktan/tomlc99
Commit: 29076dfd095bbbbd50a3c1b2760d29f4b83e74ac

Grammar: ANTLR `grammars-v4`, `toml/TomlLexer.g4` + `toml/TomlParser.g4`
Vendored at `grammar/` so the build does not depend on upstream moving.

Differential target: tomlc17 (https://github.com/cktan/tomlc17), the
maintained successor that tomlc99's README now points to.

## Environment

- Base image: `ubuntu:24.04`
- Compiler: clang-18
- Stack limit: 8 MB (8388608 bytes)
- Sanitizers: `-fsanitize=address,undefined -fno-sanitize-recover=all`
- Also: `-O1 -g -fno-omit-frame-pointer`

**Every depth threshold in this project is relative to these four
things**: the tomlc99 commit, the base image, the clang version, and the
stack rlimit. A stack overflow depth is a property of the environment as
much as of the library, so a threshold reported without them is not
reproducible. Run with:

```bash
docker run --rm -it -v "$PWD":/work \
    --ulimit stack=8388608:8388608 fuzz:pinned
```

ASan adds redzones to stack frames, so reported thresholds are
ASan-relative. An uninstrumented build overflows deeper.

## Models used

| Experiments | Model | Provider |
|---|---|---|
| 1-4 | `openai/gpt-oss-120b` | Groq |
| 5 | `qwen/qwen3.6-27b` | Groq |

Both open-weight. Selected via the `FUZZ_MODEL` environment variable,
read in `llm.py` - the only file that names a provider.

## Liveness check (8 Aug)

- Deep-nested-array input crashes `toml_cat` with SIGSEGV (exit 139)
- Confirms the recursion bug is present at this commit, before any
  fuzzing work was built on the assumption that it would be

## Exit code contract

| Code | Meaning |
|---|---|
| 0 | Library parsed the input successfully |
| 50 | Library cleanly rejected the input (correct behaviour, not a bug) |
| 51 | The harness itself failed, or the input could not be tested |

Codes 1, 2, 126-165 and 255 are deliberately avoided:

- 1 and 2 are used by sanitizer runtimes and generic errors, so a real
  memory-safety bug would be indistinguishable from a normal rejection
- 126-165 are used by bash for "command not found" and "killed by signal"

Code 51 covers three cases, all of which mean "this input was not fairly
tested" rather than "the parser did something":

1. The input contains an embedded NUL byte. `toml_parse` takes a
   NUL-terminated `char*` with no length parameter, so such an input
   would be silently truncated and the result would describe a different
   input from the one generated. Refusing is more honest than reporting
   a result for the wrong input.
2. The input exceeds an 8 MB cap, a resource guard against a runaway
   generator. This is far above any measured crash threshold - the
   deepest reproducer is about 175 KB - so it cannot suppress a finding.
3. The harness itself ran out of memory.

## Budget enforcement

| Constraint | Where enforced |
|---|---|
| 500 examples per iteration | `run_round(n_examples=500)` |
| 5-second per-input timeout | `oracle.py`, `TIMEOUT_SECONDS` |
| 10-minute wall-clock cap per run | `agent/runner.py`, `WALL_CLOCK_CAP_SECONDS` |
| 8 MB input size guard | `oracle.py`, `MAX_INPUT_BYTES` |
| 5 iterations per experiment | `agent/loop.py`, `MAX_ITERATIONS` |

A truncated run reports `stopped_early: True` in its round log, so a run cut
short by the cap is never mistaken for a complete one.

## Outcome taxonomy

`oracle.py` classifies each run into one of five outcomes. The **order**
of the checks is the design:

1. **HANG** - timed out (5s). Checked first: a hang is a hang regardless
   of what it printed.
2. **CRASH** - sanitizer text in stderr. Checked before the exit code,
   because sanitizer output can appear alongside a healthy-looking exit
   code, and that is exactly the failure this ordering prevents.
3. **CRASH** - killed by a fatal signal (negative return code).
4. **ACCEPTED / REJECTED / HARNESS_ERROR** - the three codes above.
5. **UNKNOWN** - anything else. Surfaces rather than being silently
   filed as fine.

Timeouts are treated as crashes and go through the same triage pipeline,
as the assignment requires. They have no stack trace, so they get a
separate signature scheme based on input shape rather than stack frames.
