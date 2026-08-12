from hypothesis import strategies as st

# The dumb fuzzer: just random text and random bytes.
# No knowledge of TOML at all. This is on purpose.
baseline = st.one_of(
    st.text(),
    st.binary(),
)