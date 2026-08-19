# Agentic Blackbox Fuzzing of a TOML Parser

An LLM-driven fuzzer that writes its own input generator, measures how
well it performs against a proxy signal, and improves itself across
iterations — with no access to code coverage.

**Target:** [tomlc99](https://github.com/cktan/tomlc99), a C TOML parser,
pinned at commit `29076df`.

## Result in one line

Starting from a generator that found **0 crashes**, the feedback loop
drove it to find **~55 crashes per 500 inputs** — while a random baseline
and the un-refined seed both found **0**. The improvement comes from the
loop, not from a lucky model: a second, different-family model reproduced
the same 0→~50 gain.

## The problem

Fuzzers are normally guided by code coverage. This project is **blackbox**:
no coverage instrumentation. The core question is what to measure instead
— the *proxy signal* — to steer an LLM toward inputs that find bugs.
See [`SIGNAL.md`](SIGNAL.md) for the full design.

## How it works

```
seed strategy
     │
     ▼
generate 500 inputs ──► harness + sanitizers ──► oracle (5 outcomes)
     ▲                                                │
     │                                                ▼
LLM rewrites          ◄── proxy-signal feedback ◄── metrics
   strategy               (depth, type coverage,
                           acceptance, error diversity)
```

Five iterations. The LLM only ever sees the proxy signal, never the
target's source.

## Key results

**Method works (control experiment, 500 inputs each):**

| Approach | Crashes | Max depth |
|---|---|---|
| Random baseline | 0 | 0 |
| Seed strategy (iteration 0) | 0 | 3,939 |
| Evolved strategy (iteration 5) | 55 | 200,000 |

**Bugs found (triaged by recursion cycle):** deep arrays, deep dotted
keys, deep inline tables, and mixed nestings — all unbounded-recursion
stack overflows. Approximate crash thresholds under an 8 MB stack:
arrays ~14,850, inline tables ~52,400, dotted keys ~87,300.

**Differential test against the maintained successor
([tomlc17](https://github.com/cktan/tomlc17)):** the stack-overflow
recursion was fixed, but the same deeply-nested inputs trigger a
*different, newly-introduced* bug — a null-pointer dereference at
`tomlc17.c:110`, caused by an unchecked return from `page_create()`.

**Cross-model validation:** rerunning the loop with Qwen 3.6 27B
(vs GPT-OSS-120B) reproduced the 0→~50 crash improvement, showing the
result is driven by the loop, not a single model.

Full details in [`FINDINGS.md`](FINDINGS.md).

## Reproduce

Everything runs in a pinned Docker environment.

```bash
# build the environment
docker build -t fuzz:pinned .

# enter it (8 MB stack matters - see below)
docker run --rm -it -v "$PWD":/work \
    --ulimit stack=8388608:8388608 fuzz:pinned

# inside the container:
cd /work
clang -O1 -g -fno-omit-frame-pointer \
      -fsanitize=address,undefined -fno-sanitize-recover=all \
      -I tomlc99 harness/harness.c tomlc99/toml.c -o harness/harness_asan

python3 agent/loop.py        # run the agentic loop
python3 control.py           # run the control experiment
python3 triage.py            # group crashes into distinct bugs
python3 minimize.py          # find crash-depth thresholds
```

Crash depth thresholds depend on the stack limit, so the
`--ulimit stack=8388608` flag is required for reproducible numbers.

## Repository map

| Path | What it is |
|---|---|
| `harness/harness.c` | Feeds one input to tomlc99, reports the outcome |
| `oracle.py` | Classifies a run into 5 outcomes (accept/reject/crash/hang/error) |
| `metrics.py` | Structure depth, type coverage, serializer |
| `SIGNAL.md` | The proxy-signal design (the core decision) |
| `agent/loop.py` | The agentic loop |
| `agent/runner.py` | Runs one round, builds feedback |
| `agent/refine.py` | Calls the LLM, validates returned code |
| `llm.py` | Provider-agnostic LLM interface |
| `triage.py` | Groups crashes by recursion cycle |
| `minimize.py` | Binary-searches crash-depth thresholds |
| `control.py` | Random vs seed vs evolved experiment |
| `GRAMMAR.md` | TOML grammar and spec-vs-library gaps |
| `FINDINGS.md` | All results |
| `TARGET.md` | Pinned environment and exit-code contract |
| `logs/`, `crashes/`, `strategies/generated*` | Raw experiment data |

## Environment

- Base: `ubuntu:24.04`, clang-18
- Stack limit: 8 MB
- LLM: GPT-OSS-120B (and Qwen 3.6 27B) via Groq
- Total LLM cost: ~$0.013


