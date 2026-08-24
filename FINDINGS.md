# Findings

## Summary

Five experiments against tomlc99 at commit `29076df`, each a 5-iteration
agentic loop of 500 inputs per iteration. All crashes found are
unbounded-recursion stack overflows. No other defect class appeared.

| Exp | Generator vocabulary | Objective     | Model        | Crashes |
|-----|----------------------|---------------|--------------|---------|
| 1   | 9 of 23 productions  | flat          | GPT-OSS-120B | 271     |
| 2   | 9 of 23 productions  | flat          | GPT-OSS-120B | 278     |
| 3   | 22 of 23 productions | flat          | GPT-OSS-120B | 10      |
| 4   | 22 of 23 productions | depth primary | GPT-OSS-120B | 142     |
| 5   | 22 of 23 productions | depth primary | Qwen 3.6 27B | 18 (loop never evolved - see below) |

Experiments 3 and 4 are a controlled pair: one variable changed, the
priority ordering of the objective. Experiment 5 repeats experiment 4's
configuration with a different model family.

## Distinct bugs, triaged by recursion cycle

Crashes are grouped by the set of functions that *repeat* in the stack
trace. Functions appearing once or twice are the exhaustion point
(STRNDUP, expand, normalize_key), which varies run to run and is noise.
Keeping only frequently-repeating frames isolates the recursion cycle,
which is the actual defect.

| Recursion cycle                                 | Defect class                       | Crash threshold |
|-------------------------------------------------|------------------------------------|-----------------|
| parse_array                                     | Deep arrays `[[[...]]]`            | ~14,850         |
| parse_keyval                                    | Deep dotted keys `a.a.a...`        | ~87,270         |
| parse_inline_table + parse_keyval               | Deep inline tables `{ k = {...} }` | ~52,360         |
| parse_array + parse_keyval                      | Mixed array/dotted                 | variant         |
| parse_array + parse_inline_table + parse_keyval | Fully mixed nesting                | variant         |

Five distinct cycles across all experiments.

## Crash thresholds: which number is authoritative

Three measurements exist and they answer different questions.

| Method                                   | Arrays | What it measures                                |
|------------------------------------------|--------|-------------------------------------------------|
| Binary search (`minimize.py`)            | ~14,850| smallest depth that still crashes, converged    |
| Hypothesis shrinker (`triage/shrink.py`) | 15,746 | smallest the shrinker reached in 60 examples    |
| Triage minimum (`triage.py`)             | 15,160 | shallowest crash the generator happened to emit |

**The binary search is authoritative.** It is the only method that tests
both sides of the boundary: it confirms depth N crashes and depth N-1
survives. The shrinker stops at "small enough" rather than minimal within
its example budget; the triage minimum is simply the luckiest sample.

That the three agree within 6% is independent corroboration of the
threshold, arrived at by three different search procedures.

Thresholds for all three defect classes, binary-searched:

```
arrays        ~14,850
inline tables ~52,360
dotted keys   ~87,270
```

All under an 8 MB stack, clang-18, with AddressSanitizer. ASan adds
redzones to stack frames, so these thresholds are ASan-relative; an
uninstrumented build overflows at a greater depth.

Thresholds vary run to run by roughly 6-25 levels, because the exact
point of stack exhaustion depends on runtime memory state. They are not
fixed constants. The three classes differ from each other because each
recursion consumes a different stack-frame size per level.

## Minimized reproducers

```
python3 -c "print('a = '+'['*20000+'1'+']'*20000)"
python3 -c "print('a'+'.a'*100000+' = 1')"
python3 -c "print('a = '+'{ k = '*60000+'1'+' }'*60000)"
```

Each verified by re-running standalone against the pinned build.

Reproducers are written above the measured thresholds deliberately.
A command written at the boundary fails on some runs, since the exact
point of exhaustion varies by 6 to 25 levels with runtime memory state.
Verified on a fresh clone (2025-08-24): 20,000 / 100,000 / 60,000 all
crash; 14,851 / 87,258 / 52,000 do not.

## Resolving the unsymbolicated crashes

73 crashes across experiments 1, 2 and 4 produced `<empty stack>` - no
readable trace, because extreme stack exhaustion left ASan no room to
unwind and print one.

Re-running the same input class at a shallower depth, just past the crash
threshold, restored symbolication and revealed the same
parse_array / parse_inline_table / parse_keyval mixed-recursion cycle.

