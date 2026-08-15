# The Proxy Signal

## Why a Proxy Signal is needed

Normally a fuzzer is judged by code coverage- which lines of the target program its inputs reached. This assignment is blackbox: I can not see inside the parser. I can only observe what leaks out (exit code, error message, run time).

So I need a sustitute measurement, taken from outside, that stands in for "am I testing more of this parser?" That substitute is the proxy signal, and choosing it is the core design decision of the loop.

## The four components I chose

### 1. Acceptance Rate
What fraction of generated files the parser accepts.

Why: If the acceptance rate is very low then the random files weren't high quality enough to enter the parser. If almost none go past the door then nothing gets tested.

### 2. Nesting Depth
Maximum and average depth of the generated structure.

Why: The three bugs I found are all recursion bugs, triggered by very deep nesting. Inline tables at 50,000 deep did not crash; at 100,000 they did. So if the generator does not go deep enough, these bugs are unreachable. My baseline run had an average depth of 1.6, which is far too shallow.

### 3. Type Coverage
How many distinct node type appear (array, string, integer, bool, .....)

Why: If the generator only makes one kind of node, it explores one corner of TOML and will only ever find bugs in that corner. My three known bugs came from three different features (arrays, inline tables, dotted keys), which suggests bugs are spread across features rather than concentrated in one.

### 4. Rejection Message Diversity
How many distinct error message the parser produces.

Why: If all rejections carry the same message, the generator is stuck producing one shape of broken file - it has converged and stopped exploring. Many distinct messages mean the generator is reaching many different parts of the parser's error-handling code. Since I cannot see the parser's code, these messages are the parser describing itself from the inside - the closest thing to coverage I can observe from outside.


## The Objective
Reach at least 6 distinct node types, then maximize nesting depth, while keeping acceptance rate between 30% and 70%.

Why this odering: If the depth comes first then the AI will chase depth. It might make 500 files that are all deep nested arrays- and never touch any other types like dates, strings or dotted keys. 

## What I rejected, and why

**Number of crashes as the signal.** 
Crash count is 0 most of the time, so it gives the AI no direction to improve. It would be like telling the AI 'you failed' five times with no guidance about which direction to move.

From my baseline run:

```
ACCEPTED        4
HARNESS_ERROR   6
REJECTED      490
CRASH           0
```

**Maximising acceptance rate.**
If every file is perfectly valid and the acceptance rate is 100% then the code that only handles correct inputs is being tested every time. Bugs often hide in the error-handling code. The parts that deal with broken, weird, almost-right input. If broken input is never being sent then the code never runs and it is never been tested.