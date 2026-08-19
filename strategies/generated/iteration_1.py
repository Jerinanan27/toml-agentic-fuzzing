from hypothesis import strategies as st

# Simple identifier keys for inline tables
key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Leaf strategies with a bias toward malformed values
int_leaf = st.integers(min_value=-(10**100), max_value=10**100)
bool_leaf = st.booleans()

# Valid strings (mostly safe characters)
valid_string = st.text(
    min_size=0,
    max_size=20,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs", "Po", "Pc"),
        blacklist_characters=("\n", "\r", "\t", "\\"),  # avoid obvious escapes
    ),
)

# Malformed strings that are likely to break TOML parsing when serialized
bad_string = st.text(
    min_size=1,
    max_size=5,
    alphabet=st.sampled_from(['"', '\\', '\n', '\r', '\t', '\b']),
)

# Floats, including NaN and infinities to provoke errors
float_invalid = st.floats(allow_nan=True, allow_infinity=True)
float_valid = st.floats(min_value=-1e308, max_value=1e308, allow_nan=False, allow_infinity=False)

# Combine leaves, biasing toward the invalid/malformed variants
leaf = st.one_of(
    int_leaf,
    bool_leaf,
    valid_string,
    # bias: two invalid variants for each valid one
    bad_string,
    bad_string,
    float_invalid,
    float_invalid,
    float_valid,
)

# Recursive container definition (shallow varied structures)
def _containers(children):
    return st.one_of(
        st.lists(children, min_size=0, max_size=3),
        st.dictionaries(key_strategy, children, min_size=0, max_size=3),
    )

recursive_strategy = st.recursive(
    leaf,
    _containers,
    max_leaves=30,
)

# Helper to produce very deep nesting (alternating list/dict)
def _deep_nest(base, depth):
    v = base
    for i in range(depth):
        if i % 2 == 0:
            v = [v]
        else:
            v = {"k": v}
    return v

# Explicit deep‑nesting generator reaching >100 000 levels
deep_structure = st.integers(min_value=100, max_value=200_000).flatmap(
    lambda d: leaf.map(lambda b: _deep_nest(b, d))
)

# Final mixed strategy
strategy = st.one_of(recursive_strategy, deep_structure)