Conclusion: the unsymbolicated crashes are not a distinct bug. They are
the same defects at depths too extreme for the sanitizer to report.
The technique - diagnose a deep crash by reproducing it shallow - is
what made this determinable rather than assumed.

They are still reported as a separate bucket, because the inference is
from input shape rather than from the stack itself.

## What the expanded grammar vocabulary bought (and did not)

Experiments 1 and 2 used a generator that could express only 9 of the 23
grammar productions in TomlParser.g4. It was structurally incapable of
emitting table headers, datetimes, quoted keys, non-decimal integers, or
three of the four string forms. This was not visible until a
production-coverage metric existed to measure it.

Experiment 4 reached 22 of 23 productions. The result:

**No new defect class.** Every crash in exp4 falls into a recursion cycle
already identified in exp1/exp2. Datetimes, table headers, and the four
integer bases surfaced nothing.

**A new access path.** The exp4 crashes are reached through productions
the earlier generator could not produce:

```
"<astral-plane unicode>" = [[[[[...     quoted key + deep array
'Z<control char>' = { k = { k = ...     literal key + deep inline table
'uQ"6&<astral>Aa' = { k = { k = ...     literal key containing a quote
```

Exp1 and exp2 only ever produced bare keys (`a = ...`). Exp4 reaches the
same defects through `quoted_key` carrying astral-plane and control
characters.

**The conclusion, supported by measured coverage:** tomlc99's
memory-safety defects concentrate in its recursive descent. Its scalar
token handling - all four datetime forms, all four integer bases, all
four string forms - is comparatively robust. This is a stronger claim
than "I found more bugs", because it is backed by knowing which
productions were exercised rather than assuming.

Note on exp4's reported minimum depths (~100,000): exp4's generator draws
depth from [100,000, 110,000], so it never attempted anything shallower.
That minimum is a property of the generator, not a threshold.

## The objective's priority ordering determined whether the loop worked

Experiments 3 and 4 are a controlled comparison. Same loop, same model,
same budget, same seed strategy. One variable changed: whether the
feedback declares a priority between nesting depth and acceptance rate.

Experiment 3's feedback presented four measurements as equally weighted complaints.
Both "depth TOO SHALLOW" and "acceptance TOO LOW" fired every round with
no statement of which mattered more.

| Iteration | 0       | 1       | 2          | 3      | 4      | 5      |
|-----------|---------|---------|------------|--------|--------|--------|
| Depth max | 110,001 | 108,246 | **20,001** | 20,000 | 20,001 | 19,970 |
| Crashes   | 2       | 0       | 1          | 4      | 1      | 2      |

The model resolved the ambiguity by satisfying the objective it could
move cheaply. Acceptance climbed 0.000 to 0.176 while depth collapsed by
a factor of five at iteration 2 and never recovered. Below 20,000 levels
only one of the three defect classes is reachable at all.

Experiment 4 changed the feedback to label depth PRIMARY and acceptance
SECONDARY, and to state that acceptance should be raised by making the
shallow statements well-formed rather than by removing deep values.

| Iteration | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Depth max | 109,761 | 110,001 | 110,001 | 110,001 | 110,001 | 110,001 |
| Crashes | 5 | 5 | **121** | 2 | 4 | 5 |

Depth held. The finding is that an underspecified objective is not
neutral - the model will resolve the ambiguity, and it will resolve it
toward whichever term is cheapest to satisfy.

## A generator defect outperformed the corrected generator

Experiment 4's iteration 2 found 121 crashes; iteration 3 found 2. Depth
was identical (110,001) in both. The difference was a one-line defect:

```python
st.just(st.just(RawValue("0", "DEC_INT")))    # iteration 2
st.just(RawValue("0", "DEC_INT"))             # iteration 3
```

The double-wrapped `st.just` produced a Hypothesis strategy *object* as
the innermost value rather than a RawValue. The serializer fell through
to `str(item)`, emitting a long malformed payload at the centre of the
nesting. That payload triggered stack exhaustion far more often than the
clean `0` did. When the model repaired the typo in the next iteration,
the crash rate fell by 98%.

Two consequences:

1. **Crash yield depends on payload shape, not only nesting depth.**
   Depth was constant across all six iterations; crash count varied by
   60x. Depth is necessary but not sufficient.

2. **A proxy signal rewarding crash count would have rewarded a bug in
   the generator.** This is a second, sharper argument for the decision
   recorded in SIGNAL.md: crash count was rejected as a steering signal
   for lack of gradient, and it turns out also to be gameable by
   generator defects.

## Acceptance rate degrades as the generator improves

