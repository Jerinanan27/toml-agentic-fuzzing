from hypothesis import strategies as st

# ---------- Leaf values ----------
int_leaf = st.integers(min_value=-(10**102), max_value=10**102)

float_leaf = st.one_of(
    st.just(0.0),
    st.floats(min_value=-1e308, max_value=1e308,
              allow_nan=False, allow_infinity=False)
)

bool_leaf = st.booleans()

# well‑formed strings
good_string = st.text(min_size=0, max_size=20)

# deliberately problematic strings (control chars, unescaped quotes, backslashes, etc.)
bad_string = st.text(
    alphabet=st.characters(
        min_codepoint=0,
        max_codepoint=0x10FFFF,
        blacklist_characters=''  # allow everything
    ),
    min_size=1,
    max_size=20
)

string_leaf = st.one_of(good_string, bad_string, bad_string, bad_string)

leaf = st.one_of(int_leaf, float_leaf, bool_leaf, string_leaf)

# ---------- Keys ----------
good_key = st.from_regex(r"[a-z][a-z0-9_]*", fullmatch=True)

# keys that violate the spec: empty, contain dots, uppercase, spaces, etc.
bad_key = st.one_of(
    st.just(""),
    st.from_regex(r"[A-Z][a-z0-9_]*", fullmatch=True),
    st.from_regex(r".*\..*", fullmatch=True),
    st.text(min_size=1, max_size=5).filter(lambda s: not s.isidentifier() or s[0].isdigit())
)

# ---------- Recursive containers ----------
def _containers(children):
    # well‑formed containers
    good = st.one_of(
        st.lists(children, min_size=0, max_size=2),
        st.dictionaries(good_key, children, min_size=0, max_size=2)
    )
    # malformed dicts (bad keys) – these will be rejected by a strict parser
    malformed = st.dictionaries(bad_key, children, min_size=1, max_size=2)
    return st.one_of(good, malformed)

recursive_strategy = st.recursive(
    leaf,
    _containers,
    max_leaves=1500,
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

def _wrap_bad_dicts(value, depth: int):
    # use a bad key at the outermost level to provoke a rejection
    for i in range(depth):
        key = "" if i == depth - 1 else "k"
        value = {key: value}
    return value

deep_list = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: _wrap_lists(b, d))
)

deep_dict = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: _wrap_dicts(b, d))
)

deep_bad_dict = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: _wrap_bad_dicts(b, d))
)

# ---------- DottedKey ----------
# Assume DottedKey is defined elsewhere and accepts (depth, value)
deep_dotted = st.integers(min_value=100, max_value=200000).flatmap(
    lambda d: leaf.map(lambda b: DottedKey(d, b))
)

# ---------- Final mixed strategy ----------
strategy = st.one_of(
    recursive_strategy,
    deep_list,
    deep_dict,
    deep_bad_dict,
    deep_dotted,
)