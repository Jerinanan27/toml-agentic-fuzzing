import hypothesis.strategies as st
from hypothesis import given, settings, HealthCheck

# ----- Raw token strategies (valid) -----
valid_int = st.one_of(
    st.just(RawValue("0", "DEC_INT")),
    st.just(RawValue("-9223372036854775808", "DEC_INT")),  # int64 min
    st.just(RawValue("9223372036854775807", "DEC_INT")),   # int64 max
    st.integers(min_value=-2**63, max_value=2**63 - 1).map(
        lambda i: RawValue(str(i), "DEC_INT")
    ),
    st.just(RawValue("0xDEAD_BEEF", "HEX_INT")),
    st.just(RawValue("0o755", "OCT_INT")),
    st.just(RawValue("0b1101_0110", "BIN_INT")),
)

valid_float = st.one_of(
    st.just(RawValue("0.0", "FLOAT")),
    st.just(RawValue("-1.23e+45", "FLOAT")),
    st.just(RawValue("inf", "INF")),
    st.just(RawValue("+inf", "INF")),
    st.just(RawValue("-inf", "INF")),
    st.just(RawValue("nan", "NAN")),
    st.just(RawValue("+nan", "NAN")),
    st.just(RawValue("-nan", "NAN")),
    st.floats(allow_nan=False, allow_infinity=False).map(
        lambda f: RawValue(repr(f), "FLOAT")
    ),
)

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

# ----- Shallow container strategies -----
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

# ----- Deep nesting generators (iterative) -----
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

# ----- Value strategies -----
shallow_value = st.one_of(
    # bias heavily toward valid scalars, especially booleans
    valid_bool,
    raw_valid,
    raw_valid,
    array_shallow,
    inline_table_shallow,
)

deep_value = st.one_of(deep_array, deep_inline_table)

# ----- Key strategies -----
bare_key_char = st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    whitelist_characters='_-',
)

simple_key = st.text(min_size=1, max_size=10, alphabet=bare_key_char)

quoted_key = st.builds(
    QuotedKey,
    st.text(min_size=1, max_size=10, alphabet=bare_key_char),
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

# ----- Statement strategies -----
comment_stmt = st.builds(Comment, st.text(min_size=0, max_size=20))

table_header_stmt = st.builds(
    TableHeader,
    st.lists(simple_key, min_size=1, max_size=3)
)

array_table_header_stmt = st.builds(
    ArrayTableHeader,
    st.lists(simple_key, min_size=1, max_size=3)
)

keyvalue_shallow = st.builds(
    KeyValue,
    key_strategy,
    shallow_value,
)

keyvalue_deep = st.builds(
    KeyValue,
    key_strategy,
    deep_value,
)

normal_statement = st.one_of(
    keyvalue_shallow,
    table_header_stmt,
    array_table_header_stmt,
    comment_stmt,
)

# ----- Document strategy with guaranteed deep statement -----
@st.composite
def document_strategy(draw):
    stmt_count = draw(st.integers(min_value=5, max_value=15))
    deep_idx = draw(st.integers(min_value=0, max_value=stmt_count - 1))
    statements = []
    for i in range(stmt_count):
        if i == deep_idx:
            stmt = draw(keyvalue_deep)
        else:
            stmt = draw(normal_statement)
        statements.append(stmt)
    return Document(statements)

strategy = document_strategy()