Acceptance rate was chosen as a proxy component on the reasoning that a
generator rejected at the parser's front door tests nothing. That
reasoning held for the random baseline:

```
ACCEPTED 4    REJECTED 490    CRASH 0
```

Near-zero acceptance, zero crashes - the metric correctly diagnosed a
useless generator.

It failed in experiment 4:

```
ACCEPTED 0    REJECTED 379    CRASH 121
```

Identical acceptance, 121 crashes. The parser was being driven thousands
of stack frames deep on inputs it then correctly rejected.

The cause is that acceptance is measured per document, and REJECTED
conflates two very different events: rejected at the first byte, and
rejected after 14,000 recursive calls. Additionally, tomlc99 rejects
deeply-nested input even when it survives parsing it, so any document
containing a deep value is rejected regardless of how well-formed its
other statements are.

**Acceptance rate is a valid early-stage health check and an invalid
late-stage steering signal** - it stops discriminating precisely when the
generator becomes good at reaching the target defect class.

The fix, not implemented for want of time, is to measure acceptance only
over documents containing no deep value, so the metric reports on the
statements whose validity the generator can actually control.

## Control experiment

Four arms, 500 inputs each, identical budget, repeated three times.
Crash counts at this scale are noisy, so means are reported alongside the
individual runs.

| Arm | Run 1 | Run 2 | Run 3 | Mean | Max depth |
|---|---|---|---|---|---|
| Random baseline | 0 | 0 | 0 | **0.0** | 0 |
| Grammar seed (iteration 0) | 8 | 1 | 6 | **5.0** | ~110,000 |
| Exp3 final (flat objective) | 1 | 2 | 1 | **1.3** | ~20,000 |
| Exp4 final (depth primary) | 6 | 8 | 6 | **6.7** | ~110,000 |

Three readings, in decreasing order of confidence:

**Grammar-derived generation beats random.** Zero crashes in all three
baseline runs, against a mean of 5.0 for the grammar-seeded strategy.
Random byte generation never reaches the defect class at all - it cannot
construct 14,850 balanced brackets by chance.

**A flat objective degraded the generator below its own seed.** 5.0 to
1.3, with depth collapsing from ~110,000 to ~20,000 in every run. Five
iterations of refinement under an ambiguous objective made the fuzzer
worse than the thing it started from. This is the strongest evidence in
the project that proxy-signal design, not iteration count, is what
determines whether the loop works.

**Refinement did not measurably improve on the seed.** 5.0 to 6.7, with
overlapping ranges (1-8 against 6-8). I cannot claim the loop improved
the generator. The honest statement is that the prioritised objective
*preserved* the seed's capability while the flat one destroyed it.

The likely reason is that the seed prompt is unusually specific: it
carries the ANTLR grammar, the documented library gap, the known crash
thresholds, and an explicit requirement to exceed 100,000 levels of
nesting. Where a seed can be made that good, there is little left for
iteration to discover. The assignment notes that 5 iterations took a
parson/JSON generator from 0 crashes to reliable ones; my seed started at
5.0, which is a different starting point and produces a different
conclusion.

Caveat: the exp3 arm uses the `random` module internally (the model
introduced it at an iteration that predates the validation gate for it),
so that arm's individual runs are not exactly reproducible.

## Cost and efficiency

Token counts are taken from the API's `usage` field, not estimated.

| Experiment | Input tokens | Output tokens | Cost |
|---|---|---|---|
| Exp 1 + 2 combined | 14,806 | 18,785 | $0.013 |
| Exp 4 | 11,148 | 13,584 | $0.0098 |
| Exp 5 | 11,855 | 13,142 | $0.0097 |

Model: `openai/gpt-oss-120b` (Groq) for experiments 1-4, `qwen/qwen3.6-27b`
for experiment 5. Both open-weight; neither is a frontier model. The task
did not require one.

Total across all experiments is well under $0.05 - roughly 1% of the $5
budget. **The binding constraint was never cost.** It was the free-tier
rate limit of 8,000 tokens per minute, which forced a 65-second wait
between refinement calls and, more importantly, capped the output budget
at 4,000 tokens - the confound that makes the experiment-5 comparison
inconclusive.

The dominant workload was local and free: roughly 15,000
sanitizer-instrumented harness executions, which cost nothing but
wall-clock time.

Reproducibility note: the model identity was not recorded in the
iteration logs for experiments 1-4. It was resolved from the default in
`llm.py`, which is verifiable but weaker than a logged record. Logging
was added for experiment 5.

