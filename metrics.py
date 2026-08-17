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

def depth(node) -> int:
    """How many layers deep is this structure?

    Iterative, not recursive - deep structures would otherwise
    overflow Python's own stack (which is the same bug class we
    are hunting in the C parser).
    """
    max_d = 0
    stack = [(node, 0)]
    while stack:
        current, d = stack.pop()
        if isinstance(current, DottedKey):
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


def to_toml(node) -> str:
    if isinstance(node, DottedKey):
        return serialize(node)   # already a full statement
    return "a = " + serialize(node)

def node_types(node) -> set:
    """What types of nodes appear? Iterative, for the same reason as depth()."""
    found = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, DottedKey):
            found.add("dotted_key")
            stack.append(current.value)
        elif isinstance(current, dict):
            found.add("inline_table")
            stack.extend(current.values())
        elif isinstance(current, list):
            found.add("array")
            stack.extend(current)
        elif isinstance(current, bool):
            found.add("bool")
        elif isinstance(current, str):
            found.add("string")
        elif isinstance(current, int):
            found.add("integer")
        elif isinstance(current, float):
            found.add("float")
        else:
            found.add("unknown")
    return found

def summarise(structures: list) -> dict:
    """Summarise a batch of structures."""
    if not structures:
        return {}
    depths = [depth(s) for s in structures]
    all_types = set()
    for s in structures:
        all_types |= node_types(s)
    return {
        "count": len(structures),
        "depth_max": max(depths),
        "depth_avg": round(sum(depths) / len(depths), 1),
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