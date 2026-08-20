import sys

# Deep structures are the point of this project, so allow deep recursion
# in serialize(). depth() and node_types() are iterative and unaffected.
sys.setrecursionlimit(100000)

class DottedKey:
    """Represents a dotted key like a.b.c.d = value.
    depth = number of key segments; value = the assigned value."""
    def __init__(self, depth, value):
        self.depth = depth
        self.value = value
class TableHeader:
    """[server] or [a.b.c] - grammar production: standard_table"""
    def __init__(self, path):
        self.path = path            # list of key segments


class ArrayTableHeader:
    """[[products]] - grammar production: array_table"""
    def __init__(self, path):
        self.path = path


class Comment:
    """# text - grammar production: comment"""
    def __init__(self, text):
        self.text = text


class KeyValue:
    """key = value - grammar production: key_value"""
    def __init__(self, key, value):
        self.key = key              # str, DottedKey path, or QuotedKey
        self.value = value


class Document:
    """The whole file - grammar production: document"""
    def __init__(self, statements):
        self.statements = statements   # list of the above
class RawValue:
    """A value already in TOML text form - used for datetimes,
    non-decimal integers, inf/nan, and multi-line strings, where
    Python has no matching native type. `production` records which
    grammar production it represents, for coverage measurement."""
    def __init__(self, text, production):
        self.text = text
        self.production = production

class QuotedKey:
    """A key written in quotes - grammar production: quoted_key"""
    def __init__(self, text, literal=False):
        self.text = text
        self.literal = literal      # True -> 'single', False -> "double"

def depth(node) -> int:
    """How many layers deep is this structure?

    Iterative, not recursive - deep structures would otherwise
    overflow Python's own stack (which is the same bug class we
    are hunting in the C parser).

    Document/KeyValue/header nodes are walked through without adding
    depth: a document containing one 3-deep array is 3 deep, not 5.
    Statements are structure, not nesting.
    """
    max_d = 0
    stack = [(node, 0)]
    while stack:
        current, d = stack.pop()
        if isinstance(current, Document):
            for stmt in current.statements:
                stack.append((stmt, d))
        elif isinstance(current, KeyValue):
            stack.append((current.value, d))
        elif isinstance(current, (TableHeader, ArrayTableHeader, Comment)):
            max_d = max(max_d, d)
        elif isinstance(current, DottedKey):
            max_d = max(max_d, d + current.depth)
            stack.append((current.value, d + current.depth))
        elif isinstance(current, dict):
            max_d = max(max_d, d + 1)
            for v in current.values():
                stack.append((v, d + 1))
        elif isinstance(current, list):
            max_d = max(max_d, d + 1)
            for child in current:
                stack.append((child, d + 1))
        else:
            max_d = max(max_d, d)
    return max_d

def serialize(node) -> str:
    """Turn a structure into TOML text. Iterative, to survive deep nesting."""
    out = []
    stack = [("value", node)]
    while stack:
        kind, item = stack.pop()
        if kind == "raw":
            out.append(item)
            continue
        if isinstance(item, RawValue):
            out.append(item.text)
            continue
        if isinstance(item, DottedKey):
            key = ".".join("a" for _ in range(item.depth))
            stack.append(("value", item.value))
            stack.append(("raw", key + " = "))
            continue
        if isinstance(item, dict):
            stack.append(("raw", " }"))
            items = list(item.items())
            for i, (k, v) in enumerate(reversed(items)):
                stack.append(("value", v))
                stack.append(("raw", f"{k} = "))
                if i < len(items) - 1:
                    stack.append(("raw", ", "))
            stack.append(("raw", "{ "))
        elif isinstance(item, list):
            stack.append(("raw", "]"))
            for i, child in enumerate(reversed(item)):
                stack.append(("value", child))
                if i < len(item) - 1:
                    stack.append(("raw", ", "))
            stack.append(("raw", "["))
        elif isinstance(item, bool):
            out.append("true" if item else "false")
        elif isinstance(item, str):
            out.append('"' + item + '"')
        else:
            out.append(str(item))
    return "".join(out)
def serialize_document(doc) -> str:
    """Render a Document to TOML text, one statement per line."""
    lines = []
    for stmt in doc.statements:
        if isinstance(stmt, TableHeader):
            lines.append("[" + ".".join(stmt.path) + "]")
        elif isinstance(stmt, ArrayTableHeader):
            lines.append("[[" + ".".join(stmt.path) + "]]")
        elif isinstance(stmt, Comment):
            lines.append("#" + stmt.text)
        elif isinstance(stmt, KeyValue):
            lines.append(serialize_key(stmt.key) + " = " + serialize(stmt.value))
        else:
            raise ValueError(f"unknown statement type: {type(stmt)}")
    return "\n".join(lines)


def serialize_key(key) -> str:
    if isinstance(key, QuotedKey):
        q = "'" if key.literal else '"'
        return q + key.text + q
    if isinstance(key, list):
        return ".".join(key)
    return str(key)

