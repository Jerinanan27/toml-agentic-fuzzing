from hypothesis import strategies as st, assume
import random

# --- Leaf Types ---

# Integers: including very large/small
int_leaf = st.integers(min_value=-(10**18), max_value=10**18)

# Floats: including 0.0, negatives, no nan/inf per TOML spec usually, 
# but we can allow standard float representations
float_leaf = st.floats(allow_nan=False, allow_infinity=False, width=64)

# Booleans
bool_leaf = st.booleans()

# Strings: Normal strings + malformed strings for error handling
# Malformed: unescaped quotes, bad escapes, unterminated quotes
normal_string = st.text(alphabet=st.characters(blacklist_categories=('Cc',), min_codepoint=32), min_size=0, max_size=50)

malformed_string_unescaped = st.text(min_size=1, max_size=10)
malformed_string_bad_escape = st.text(min_size=1, max_size=10)
malformed_string_unterminated = st.text(min_size=1, max_size=10)

# We want some malformed strings to be drawn
string_leaf = st.one_of(
    normal_string.map(lambda s: f'"{s}"'),
    malformed_string_unescaped.map(lambda s: f'"{s.replace(chr(34), "")} {chr(34)} test"'), # Try to inject quote
    malformed_string_bad_escape.map(lambda s: f'"{s}\\z"'), # Invalid escape \z
    malformed_string_unterminated.map(lambda s: f'"{s}') # Missing closing quote
)

# --- Deep Nesting Helpers ---

def _build_deep_list(depth):
    val = 1
    for _ in range(depth):
        val = [val]
    return val

def _build_deep_dict(depth):
    val = 1
    for _ in range(depth):
        val = {"k": val}
    return val

# Depth strategy: draw a large integer for depth
deep_list_strategy = (
    st.integers(min_value=50, max_value=200000)
    .map(_build_deep_list)
)

deep_dict_strategy = (
    st.integers(min_value=50, max_value=200000)
    .map(_build_deep_dict)
)

# Combined deep strategies
deep_value_strategy = st.one_of(deep_list_strategy, deep_dict_strategy)

# --- Dotted Keys ---

class DottedKey:
    def __init__(self, depth, value):
        self.depth = depth
        self.value = value
    
    def __repr__(self):
        # Construct the dotted key string
        # a.b.c.d = value
        keys = ".".join([f"k{i}" for i in range(self.depth)])
        # We need to serialize the value part eventually, but for the object itself:
        return f"DottedKey({self.depth}, {repr(self.value)})"

# Generate deep dotted keys
# D dotted key segments, wrapping a base value
deep_dotted_key_strategy = (
    st.integers(min_value=100, max_value=200000)
    .flatmap(lambda depth: 
        st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf, st.just([]))
        .map(lambda val: DottedKey(depth, val))
    )
)

# --- Recursive Shallow Strategy ---

key_simple = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Base leaves for recursion
base_leaves = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf)

# Recursive structure definition
# We limit the recursion size for the "normal" part to keep it shallow
recursive_value = st.recursive(
    base_leaves,
    lambda inner: st.one_of(
        st.lists(inner, min_size=0, max_size=5),
        st.dictionaries(key_simple, inner, min_size=0, max_size=5)
    ),
    max_leaves=100 # Keep shallow ones truly shallow
)

# --- Specific Edge Cases & Malformed Structures ---

# Empty containers
empty_list = st.just([])
empty_dict = st.just({})

# Duplicate keys in a dict (represented as a list of tuples for order, 
# though standard dict() merges. We need to signal this differently or 
# rely on string generation for malformed TOML. 
# Since the output type is Python dict, standard dicts can't have duplicate keys.
# However, the prompt says "dict -> becomes a TOML inline table".
# If we need to test duplicate key errors, we might need a special marker or
# rely on the string generation side. 
# Let's assume the tester handles Python dicts as valid tables.
# To generate malformed TOML via Python objects is tricky if the serializer
# is deterministic. 
# The previous rejection messages suggest the serializer handles the conversion.
# We can force malformed strings specifically.

# Very large integers
huge_int = st.integers(min_value=10**100, max_value=10**1000)

# --- Final Mix ---

# We want:
# 1. Shallow recursive values (normal cases)
# 2. Deeply nested lists/dicts (corner cases for stack overflow)
# 3. Deep dotted keys (corner cases for key parsing)
# 4. Explicit edge cases (empty, huge int, malformed strings)

strategy = st.one_of(
    recursive_value,                             # Shallow valid
    deep_value_strategy,                         # Deep valid (100k+ levels)
    deep_dotted_key_strategy,                    # Deep dotted keys (100k+ segs)
    empty_list,                                  # Edge: empty list
    empty_dict,                                  # Edge: empty dict
    huge_int,                                    # Edge: huge int
    string_leaf,                                 # Includes malformed strings
)