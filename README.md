# Agentic Blackbox Fuzzing of a TOML Parser

An LLM-driven fuzzer that turns a formal grammar into a Hypothesis
strategy, measures that strategy against a proxy signal, and refines it
across iterations — with no access to code coverage.

**Target:** [tomlc99](https://github.com/cktan/tomlc99), a C TOML parser,
pinned at commit `29076df`.

## The problem

Fuzzers are normally steered by code coverage. This project is
**blackbox**: sanitizers only, no instrumentation. The core design
question is what to measure instead — the *proxy signal* — to steer an
LLM toward inputs that find bugs. See [`SIGNAL.md`](SIGNAL.md).

## How it works

```
grammar (TomlParser.g4) ──► seed prompt ──► LLM ──► Hypothesis strategy
                                                          │
                                                          ▼
                            structured AST nodes ──► serialize ──► TOML text
                                     │                                  │
                                     ▼                                  ▼
                              metrics.py                    harness + ASan/UBSan
                        (depth, production coverage)                    │
                                     │                                  ▼
                                     └──────► proxy signal ◄──── oracle (5 outcomes)
                                                    │
                                                    ▼
                                              LLM rewrites
```

The generator emits **structured nodes, not text**. A separate serializer
renders them to TOML. This makes nesting depth a tree walk rather than a
bracket-counting heuristic, and makes grammar-production coverage exact
rather than inferred.

The LLM sees only the proxy signal. It never sees the target's source.

## Verify

```bash
docker build -t fuzz:pinned .
docker run --rm -it -v "$PWD":/work --ulimit stack=8388608:8388608 fuzz:pinned
# inside the container:
./build.sh && ./reproduce.sh
```

`build.sh` fetches tomlc99 at the pinned commit and refuses to build against
any other. `reproduce.sh` exits non-zero if any of the three defect classes
stops reproducing.

Harness behaviour on sample inputs (spec Step 2) — valid, malformed,
deeply nested, empty, and binary-with-NUL:

```bash
python3 oracle.py
```

Recorded output: [`docs/harness_demo.txt`](docs/harness_demo.txt)

## Results

**Grammar-derived generation beats random** (control experiment,
500 inputs per arm, mean of three runs):

| Arm | Crashes | Max depth |
|---|---|---|
| Random baseline | 0.0 | 0 |
| Grammar-seeded strategy | 5.0 | ~110,000 |
| Exp3 final — flat objective | 1.3 | ~20,000 |
| Exp4 final — depth prioritised | 6.7 | ~110,000 |

Two things this shows, and one it does not:

- Random generation found **zero** crashes in all three runs. Grammar
  derivation is what makes the defect class reachable at all.
- A **flat objective made the generator worse than its own seed** (5.0 →
  1.3). Five refinement iterations under an underspecified objective
  degraded capability.
- It does **not** show that refinement improved on the seed (5.0 → 6.7,
  overlapping ranges). With a sufficiently specific seed prompt, iteration
  had little left to contribute.

**Bugs found:** five distinct recursion cycles, all unbounded-recursion
stack overflows. Binary-searched thresholds under an 8 MB stack with
ASan: arrays ~14,850, inline tables ~52,360, dotted keys ~87,270.

**Differential test against the maintained successor
([tomlc17](https://github.com/cktan/tomlc17)):** the recursion overflow is
fixed, and the reproducers find no memory-safety defect. UBSan reports
undefined behaviour at `tomlc17.c:110`, but that line is a hand-rolled
`offsetof` inside `page_create()` and fires on `a = 1` as readily as on a
20,000-level array, so it is not reachable by input.

Full details, including negative results, in [`FINDINGS.md`](FINDINGS.md).

## Reproduce

```bash
docker build -t fuzz:pinned .

docker run --rm -it -v "$PWD":/work \
    --ulimit stack=8388608:8388608 fuzz:pinned

# inside the container:
cd /work
./build.sh                   # sanitizer build of harness + tomlc99

python3 agent/seed.py        # generate iteration 0 from the grammar
FUZZ_TAG=exp4 python3 agent/loop.py   # run the agentic loop
python3 control.py           # four-arm control experiment
python3 triage.py            # group crashes by recursion cycle
python3 minimize.py          # binary-search crash thresholds
python3 triage/shrink.py     # Hypothesis shrinker minimisation
```

The `--ulimit stack=8388608` flag is **required**. Every depth threshold
reported here is relative to an 8 MB stack; without the flag the numbers
are not comparable.

## Repository map

| Path | What it is |
|---|---|
| `grammar/Toml{Lexer,Parser}.g4` | The ANTLR grammar (from grammars-v4) |
| `GRAMMAR.md` | Grammar in plain words + spec-vs-library gap |
| `harness/harness.c` | Feeds one input to tomlc99, reports the outcome |
| `harness/harness17.c` | Same, for tomlc17 (differential test) |
| `build.sh` | Sanitizer build |
| `oracle.py` | Classifies a run into 5 outcomes |
| `metrics.py` | AST node types, depth, production coverage, serializer |
| `SIGNAL.md` | The proxy-signal design, and how it was revised |
| `prompts/seed.txt` | The seed prompt: contract + grammar + gap + edge cases |
| `agent/seed.py` | Generates iteration 0, with validation and repair |
| `agent/loop.py` | The agentic loop |
| `agent/runner.py` | Runs one round, computes metrics, builds feedback |
| `agent/refine.py` | Calls the LLM, validates returned code |
| `llm.py` | Provider-agnostic LLM interface |
| `triage.py` | Groups crashes by recursion cycle |
| `triage/shrink.py` | Hypothesis-shrinker minimisation per signature |
| `minimize.py` | Binary-searches crash-depth thresholds |
| `control.py` | Four-arm control experiment |
| `strategies/baseline.py` | The naive control arm |
| `strategies/generated_exp*/` | One file per iteration — the evolution log |
| `logs/iterations_exp*/` | Per-round metrics, feedback, tokens, model |
| `crashes_exp*/` | Full input, full stderr, exit code, signature |
| `FINDINGS.md` | All results, including negative ones |
| `TARGET.md` | Pinned environment and exit-code contract |

## Environment

- Base: `ubuntu:24.04`, clang-18, 8 MB stack
- LLM: `openai/gpt-oss-120b` via Groq (open-weight, not frontier)
- Total LLM cost across all experiments: under $0.05, ~1% of the $5 budget

