"""Graph-based N-1 connectivity screening for small networks."""


def is_connected(nodes: set[str], edges: list[tuple[str, str]], removed: int | None = None) -> bool:
    if not nodes:
        return True
    adjacency = {node: set() for node in nodes}
    for index, (left, right) in enumerate(edges):
        if index == removed:
            continue
        if left not in nodes or right not in nodes:
            raise ValueError("edge references an unknown node")
        adjacency[left].add(right)
        adjacency[right].add(left)
    seen, stack = set(), [next(iter(nodes))]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node] - seen)
    return seen == nodes


def critical_lines(nodes: set[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [edge for index, edge in enumerate(edges) if not is_connected(nodes, edges, index)]


def n_minus_one_secure(nodes: set[str], edges: list[tuple[str, str]]) -> bool:
    return is_connected(nodes, edges) and not critical_lines(nodes, edges)
