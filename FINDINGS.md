# Findings

## Distinct bugs (both experiments, triaged by recursion cycle)


| Recursion cycle                                 | Defect class                     | Crash threshold (8 MB stack, clang-18) |
|-------------------------------------------------|----------------------------------|----------------------------------------|
| parse_array                                     | Deep arrays [[[...]]]            | ~14,850                                |
| parse_keyval                                    | Deep dotted keys a.a.a...        | ~87,270                                |
| parse_inline_table + parse_keyval               | Deep inline tables { k = {...} } | ~52,360                                |
| parse_array + parse_keyval                      | Mixed array/dotted               | (variant)                              |
| parse_array + parse_inline_table + parse_keyval | Fully mixed nesting              | (variant)                              |

## Resolving the unsymbolicated crashes

48 crashes (17 in exp1, 31 in exp2) produced <empty stack> - no trace,
because extreme stack exhaustion left ASan no room to unwind.

Re-running the same input class at a shallower depth (just past the
crash threshold) restored symbolication, revealing the same
parse_array / parse_inline_table / parse_keyval mixed-recursion cycle.

Conclusion: the unsymbolicated crashes are NOT a distinct bug. They are
the same mixed-nesting defect at depths too extreme for the sanitizer
to produce a trace. Technique: diagnose deep crashes at shallow depth.
All are unbounded-recursion stack overflows under an 8 MB stack, clang-18.

*Thresholds are approximate and vary run-to-run by roughly 6-25 levels,
because the exact point of stack exhaustion depends on runtime memory
state. They are not fixed constants. Thresholds differ between defect
classes because each recursion consumes a different stack-frame size
per level.

## Crash counts

Experiment 1 (arrays + inline tables)               : 271 crashes
Experiment 2 (arrays + inline tables + dotted keys) : 278 crashes

## Minimized reproducers

array reproducer:
  python3 -c "print('a = ' + '['*14851 + '1' + ']'*14851)"

dotted reproducer:
  python3 -c "print('a' + '.a'*87258 + ' = 1')"

inline table reproducer:
  python3 -c "print('a = ' + '{ k = '*52000 + '1' + ' }'*52000)"

## Control experiment (500 inputs each, same budget)

| Approach                       | Crashes | Max depth |
|--------------------------------|---------|-----------|
| Random baseline                | 0       | 0         |
| Seed strategy (iteration 0)    | 0       | 3,939     |
| Evolved strategy (iteration 5) | 55      | 200,000   |

Random generation and the unrefined seed both found zero crashes.
Only the evolved strategy, driven by the proxy-signal feedback loop,
reached crash-triggering depth. The improvement is attributable to
the feedback loop, not to structured generation alone: the seed was
already structured and still found nothing.


## Cost and efficiency

Total LLM usage across both experiments (12 refinement calls):
- Input tokens  : 14,806  (x $0.15/M = $0.0022)
- Output tokens : 18,785  (x $0.60/M = $0.0113)
- Total         : 33,591 tokens
- Total cost    : ~$0.013 (about 0.3% of the ~$5 budget)

Model: openai/gpt-oss-120b (Groq), an open-weight model - not a
frontier model. The task did not require one.

Efficiency: 549 crashes found (~61 tokens/crash) across 5 distinct
recursion cycles. The dominant workload was the ~6,000 local harness
executions (500 x 12 rounds), which cost nothing.

The binding constraint was not cost but the free-tier rate limit
(8,000 tokens/minute), which forced a 65-second wait between rounds.

## Differential test against tomlc17 (the maintained successor)

tomlc99 is obsolete; its README points to tomlc17. I built a second
harness (harness/harness17.c) for tomlc17's changed API (which takes
an explicit length - fixing the embedded-NUL limitation of tomlc99)
and ran all three reproducers against it.

Result: the recursion/stack-overflow was FIXED, but the same deeply-
nested inputs trigger a DIFFERENT, newly-introduced bug:

- Fault: null-pointer dereference at tomlc17.c:110
- Root cause: page_create() (tomlc17.c:105) returns NULL when the
  requested size exceeds its 1GB cap, but a caller dereferences the
  result without a null check.
- Impact: denial-of-service on the current, maintained version.
- All three input classes (array, dotted, inline table) trigger it.

This turns a rediscovery into a novel finding: the fix for the old
recursion bug introduced a distinct defect reachable by the same
input class.


## Second model: Qwen 3.6 27B (cross-model validation)

To test whether improvement comes from the loop design or from one
specific model, I ran the identical loop with a different-family model
(Qwen 3.6 27B instead of GPT-OSS-120B), changing only one config value -
made possible by the provider-agnostic call_llm() design.

|                  | GPT-OSS-120B | Qwen 3.6 27B |
|------------------|--------------|--------------|
| Seed crashes     | 0            | 0            |
| Final crashes    | ~49          | 47           |
| Final depth      | 200,000      | 200,000      |
| Final acceptance | 0.82         | 0.67         |

Both models, driven by the same proxy signal, improved from 0 crashes
to ~50. The improvement is therefore attributable to the loop design,
not to a single model. Notably, Qwen kept acceptance within the target
0.3-0.7 band while GPT-OSS drifted slightly above it - different models
satisfy the same objective differently.

Implementation note: Qwen is a reasoning model that consumed its token
budget on <think> output. Setting reasoning_effort="none" and stripping
think-tags was required - a one-file change, isolated behind call_llm().