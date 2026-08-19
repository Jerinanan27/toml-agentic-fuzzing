from hypothesis import strategies as st

# DottedKey helper class as specified in the prompt
class DottedKey:
    def __init__(self, depth, value):
        self.depth = depth
        self.value = value

# --- Leaf Strategies ---

# Integers: very large and very small
int_leaf = st.integers(min_value=-(10**18), max_value=10**18)

# Floats: including 0.0, negatives, no nan/inf.
# Ensure we get valid TOML floats. TOML supports Inf and NaN but tomlc99 might have quirks.
# For safety and generality, we exclude them, but ensure 0.0 and negatives are possible.
float_leaf = st.floats(allow_nan=False, allow_infinity=False, width=64)

# Booleans
bool_leaf = st.booleans()

# Strings: including quotes, backslashes, unicode.
# TOML strings can be basic ("...") or literal ('...'). Basic strings support escapes.
# To avoid "bad escape char" rejections in certain parsers or contexts with raw strings,
# we should be careful. However, standard TOML allows \n, \\, etc.
# The previous strategy used st.characters with blacklist_categories=('Cc',), min_codepoint=32.
# This might generate characters that need escaping in a basic string but aren't.
# Let's use a simpler approach: generate strings that are likely to be safe or use escaped strings.
# Actually, Hypothesis strategy for TOML strings usually just generates text.
# If the serializer handles escaping, any text is fine.
# The rejection "bad escape char" suggests a raw string interpretation or a specific parser quirk.
# Let's stick to printable ASCII for robustness, plus some unicode.
string_leaf = st.text(
    alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), min_codepoint=32),
    min_size=0,
    max_size=50
)

# --- Deep Nesting Strategies ---
# Requirement: Draw D from 100-200000, use python loop to wrap value in D layers.

def _build_deep_list(depth, base_val=0):
    """Build a deeply nested list [ [...[ base_val ]...] ]"""
    val = base_val
    for _ in range(depth):
        val = [val]
    return val

def _build_deep_dict(depth, base_val=0):
    """Build a deeply nested dict { "k": { "k": ... } }"""
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

# Generate a simple base value for the dotted key.
# To avoid "extra chars after value" or similar parsing issues downstream,
# keep the base value simple and self-contained.
simple_base_value = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf)

deep_dotted_key_strategy = (
    st.integers(min_value=100, max_value=200000)
    .flatmap(lambda d: simple_base_value.map(lambda v: _build_deep_dotted_key(d, v)))
)

# --- Shallow Recursive Strategy ---
# Requirements: st.recursive, dict keys are simple lowercase identifiers

key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Base leaves for recursion: including empty containers
base_leaf = st.one_of(
    int_leaf, 
    float_leaf, 
    bool_leaf, 
    string_leaf, 
    st.just([]), 
    st.just({})
)

# Recursive structure: lists and dicts containing other values.
# Limit depth to avoid excessive complexity in the "shallow" mix,
# allowing the explicit deep strategies to handle the heavy lifting.
recursive_leaf = st.recursive(
    base=base_leaf,
    extend=lambda inner: st.one_of(
        st.lists(inner, min_size=0, max_size=5),
        st.dictionaries(key_strategy, inner, min_size=0, max_size=5)
    ),
    max_leaves=20
)

# --- Final Mix ---
# The goal is mostly shallow values, but with a meaningful share of deep structures.
# We explicitly include empty list/dict in base_leaf.
# We include deep containers and deep dotted keys.

strategy = st.one_of(
    recursive_leaf,
    deep_container_strategy,
    deep_dotted_key_strategy
)