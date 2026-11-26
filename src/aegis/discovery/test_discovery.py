
import networkx as nx


def discover_tests(
    graph: nx.DiGraph,
    test_functions: dict,
    changed_ids: list[str],
) -> list[dict]:
    """Discover and rank tests that depend on changed functions."""

    discovered = []

    for test_id, test_data in test_functions.items():
        if test_id not in graph:
            continue

        shortest_distance = None

        for changed_id in changed_ids:
            if changed_id not in graph:
                continue

            try:
                distance = nx.shortest_path_length(
                    graph,
                    source=test_id,
                    target=changed_id,
                )
            except nx.NetworkXNoPath:
                continue

            if shortest_distance is None or distance < shortest_distance:
                shortest_distance = distance

        if shortest_distance is None:
            continue

        score = round(100 / shortest_distance, 2)

        if shortest_distance == 1:
            reason = "Direct dependency on a changed function"
        else:
            reason = (
                f"Indirect dependency through "
                f"{shortest_distance - 1} intermediate call(s)"
            )

        discovered.append(
            {
                **test_data,
                "id": test_id,
                "distance": shortest_distance,
                "score": score,
                "reason": reason,
            }
        )

    return sorted(
        discovered,
        key=lambda item: (
            -item["score"],
            item["id"],
        ),
    )
