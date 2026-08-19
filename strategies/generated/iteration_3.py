from hypothesis import strategies as st

# Identifier keys for inline tables (lowercase, alphanumeric, underscores)
key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Integer leaf values – include extremely large/small numbers
int_leaf = st.one_of(
    st.integers(min_value=-(10**200), max_value=-(10**100)),  # huge negative
    st.integers(min_value=10**100, max_value=10**200),       # huge positive
    st.integers(min_value=-(2**63), max_value=2**63 - 1),    # typical 64‑bit range
)

# Float leaf values – heavy bias toward NaN / infinities (illegal in TOML)
float_leaf = st.one_of(
    st.just(float('nan')),
    st.just(float('inf')),
    st.just(float('-inf')),
    st.floats(min_value=-1e308, max_value=1e308, allow_nan=False, allow_infinity=False),
)

bool_leaf = st.booleans()

# Strings likely to cause parsing trouble
problem_string = st.text(
    min_size=1,
    max_size=12,
    alphabet=st.sampled_from(['"', '\\', '\n', '\r', '\t', '\b', '\0', '\u202e']),
)

safe_string = st.text(
    min_size=0,
    max_size=12,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs", "Po", "Pc"),
        blacklist_characters=("\n", "\r", "\t", "\\"),  # keep simple safe strings
    ),
)

# Heavier weighting toward problematic variants
leaf = st.one_of(
    int_leaf, int_leaf,
    float_leaf, float_leaf,
    bool_leaf,
    problem_string, problem_string, problem_string,
    safe_string,
)

# Recursive container definition (shallow varied structures)
def _containers(child):
    return st.one_of(
        st.lists(child, min_size=0, max_size=3),
        st.dictionaries(key_strategy, child, min_size=0, max_size=3),
    )

shallow = st.recursive(
    leaf,
    _containers,
    max_leaves=30,
)

# Helper to build a very deep nested structure
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
strategy = st.one_of(shallow, deep_structure)