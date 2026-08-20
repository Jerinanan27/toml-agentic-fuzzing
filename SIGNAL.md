# The Proxy Signal

## Why a proxy signal is needed

Normally a fuzzer is judged by code coverage - which lines of the target
program its inputs reached. This assignment is blackbox: I cannot see
inside the parser. I can only observe what leaks out (exit code, error
message, run time).

So I need a substitute measurement, taken from outside, that stands in
for "am I testing more of this parser?" That substitute is the proxy
signal, and choosing it is the core design decision of the loop.

This document records the signal I designed, the objective I first wrote,
why that objective failed, and what I changed it to. The revision is part
of the design, not a correction to hide.

## The four components I chose

### 1. Grammar production coverage

How many of the 23 parser productions in `TomlParser.g4` appear in the
generated inputs.

Why: this is the closest structural analogue to code coverage that I can
compute without instrumentation. A production that never appears is
parser code I provably never reached.

Measuring it exactly is only possible because the generator emits
structured nodes rather than TOML text - I know which productions I
emitted because I emitted them, and I never have to re-parse my own
output to find out.

I exclude `comment_or_nl` and `nl_or_comment` from the 23. They are
whitespace-handling rules, not content, and counting them would inflate
the number without meaning anything.

**Note on the first version.** My initial signal counted "6 distinct node
types" - a category I invented. Nobody could check that number against
anything. Switching to production names taken from the grammar file made
it verifiable, and immediately revealed that my experiment 1 and 2
generator reached only 9 of 23 productions. I had been fuzzing a fraction
of TOML without knowing it.

### 2. Nesting depth

Maximum and average depth of the generated structure.

Why: the defect class in this parser is unbounded recursion, and it is
depth-gated. Arrays do not crash until about 14,850 levels; inline tables
until about 52,360; dotted keys until about 87,270. A generator that
never exceeds a few hundred levels cannot find these bugs at all, and the
depth distribution tells me that before I waste a run finding out.

My baseline run had an average depth of 1.6.

### 3. Acceptance rate

What fraction of generated documents the parser accepts.

Why: if almost nothing is accepted, the generator may be producing
garbage that is rejected at the first byte, in which case the parser's
real logic is never reached.

**This component did not work as intended - see below.**

### 4. Rejection-message diversity

How many distinct error messages the parser produces.

Why: if every rejection carries the same message, the generator has
converged on one shape of broken file and stopped exploring. Many
distinct messages mean many different parts of the parser's error
handling are being reached. Since I cannot see the parser's code, these
messages are the parser describing itself from the inside.

## The objective I first wrote, and why it failed

> Reach at least 6 node types, then maximise nesting depth, while keeping
> acceptance rate between 0.3 and 0.7.

I intended that as an ordering. The feedback I actually sent the model
did not express one - it presented four measurements as four equally
weighted complaints. Every round it said both "depth TOO SHALLOW" and
"acceptance TOO LOW", with nothing to say which mattered more.

Experiment 3 shows what the model did with that:

| Iteration | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Depth max | 110,001 | 108,246 | **20,001** | 20,000 | 20,001 | 19,970 |
| Acceptance | 0.000 | 0.110 | 0.150 | 0.160 | 0.170 | 0.176 |
| Crashes | 2 | 0 | 1 | 4 | 1 | 2 |

It satisfied the term it could move cheaply. Acceptance climbed steadily;
depth collapsed by a factor of five and never recovered. Below 20,000
levels only one of the three defect classes is reachable.

The lesson: **an underspecified objective is not neutral.** The model
will resolve the ambiguity, and it will resolve it toward whatever is
easiest to satisfy, not toward what I meant.

## The objective I use now

> Maximise grammar production coverage and nesting depth. Depth is
> primary. Acceptance rate is secondary and should be raised by making
> the shallow statements well-formed, never by removing deep values.

Experiment 4 changed only that - same loop, same model, same budget, same
seed:

| Iteration | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Depth max | 109,761 | 110,001 | 110,001 | 110,001 | 110,001 | 110,001 |
| Crashes | 5 | 5 | 121 | 2 | 4 | 5 |

Depth held for the whole run.

## Where acceptance rate broke

I chose acceptance rate on the reasoning that a generator rejected at the
front door tests nothing. That reasoning held for the random baseline:

```
ACCEPTED 4    REJECTED 490    CRASH 0
```

Near-zero acceptance, zero crashes. The metric correctly said "this
generator is useless."

It failed in experiment 4:

```
ACCEPTED 0    REJECTED 379    CRASH 121
```

Same acceptance, 121 crashes. The parser was being driven thousands of
stack frames deep on inputs it then correctly rejected.

Two causes:

1. **REJECTED conflates two different events** - rejected at the first
   byte, and rejected after 14,000 recursive calls. Both count the same.
   Acceptance rate cannot tell them apart, so it cannot tell a useless
   generator from a very effective one.

2. **Acceptance is measured per document.** Once I moved from generating
   a single value to generating multi-statement documents, one malformed
   line rejects all fifteen. And tomlc99 rejects deeply nested input even
   when it survives parsing it, so any document containing a deep value
   is rejected regardless of how well-formed the rest of it is.

**Conclusion: acceptance rate is a valid early-stage health check and an
invalid late-stage steering signal.** It stops discriminating precisely
when the generator becomes good at reaching the target defect class.

The fix I would apply with more time is to measure acceptance only over
documents that contain no deep value, so the number reports on the
statements whose validity the generator can actually control.

## What I rejected, and why

**Crash count as the steering signal.**

Crash count is zero for most of a run, so it gives the model no gradient
to follow. Telling it "you failed" five times says nothing about which
direction to move.

Experiment 4 gave me a second and sharper reason. Iteration 2 found 121
crashes; iteration 3 found 2, at identical depth. The difference was a
defect in the generator - a double-wrapped `st.just` that serialised a
Hypothesis strategy object instead of a value, producing a long malformed
payload at the centre of the nesting. That accident triggered stack
exhaustion far more often than the correct value did.

So a signal that rewarded crash count would have rewarded a bug in the
generator, and penalised the model for fixing it. Crash count is not just
gradient-poor, it is gameable.

Crash *signatures* are still sent to the model, as the assignment
requires - but as context ("these cycles are already found, target
something else"), not as a quantity to maximise.

**Maximising acceptance rate.**

If every document is perfectly valid, only the code that handles correct
input is ever tested. Bugs hide in error handling - the parts that deal
with broken, weird, almost-right input. That is why the target was a band
rather than a maximum, even before I learned the metric's limits.