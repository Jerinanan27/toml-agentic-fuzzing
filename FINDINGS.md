# Findings

## Distinct bugs (both experiments, triaged by recursion cycle)


| Recursion cycle                                 | Defect class                     | Crash threshold (8 MB stack, clang-18) |
|-------------------------------------------------|----------------------------------|----------------------------------------|
| parse_array                                     | Deep arrays [[[...]]]            | 14,851                                 |
| parse_keyval                                    | Deep dotted keys a.a.a...        | 87,258                                 |
| parse_inline_table + parse_keyval               | Deep inline tables { k = {...} } | ~52,000                                |
| parse_array + parse_keyval                      | Mixed array/dotted               | (variant)                              |
| parse_array + parse_inline_table + parse_keyval | Fully mixed nesting              | (variant)                              |

All are unbounded-recursion stack overflows. Thresholds differ because
each recursion consumes a different stack-frame size per level.

## Crash counts

Experiment 1 (arrays + inline tables): 271 crashes
Experiment 2 (+ dotted keys): 278 crashes

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