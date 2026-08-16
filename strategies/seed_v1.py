from hypothesis import strategies as st

leaf = st.one_of(
    st.integers(min_value=-(2**62), max_value=2**62),          # very large/small ints
    st.floats(min_value=-1e200, max_value=1e200,
              allow_nan=False, allow_infinity=False),       # floats including 0.0, negatives
    st.booleans(),
    st.text(min_size=0, max_size=30)                         # strings with quotes, backslashes, unicode
)

strategy = st.recursive(
    leaf,
    lambda children: st.lists(children, min_size=0, max_size=5),
    max_leaves=200
)