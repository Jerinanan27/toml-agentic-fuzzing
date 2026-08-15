def depth(node) -> int:
    """How many layers deep is this structure?

    A plain value (number, string) has depth 0.
    A list has depth 1 + the depth of its deepest child.
    """
    if isinstance(node, list):
        if not node:
            return 1
        return 1 + max(depth(child) for child in node)
    return 0

def serialize(node) -> str:
    """Turn a structure into TOML text."""
    if isinstance(node, list):
        inner = ", ".join(serialize(child) for child in node)
        return "[" + inner + "]"
    if isinstance(node, bool):
        return "true" if node else "false"
    if isinstance(node, str):
        return '"' + node + '"'
    return str(node)


def to_toml(node) -> str:
    """Wrap a value into a complete TOML document."""
    return "a = " + serialize(node)

def node_types(node) -> set:
    """What types of nodes appear in this structure?"""
    if isinstance(node, list):
        types = {"array"}
        for child in node:
            types |= node_types(child)
        return types
    if isinstance(node, bool):
        return {"bool"}
    if isinstance(node, str):
        return {"string"}
    if isinstance(node, int):
        return {"integer"}
    if isinstance(node, float):
        return {"float"}
    return {"unknown"}

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