def to_toml(node) -> str:
    if isinstance(node, Document):
        return serialize_document(node)
    if isinstance(node, DottedKey):
        return serialize(node)
    return "a = " + serialize(node)

def node_types(node) -> set:
    """Which ANTLR grammar productions does this structure exercise?
    Names match TomlParser.g4 / TomlLexer.g4 exactly, so coverage is
    checkable against the grammar rather than against invented labels."""
    found = set()
    stack = [node]
    while stack:
        current = stack.pop()

        if isinstance(current, Document):
            found.add("document")
            stack.extend(current.statements)
        elif isinstance(current, TableHeader):
            found.update({"expression", "table", "standard_table", "key"})
        elif isinstance(current, ArrayTableHeader):
            found.update({"expression", "table", "array_table", "key"})
        elif isinstance(current, Comment):
            found.update({"expression", "comment"})
        elif isinstance(current, KeyValue):
            found.update({"expression", "key_value", "key", "value"})
            if isinstance(current.key, str):
                found.update({"simple_key", "unquoted_key"})
            elif isinstance(current.key, list):
                # a.b.c - a list of key segments, NOT an array value
                found.update({"dotted_key", "simple_key", "unquoted_key"})
            else:
                stack.append(current.key)   # QuotedKey / DottedKey handle themselves
            stack.append(current.value)
        elif isinstance(current, QuotedKey):
            found.update({"simple_key", "quoted_key"})
            found.add("LITERAL_STRING" if current.literal else "BASIC_STRING")
        elif isinstance(current, DottedKey):
            found.update({"key", "dotted_key", "simple_key", "unquoted_key"})
            stack.append(current.value)
        elif isinstance(current, RawValue):
            found.add("value")
            found.add(current.production)
            # map token to its parent production
            if current.production in ("OFFSET_DATE_TIME", "LOCAL_DATE_TIME",
                                      "LOCAL_DATE", "LOCAL_TIME"):
                found.add("date_time")
            elif current.production in ("HEX_INT", "OCT_INT", "BIN_INT", "DEC_INT"):
                found.add("integer")
            elif current.production in ("FLOAT", "INF", "NAN"):
                found.add("floating_point")
            elif current.production in ("BASIC_STRING", "ML_BASIC_STRING",
                                        "LITERAL_STRING", "ML_LITERAL_STRING"):
                found.add("string")
        elif isinstance(current, dict):
            found.update({"value", "inline_table", "inline_table_keyvals"})
            if current:
                found.add("inline_table_keyvals_non_empty")
            stack.extend(current.values())
        elif isinstance(current, list):
            found.add("value")
            found.add("array_")
            if current:
                found.add("array_values")
            stack.extend(current)
        elif isinstance(current, bool):
            found.update({"value", "bool_", "BOOLEAN"})
        elif isinstance(current, str):
            found.update({"value", "string", "BASIC_STRING"})
        elif isinstance(current, int):
            found.update({"value", "integer", "DEC_INT"})
        elif isinstance(current, float):
            found.update({"value", "floating_point", "FLOAT"})
    return found
ALL_PRODUCTIONS = {
    "document", "expression", "comment", "key_value", "key", "simple_key",
    "unquoted_key", "quoted_key", "dotted_key", "value", "string", "integer",
    "floating_point", "bool_", "date_time", "array_", "array_values",
    "table", "standard_table", "inline_table", "inline_table_keyvals",
    "inline_table_keyvals_non_empty", "array_table",
}


def production_coverage(structures: list) -> dict:
    """Coverage against TomlParser.g4's parser productions."""
    seen = set()
    for s in structures:
        seen |= node_types(s)
    covered = seen & ALL_PRODUCTIONS
    return {
        "covered": len(covered),
        "total": len(ALL_PRODUCTIONS),
        "missing": sorted(ALL_PRODUCTIONS - covered),
        "tokens_seen": sorted(seen - ALL_PRODUCTIONS),
    }


def summarise(structures: list) -> dict:
    if not structures:
        return {}
    depths = [depth(s) for s in structures]
    cov = production_coverage(structures)
    all_types = set()
    for s in structures:
        all_types |= node_types(s)
    return {
        "count": len(structures),
        "depth_max": max(depths),
        "depth_avg": round(sum(depths) / len(depths), 1),
        "productions_covered": cov["covered"],
        "productions_total": cov["total"],
        "productions_missing": cov["missing"],
        "types_seen": sorted(all_types),
    }

if __name__ == "__main__":
    tests = [
        1,
        [1, 2, 3],
        [[1, 2]],
        [[[1]]],
        [],
        [1, [2, [3, [4]]]],
        [True, "hello", 42],
    ]
    for t in tests:
        print(f"depth {depth(t)}  types {node_types(t)}  {to_toml(t)}")

    batch = [[1], [[2]], [[[3]]], [True, "x"], [1, 2, 3]]
    print("\nBatch summary:", summarise(batch))