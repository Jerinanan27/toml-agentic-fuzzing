import random
import hypothesis.strategies as st
from hypothesis import given

# Assuming the node classes are imported from the target module:
# from toml_ast import Document, Comment, KeyValue, TableHeader, ArrayTableHeader, QuotedKey, DottedKey, RawValue

# ----- Raw token strategies (mostly valid, fewer malformed) -----
valid_int = st.one_of(
    st.just(RawValue("0", "DEC_INT")),
    st.just(RawValue("-9223372036854775808", "DEC_INT")),
    st.just(RawValue("9223372036854775807", "DEC_INT")),
    st.integers(min_value=-2**63, max_value=2**63 - 1).map(lambda i: RawValue(str(i), "DEC_INT")),
    st.just(RawValue("0xDEAD_BEEF", "HEX_INT")),
    st.just(RawValue("0o755", "OCT_INT")),
    st.just(RawValue("0b1101_0110", "BIN_INT")),
)

malformed_int = st.sampled_from([
    RawValue("123_", "DEC_INT"),
    RawValue("-0_", "DEC_INT"),
    RawValue("0xGHI", "HEX_INT"),
    RawValue("0b102", "BIN_INT"),
])

valid_float = st.one_of(
    st.just(RawValue("0.0", "FLOAT")),
    st.just(RawValue("-1.23e+45", "FLOAT")),
    st.just(RawValue("inf", "INF")),
    st.just(RawValue("+inf", "INF")),
    st.just(RawValue("-inf", "INF")),
    st.just(RawValue("nan", "NAN")),
    st.just(RawValue("+nan", "NAN")),
    st.just(RawValue("-nan", "NAN")),
    st.floats(allow_nan=False, allow_infinity=False).map(lambda f: RawValue(repr(f), "FLOAT")),
)

malformed_float = st.sampled_from([
    RawValue("1.2.3", "FLOAT"),
    RawValue("e10", "FLOAT"),
    RawValue("1e", "FLOAT"),
])

valid_bool = st.sampled_from([
    RawValue("true", "BOOLEAN"),
    RawValue("false", "BOOLEAN"),
])

valid_string = st.one_of(
    st.just(RawValue(r'"simple"', "BASIC_STRING")),
    st.just(RawValue(r'"esc: \n \t \" \\ \u00E9 \U0001F600"', "BASIC_STRING")),
    st.just(RawValue(r"'literal'", "LITERAL_STRING")),
    st.just(RawValue('"""multi\nline"""', "ML_BASIC_STRING")),
    st.just(RawValue("'''multi\nline'''", "ML_LITERAL_STRING")),
)

malformed_string = st.sampled_from([
    RawValue(r'"unterminated', "BASIC_STRING"),
    RawValue(r'"bad\escape"', "BASIC_STRING"),
    RawValue(r"'unterminated", "LITERAL_STRING"),
    RawValue('"""unclosed multiline', "ML_BASIC_STRING"),
])

valid_datetime = st.sampled_from([
    RawValue("1979-05-27T07:32:00Z", "OFFSET_DATE_TIME"),
    RawValue("1979-05-27T07:32:00", "LOCAL_DATE_TIME"),
    RawValue("1979-05-27", "LOCAL_DATE"),
    RawValue("07:32:00.999", "LOCAL_TIME"),
])

malformed_datetime = st.sampled_from([
    RawValue("1979-13-27T07:32:00Z", "OFFSET_DATE_TIME"),
    RawValue("1979-05-32", "LOCAL_DATE"),
    RawValue("24:01:00", "LOCAL_TIME"),
])

raw_valid = st.one_of(
    valid_int,
    valid_float,
    valid_bool,
    valid_string,
    valid_datetime,
)

raw_mixed = st.one_of(
    raw_valid,
    malformed_int,
    malformed_float,
    malformed_string,
    malformed_datetime,
)

# ----- Container strategies -----
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

def build_deep_array(depth: int):
    element = RawValue("0", "DEC_INT")
    for _ in range(depth):
        element = [element]
    return element

def build_deep_inline_table(depth: int):
    inner = {}
    for _ in range(depth):
        inner = {"k": inner}
    return inner

deep_array = st.integers(min_value=100_000, max_value=110_000).map(build_deep_array)
deep_inline_table = st.integers(min_value=100_000, max_value=110_000).map(build_deep_inline_table)

# ----- Value strategy (biased toward valid) -----
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
    ),
)

quoted_key = st.builds(
    QuotedKey,
    st.text(min_size=1, max_size=10),
    st.booleans(),
)

dotted_key = st.lists(simple_key, min_size=2, max_size=5).map(
    lambda parts: DottedKey(len(parts), parts)
)

key_strategy = st.one_of(
    simple_key,
    quoted_key,
    dotted_key,
)

# ----- Composite document strategy -----
@st.composite
def document_strategy(draw):
    total_stmt = draw(st.integers(min_value=5, max_value=15))

    # Allocate counts for each statement type
    num_comments = draw(st.integers(min_value=0, max_value=total_stmt))
    remaining = total_stmt - num_comments

    num_tables = draw(st.integers(min_value=0, max_value=remaining))
    remaining -= num_tables

    num_array_tables = draw(st.integers(min_value=0, max_value=remaining))
    remaining -= num_array_tables

    num_keyvalues = remaining

    # Unique simple keys for tables and key‑values to avoid duplicates
    kv_keys = draw(
        st.lists(simple_key, min_size=num_keyvalues, max_size=num_keyvalues, unique=True)
    )
    table_keys = draw(
        st.lists(simple_key, min_size=num_tables, max_size=num_tables, unique=True)
    )
    array_table_keys = draw(
        st.lists(simple_key, min_size=num_array_tables, max_size=num_array_tables, unique=True)
    )

    statements = []

    # Comments
    for _ in range(num_comments):
        comment_text = draw(st.text(min_size=0, max_size=20))
        statements.append(Comment(comment_text))

    # Key‑value pairs – guarantee at least one boolean value if any KV exists
    kv_values = []
    if num_keyvalues > 0:
        kv_values.append(draw(valid_bool))
        for _ in range(num_keyvalues - 1):
            kv_values.append(draw(value_strategy))
    for k, v in zip(kv_keys, kv_values):
        statements.append(KeyValue(k, v))

    # Table headers
    for k in table_keys:
        statements.append(TableHeader([k]))

    # Array‑table headers
    for k in array_table_keys:
        statements.append(ArrayTableHeader([k]))

    # Shuffle while preserving type constraints
    random.shuffle(statements)
    return Document(statements)

strategy = document_strategy()