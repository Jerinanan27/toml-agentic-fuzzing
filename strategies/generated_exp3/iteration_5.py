import random
import hypothesis.strategies as st
from hypothesis import given

# Assume node classes are imported from the target module
# from toml_ast import (
#     Document, Comment, KeyValue, TableHeader, ArrayTableHeader,
#     QuotedKey, DottedKey, RawValue,
# )

# ----- Raw token strategies (mostly valid) -----
valid_int = st.integers(min_value=-2**63, max_value=2**63 - 1).map(
    lambda i: RawValue(str(i), "DEC_INT")
)

valid_float = st.floats(allow_nan=False, allow_infinity=False).map(
    lambda f: RawValue(repr(f), "FLOAT")
)

valid_bool = st.sampled_from([
    RawValue("true", "BOOLEAN"),
    RawValue("false", "BOOLEAN"),
])

valid_string = st.one_of(
    st.just(RawValue(r'"simple"', "BASIC_STRING")),
    st.just(RawValue(r"'literal'", "LITERAL_STRING")),
    st.just(RawValue('"""multi\\nline"""', "ML_BASIC_STRING")),
    st.just(RawValue("'''multi\\nline'''", "ML_LITERAL_STRING")),
)

valid_datetime = st.sampled_from([
    RawValue("1979-05-27T07:32:00Z", "OFFSET_DATE_TIME"),
    RawValue("1979-05-27T07:32:00", "LOCAL_DATE_TIME"),
    RawValue("1979-05-27", "LOCAL_DATE"),
    RawValue("07:32:00.999", "LOCAL_TIME"),
])

raw_valid = st.one_of(
    valid_int,
    valid_float,
    valid_bool,
    valid_string,
    valid_datetime,
)

# ----- Container strategies (shallow) -----
array_shallow = st.recursive(
    st.just([]),
    lambda children: st.lists(children, max_size=3),
    max_leaves=10,
)

inline_table_shallow = st.recursive(
    st.just({}),
    lambda children: st.dictionaries(
        st.text(
            min_size=1,
            max_size=5,
            alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                whitelist_characters='_-',
            ),
        ),
        children,
        max_size=3,
    ),
    max_leaves=10,
)

# ----- Deep nesting helpers (loop‑based, no recursion) -----
def build_deep_array(depth: int):
    elem = RawValue("0", "DEC_INT")
    for _ in range(depth):
        elem = [elem]
    return elem

def build_deep_inline_table(depth: int):
    inner = {}
    for _ in range(depth):
        inner = {"k": inner}
    return inner

deep_array = st.integers(min_value=15000, max_value=20000).map(build_deep_array)
deep_inline_table = st.integers(min_value=15000, max_value=20000).map(build_deep_inline_table)

# ----- Value strategy (biased toward valid, with occasional deep nesting) -----
value_strategy = st.one_of(
    raw_valid,
    array_shallow,
    inline_table_shallow,
    deep_array,
    deep_inline_table,
)

# ----- Key strategies -----
simple_key = st.text(
    min_size=1,
    max_size=10,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='_-',
        blacklist_characters='\x00',
    ),
)

quoted_key = st.builds(
    QuotedKey,
    st.text(min_size=1, max_size=10, alphabet=st.characters(blacklist_characters='\x00')),
    st.booleans(),
)

dotted_key = st.lists(simple_key, min_size=2, max_size=4, unique=True).map(
    lambda parts: DottedKey(len(parts), parts)
)

key_strategy = st.one_of(
    simple_key,
    quoted_key,
    dotted_key,
)

# ----- Comment strategy -----
comment_strategy = st.text(min_size=0, max_size=30, alphabet=st.characters(blacklist_characters='\x00'))

# ----- Composite document strategy -----
@st.composite
def document_strategy(draw):
    stmt_count = draw(st.integers(min_value=5, max_value=12))

    # decide how many of each statement type
    num_comments = draw(st.integers(min_value=0, max_value=stmt_count))
    remaining = stmt_count - num_comments

    num_tables = draw(st.integers(min_value=0, max_value=remaining))
    remaining -= num_tables

    num_array_tables = draw(st.integers(min_value=0, max_value=remaining))
    remaining -= num_array_tables

    num_keyvalues = remaining

    # Generate distinct simple keys for tables to avoid duplicates
    table_keys = draw(
        st.lists(simple_key, min_size=num_tables, max_size=num_tables, unique=True)
    )
    array_table_keys = draw(
        st.lists(simple_key, min_size=num_array_tables, max_size=num_array_tables, unique=True)
    )

    # Generate keys for key‑values (allow any key type, but ensure uniqueness of string representation)
    kv_keys_raw = draw(
        st.lists(simple_key, min_size=num_keyvalues, max_size=num_keyvalues, unique=True)
    )
    kv_keys = []
    for k in kv_keys_raw:
        # randomly decide to wrap into quoted or dotted form
        form = draw(st.integers(min_value=0, max_value=2))
        if form == 0:
            kv_keys.append(k)                     # simple string
        elif form == 1:
            kv_keys.append(QuotedKey(k, draw(st.booleans())))
        else:
            # dotted key needs at least two parts; prepend another simple part
            extra = draw(simple_key)
            parts = [extra, k]
            kv_keys.append(DottedKey(len(parts), parts))

    statements = []

    # Comments
    for _ in range(num_comments):
        txt = draw(comment_strategy)
        statements.append(Comment(txt))

    # Key‑value pairs
    if num_keyvalues > 0:
        # Ensure at least one boolean value to hit bool_ production
        bool_val = draw(valid_bool)
        statements.append(KeyValue(kv_keys[0], bool_val))
        for key in kv_keys[1:]:
            val = draw(value_strategy)
            statements.append(KeyValue(key, val))

    # Table headers
    for k in table_keys:
        statements.append(TableHeader([k]))

    # Array‑table headers
    for k in array_table_keys:
        statements.append(ArrayTableHeader([k]))

    random.shuffle(statements)
    return Document(statements)

strategy = document_strategy()