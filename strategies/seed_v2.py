from hypothesis import strategies as st


key_strat = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

leaf_int = st.integers(min_value=-2**63, max_value=2**63 - 1)
leaf_float = st.floats(
    min_value=-1e308,
    max_value=1e308,
    allow_nan=False,
    allow_infinity=False,
)
leaf_bool = st.booleans()
leaf_str = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S"),
        whitelist_characters='"\\"',
        min_codepoint=0x20,
        max_codepoint=0x10FFFF,
    ),
    min_size=0,
    max_size=20,
)

base = st.one_of(leaf_int, leaf_float, leaf_bool, leaf_str)

strategy = st.recursive(
    base,
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=2),
        st.dictionaries(key_strat, children, min_size=0, max_size=2),
    ),
    max_leaves=5000,
)