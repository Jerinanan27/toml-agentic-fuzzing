from hypothesis import strategies as st

# Leaf values --------------------------------------------------------------
int_leaf = st.integers(min_value=-(10 ** 20), max_value=10 ** 20)
float_leaf = st.floats(allow_nan=False, allow_infinity=False)
bool_leaf = st.booleans()
string_leaf = st.text(min_size=0, max_size=20, alphabet=st.characters())

leaf = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf)

# Dictionary keys: simple lowercase identifiers ---------------------------
key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# Recursive containers (arrays & inline tables) ---------------------------
recursive_containers = lambda children: st.one_of(
    st.lists(children, min_size=0, max_size=2),
    st.dictionaries(key_strategy, children, min_size=0, max_size=2),
)

recursive_strategy = st.recursive(
    leaf,
    recursive_containers,
    max_leaves=5000,
)

# Explicit deep‑nesting generator -----------------------------------------
def _nest(value, wrappers):
    for w in wrappers:
        if w == "list":
            value = [value]
        else:  # dict
            value = {"k": value}
    return value


deep_structure = st.integers(min_value=50, max_value=5000).flatmap(
    lambda depth: st.lists(st.sampled_from(["list", "dict"]), min_size=depth, max_size=depth).flatmap(
        lambda wrappers: leaf.map(lambda base: _nest(base, wrappers))
    )
)

# Final mixed strategy ------------------------------------------------------
strategy = st.one_of(recursive_strategy, deep_structure)