## Differential test against tomlc17 (the maintained successor)

tomlc99 is obsolete; its README points to tomlc17. A second harness
(`harness/harness17.c`) was built for tomlc17's changed API, which takes an
explicit length, and all three reproducers were replayed.

**The recursion overflow is fixed.** No input class produced a crash, a
stack overflow, or a sanitizer abort attributable to nesting depth.

UBSan does report undefined behaviour at `tomlc17.c:110`:

    runtime error: member access within null pointer of type 'page_t'

This is **not** a defect reachable by input. Line 110 is inside
`page_create()` and computes a struct size with a hand-rolled `offsetof`:

    size_t totalsz = (size_t) & ((page_t *)0)->data[size];

Forming a member access through a null pointer is undefined by the C
standard, though it behaves as intended on every mainstream compiler. The
line executes on every call to `page_create()`, so the report fires on
`a = 1` exactly as it does on a 20,000-level nested array. Verified against
commit 64a063b (22 Aug 2026): identical output and exit status for both.

An earlier draft of this document described the report as a null-pointer
dereference from an unchecked `page_create()` return, reachable by deep
input. Reading the source at the cited line disproved that. It is recorded
here because the correction matters: a sanitizer message names a location,
not a cause, and the two are easy to conflate.

## Cross-model comparison: inconclusive

To test whether the result comes from the loop design or from one
specific model, experiment 5 repeated experiment 4's exact configuration
with a different-family model (Qwen 3.6 27B instead of GPT-OSS-120B),
changing one environment variable. This is possible because the provider
and model are named in exactly one place, inside `call_llm()`.

**The comparison did not succeed.** Qwen failed validation in 5 of 5
refinement attempts, so the loop never evolved - all six rounds ran the
identical seed strategy, and experiment 5's numbers are six samples of
one generator rather than an evolution.

| Round | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Depth max | 110,000 | 110,001 | 110,000 | 110,001 | 110,000 | 110,001 |
| Crashes | 2 | 3 | 5 | 2 | 5 | 1 |
| Refine result | rejected | rejected | rejected | rejected | rejected | - |

The five rejections:

```
NameError    name 'simple_basic_key_content' is not defined
SyntaxError  invalid syntax (line 139)
TypeError    text() got an unexpected keyword argument 'filter'
TypeError    integers() got an unexpected keyword argument 'min_size'
TypeError    integers() got an unexpected keyword argument 'min_size'
```

Two of these are invalid Hypothesis API calls, one repeated verbatim
after correction - evidence of a genuine capability difference. The
`SyntaxError` and the `NameError` on an undefined helper are both
consistent with truncation at the 4,000-token output cap, which
GPT-OSS-120B's outputs (~3,200-3,500 tokens) approached but did not
exceed. **This is a confound I could not eliminate:** raising the cap was
not possible within the 8,000 tokens-per-minute free-tier rate limit
without trimming the refine prompt, which would have changed a second
variable.

So the generalisation of the loop design across model families remains
untested. What experiment 5 does establish:

- **The seed prompt is model-independent.** Round 0 under both models
  produced 22/23 production coverage and ~110,000 depth (GPT-OSS: 5
  crashes; Qwen: 2). The grammar-seeded prompt does its job regardless of
  which model reads it.
- **The validation gate held under adversarial conditions.** Five
  malformed strategies produced five rejections and zero contamination of
  the results. The loop's refusal to regress is what kept experiment 5
  interpretable rather than corrupt.
- **The two model families fail differently.** GPT-OSS invents plausible
  API signatures; Qwen produces internally inconsistent code. Both are
  caught by executing the generated code rather than inspecting it, which
  is the argument for validating by execution.

An earlier cross-model run under the experiment-1/2 configuration (9
productions, flat objective) did show both models improving similarly.
That configuration no longer exists, so those numbers are not reported
here as evidence about the current design.

## Under-tested areas

Named specifically, from production-coverage data rather than intuition:

- **`bool_`** is the one production never covered in several exp4 rounds.
- **Multi-line strings** (`ML_BASIC_STRING`, `ML_LITERAL_STRING`) are
  emitted as fixed literal payloads rather than generated, so their
  escape handling is barely explored.
- **`array_table`** (`[[products]]`) is generated but never appears in a
  crashing input; its `descend_keypart` path is likely under-tested.
- **Datetime edge cases** beyond month-13/day-32 - leap seconds,
  timezone offset extremes, fractional-second precision.
- **Deep nesting through table headers** rather than through values was
  never attempted.