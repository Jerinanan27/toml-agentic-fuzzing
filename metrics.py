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


if __name__ == "__main__":
    tests = [
        1,
        [1, 2, 3],
        [[1, 2]],
        [[[1]]],
        [[[[[1]]]]],
        [],
        [1, [2, [3, [4]]]],
    ]
    for t in tests:
        print(f"depth {depth(t)}   {t}")