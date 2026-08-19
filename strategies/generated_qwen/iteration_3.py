from hypothesis import strategies as st

# DottedKey helper class as specified in the prompt
class DottedKey:
    def __init__(self, depth, value):
        self.depth = depth
        self.value = value

# --- Leaf Strategies ---

# Integers: very large and very small
int_leaf = st.integers(min_value=-(10**18), max_value=10**18)

# Floats: including 0.0, negatives, no nan/inf
float_leaf = st.floats(allow_nan=False, allow_infinity=False, width=64)

# Booleans
bool_leaf = st.booleans()

# Strings: including quotes, backslashes, unicode
# Using text with a broad alphabet to generate valid string content.
string_leaf = st.text(
    alphabet=st.characters(blacklist_categories=('Cc',), min_codepoint=32),
    min_size=0,
    max_size=100
)

# --- Deep Nesting Strategies ---
# Requirement: Draw D from 100-200000, use python loop to wrap value in D layers.

def _build_deep_list(depth, base_val=1):
    val = base_val
    for _ in range(depth):
        val = [val]
    return val

def _build_deep_dict(depth, base_val=1):
    val = base_val
    for _ in range(depth):
        val = {"k": val}
    return val

# Strategy for deeply nested lists
deep_list_strategy = (
    st.integers(min_value=100, max_value=200000)
    .map(lambda d: _build_deep_list(d))
)

# Strategy for deeply nested dicts
deep_dict_strategy = (
    st.integers(min_value=100, max_value=200000)
    .map(lambda d: _build_deep_dict(d))
)

# Combined deep container strategy
deep_container_strategy = st.one_of(deep_list_strategy, deep_dict_strategy)

# --- Dotted Key Strategies ---
# Requirement: DottedKey(D, base_value) where D is 100-200000

def _build_deep_dotted_key(depth, base_val):
    return DottedKey(depth, base_val)

# Generate a simple base value for the dotted key
simple_base_value = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf, st.just([]), st.just({}))

deep_dotted_key_strategy = (
    st.integers(min_value=100, max_value=200000)
    .flatmap(lambda d: simple_base_value.map(lambda v: _build_deep_dotted_key(d, v)))
)

# --- Shallow Recursive Strategy ---
# Requirements: st.recursive, dict keys are simple lowercase identifiers

key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

base_leaf = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf, st.just([]), st.just({}))

# Recursive structure: lists and dicts containing other values
recursive_leaf = st.recursive(
    base=base_leaf,
    extend=lambda inner: st.one_of(
        st.lists(inner, min_size=0, max_size=10),
        st.dictionaries(key_strategy, inner, min_size=0, max_size=10)
    ),
    max_leaves=50 # Keep this part relatively shallow to avoid infinite recursion issues in generation
)

# --- Final Mix ---
# Mix of shallow recursive values, deep containers, and deep dotted keys.
# Explicitly including edge cases like empty list/dict is handled by base_leaf/recursive_leaf,
# but we can ensure they are likely via st.just in the mix if needed, though recursive covers it.
# The prompt asks for "mostly varied shallow values" plus "meaningful share" of deep structures.

strategy = st.one_of(
    recursive_leaf,
    deep_container_strategy,
    deep_dotted_key_strategy
)