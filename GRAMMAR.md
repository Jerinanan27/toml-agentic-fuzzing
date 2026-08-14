#TOML -> Tom's Obvious, Minimal Language, . It is a human-readable configuration file format created by Tom Preston-Werner (co-founder of GitHub) as a simpler, easier-to-parse alternative to formats like JSON, INI, and YAML.

#TOML Grammar and the tomlc99 Gap

## Source of the Grammar 
The formal grammar comes from the ANTLR grammars-v4 repository:
https://github.com/antlr/grammars-v4/tree/master/toml

TOML ships as two files there: TomlLexer.g4 and TomlParser.g4

The official TOML specification is at https://toml.io/en/v1.0.0

## Part 1- The rules, in plain wors

A TOML file is a list of settings. Each setting is:
    key ="value"

Values must have one of the following types:
-String
-Integer
-Float
-Boolean
-Offset Date-Time
-Local Date-Time
-Local Date
-Local Time
-Array
-Inline Table

Values can be:
-Text, in quotes    : name="server"
-Numbers, no quotes : port=8080
-True/False         : enabled=true
-Lists, in[]        : number =[1,2,3]

Square brackets [] do two different jobs, told apart by position:
-On their own line  : [server] -> a section header (groups settings like struct in C)
- After an = sign   : [1,2,3] -> a list of values

## The recursive part (this is where the bugs live)
A list can contain another list:
    data= [[1,2],[3,4]]
And that can go deeper, with no limit in the grammar:
    data= [[[[[[[[[[[........]]]]]]]]]]]
A rule that can contain itself is called RECURSIVE.
Deep recursion is what overflows the parser's stack and crashes it.

## Spec
-TOML is case-sensitive.
-A TOML file must be a valid UTF-8 encoded Unicode document.
-Whitespace means tab (0x09) or space (0x20).
-Newline means LF (0x0A) or CRLF (0x0D 0x0A).

## Part 2 — The gap (spec vs. library), tested by hand

| Feature                 | Spec allows it? | tomlc99 accepts it? | Gap? |
|-------------------------|-----------------|---------------------|--------|
| Hex numbers (0xFF)      | Yes             | Yes (exit 0)        | No gap |
| Inline tables { x = 1 } | Yes             | Yes (exit 0)        | No gap |
| Empty inline table {}   | Yes             | Yes (exit 0)        | No gap |

## Crash behaviour: nesting depth

| Input                            | Depth   | Result                |
|----------------------------------|---------|-----------------------|
| Deep arrays [[[...]]]            | 100,000 | CRASH: stack-overflow |
| Deep inline tables { b = {...} } | 50,000  | No crash              |
| Deep inline tables { b = {...} } | 100,000 | CRASH: stack-overflow |
| Deep dotted keys (a.b.b.b... × 100,000)    | CRASH: stack-overflow in parse_keyval (line 1138) |

## Two distinct bugs found

Bug 1 — deep arrays:
- Trigger: arrays nested 100,000 deep
- Stack trace: parse_array calling itself repeatedly
- One function calling itself = simple / direct recursion

Bug 2 — deep inline tables:
- Trigger: inline tables nested 100,000 deep  
- Stack trace: parse_keyval and parse_inline_table calling each other
- Two functions calling each other = mutual recursion
- Needs more depth than Bug 1 to crash (still going at 50,000)

Bug 3 — deep dotted keys:
- Trigger: a.b.b.b... repeated 100,000 times
- Stack trace: parse_keyval calling itself (line 1138)
- Direct recursion, same function as Bug 1 but different code path
  (Bug 1 crashes at line 1060, Bug 3 at line 1138)
  
These produce different stack traces and are treated as two separate bugs.