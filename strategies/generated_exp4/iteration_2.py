import hypothesis.strategies as st

# ----- Raw token strategies (valid only) -----
valid_int = st.one_of(
    st.just(st.just(RawValue("0", "DEC_INT"))),
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

valid_raw_value = st.one_of(
    valid_int,
    valid_float,
    valid_bool,
    valid_string,
    valid_datetime,
)

# ----- Shallow container strategies (valid only) -----
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
                whitelist_categories=('Lu','Ll','Nd'),
                whitelist_characters='_-'
            )
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

# ----- Value strategy groups -----
shallow_value = st.one_of(valid_raw_value, array_shallow, inline_table_shallow)

# ----- Key generators with uniqueness -----
def unique_simple_key(idx):
    return f"s{idx}"

def unique_quoted_key(idx, is_literal):
    return QuotedKey(f"q{idx}", is_literal)

def unique_dotted_key(idx):
    parts = [f"d{idx}_p{i}" for i in range(2, 5)]  # 2‑4 parts
    return DottedKey(len(parts), parts)

# ----- Composite Document strategy -----
@st.composite
def document_strategy(draw):
    num_stmts = draw(st.integers(min_value=5, max_value=15))
    # reserve positions for deep value and a boolean value
    deep_pos = draw(st.integers(min_value=0, max_value=num_stmts - 1))
    bool_pos = draw(st.integers(min_value=0, max_value=num_stmts - 1))
    if num_stmts > 1:
        while bool_pos == deep_pos:
            bool_pos = draw(st.integers(min_value=0, max_value=num_stmts - 1))

    used_keys = set()
    statements = []
    key_counter = 0

    for idx in range(num_stmts):
        if idx == deep_pos:
            deep_val = draw(st.one_of(deep_array, deep_inline_table))
            key = unique_simple_key(key_counter)
            key_counter += 1
            statements.append(KeyValue(key, deep_val))
            used_keys.add(key)
        elif idx == bool_pos:
            bool_val = draw(valid_bool)
            key = unique_simple_key(key_counter)
            key_counter += 1
            statements.append(KeyValue(key, bool_val))
            used_keys.add(key)
        else:
            stmt_type = draw(st.sampled_from(['kv', 'comment', 'table', 'array_table']))
            if stmt_type == 'kv':
                # pick a key kind, ensuring uniqueness
                key_kind = draw(st.sampled_from(['simple', 'quoted', 'dotted']))
                if key_kind == 'simple':
                    key = unique_simple_key(key_counter)
                    key_counter += 1
                elif key_kind == 'quoted':
                    is_lit = draw(st.booleans())
                    key = unique_quoted_key(key_counter, is_lit)
                    key_counter += 1
                else:  # dotted
                    key = unique_dotted_key(key_counter)
                    key_counter += 1
                # ensure textual representation not duplicate (best‑effort)
                # store a string form for duplicate avoidance
                key_repr = str(key)  # assumes __str__ gives a comparable form
                if key_repr in used_keys:
                    # skip this stmt, generate a simple fresh key instead
                    key = unique_simple_key(key_counter)
                    key_counter += 1
                    key_repr = key
                used_keys.add(key_repr)

                val = draw(shallow_value)
                statements.append(KeyValue(key, val))
            elif stmt_type == 'comment':
                comment_text = draw(
                    st.text(
                        min_size=0,
                        max_size=20,
                        alphabet=st.characters(
                            blacklist_characters='\0',
                            max_codepoint=0x10FFFF
                        )
                    )
                )
                statements.append(Comment(comment_text))
            elif stmt_type == 'table':
                header_keys = draw(
                    st.lists(
                        st.text(
                            min_size=1,
                            max_size=5,
                            alphabet=st.characters(
                                whitelist_categories=('Lu','Ll','Nd'),
                                whitelist_characters='_-'
                            )
                        ),
                        min_size=1,
                        max_size=3,
                        unique=True
                    )
                )
                statements.append(TableHeader(header_keys))
            else:  # array_table
                header_keys = draw(
                    st.lists(
                        st.text(
                            min_size=1,
                            max_size=5,
                            alphabet=st.characters(
                                whitelist_categories=('Lu','Ll','Nd'),
                                whitelist_characters='_-'
                            )
                        ),
                        min_size=1,
                        max_size=3,
                        unique=True
                    )
                )
                statements.append(ArrayTableHeader(header_keys))

    return Document(statements)

strategy = document_strategy()