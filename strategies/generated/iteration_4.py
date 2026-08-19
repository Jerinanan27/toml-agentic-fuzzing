from hypothesis import strategies as st

# Simple lowercase identifier keys for inline tables
key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Integer values, including extreme ranges
int_leaf = st.one_of(
    st.integers(min_value=-(10**200), max_value=-(10**100)),  # huge negative
    st.integers(min_value=10**100, max_value=10**200),       # huge positive
    st.integers(min_value=-(2**63), max_value=2**63 - 1),    # typical 64‑bit range
    st.integers(min_value=-5, max_value=5),                 # small numbers
)

# Float values, mixing normal floats with NaN / infinities (invalid in TOML)
float_leaf = st.one_of(
    st.floats(min_value=-1e308, max_value=1e308, allow_nan=False, allow_infinity=False),
    st.just(float('nan')),
    st.just(float('inf')),
    st.just(float('-inf')),
)

bool_leaf = st.booleans()

# Problematic strings that are likely to break simple serializers
problem_string = st.text(
    min_size=1,
    max_size=12,
    alphabet=st.sampled_from(
        ['"', '\\', '\n', '\r', '\t', '\b', '\0', '\u202e', '\uFFFD']
    ),
)

# Safe-ish strings
safe_string = st.text(
    min_size=0,
    max_size=12,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs", "Po", "Pc"),
        blacklist_characters=("\n", "\r", "\t", "\\"),  # keep simple safe strings
    ),
)

# Leaf values – overweight the problematic ones to lower acceptance rate
leaf = st.one_of(
    int_leaf, int_leaf, int_leaf,
    float_leaf, float_leaf,
    bool_leaf, bool_leaf,
    problem_string, problem_string, problem_string,
    safe_string,
)

# Recursive containers (arrays and inline tables) with small size limits
def _containers(child):
    return st.one_of(
        st.lists(child, min_size=0, max_size=3),
        st.dictionaries(key_strategy, child, min_size=0, max_size=3),
    )

shallow = st.recursive(
    leaf,
    _containers,
    max_leaves=20,
)

# Helper to build a very deep nested structure (alternating list / inline table)
def _deep_nest(base, depth):
    v = base
    for i in range(depth):
        if i % 2 == 0:
            v = [v]
        else:
            v = {"k": v}
    return v

# Deep structures with depth chosen by Hypothesis (100 – 200 000)
deep_structure = st.integers(min_value=100, max_value=200_000).flatmap(
    lambda d: leaf.map(lambda b: _deep_nest(b, d))
)

# Final mixed strategy
strategy = st.one_of(shallow, deep_structure)