from hypothesis import strategies as st

# ---------- Leaf values ----------
int_leaf = st.integers(min_value=-(10**100), max_value=10**100)

float_leaf = st.one_of(
    st.just(0.0),
    st.floats(min_value=-1e308, max_value=1e308,
              allow_nan=False, allow_infinity=False)
)

bool_leaf = st.booleans()

# strings that are likely to cause parse errors
good_string = st.text(min_size=0, max_size=20)

# include unescaped quotes, backslashes, control chars, high Unicode, etc.
bad_string = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(
        min_codepoint=0,
        max_codepoint=0x10FFFF,
        blacklist_characters=''  # allow everything, including quotes and backslashes
    )
)

string_leaf = st.one_of(good_string, bad_string, bad_string, bad_string)

leaf = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf)

# ---------- Keys ----------
key_strategy = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# ---------- Recursive containers ----------
def _containers(children):
    return st.one_of(
        st.lists(children, min_size=0, max_size=2),
        st.dictionaries(key_strategy, children, min_size=0, max_size=2)
    )

recursive_strategy = st.recursive(
    leaf,
    _containers,
    max_leaves=2000,
)

# ---------- Deep nesting helpers ----------
def _wrap_lists(value, depth: int):
    for _ in range(depth):
        value = [value]
    return value

def _wrap_dicts(value, depth: int):
    for _ in range(depth):
        value = {"k": value}
    return value

deep_list = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: _wrap_lists(b, d))
)

deep_dict = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: _wrap_dicts(b, d))
)

# ---------- DottedKey ----------
deep_dotted = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: DottedKey(d, b))
)

# ---------- Final mixed strategy ----------
strategy = st.one_of(
    recursive_strategy,
    deep_list,
    deep_dict,
    deep_dotted,
)