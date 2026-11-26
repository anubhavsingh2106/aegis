
import networkx as nx


def correlate_failures(
    impact_report: dict,
    verification: dict,
) -> dict:
    """Connect failed tests to changed functions through dependency paths."""

    failures = verification.get("changed", {}).get("failures", [])
    candidates = impact_report.get("candidate_tests", [])
    changed_functions = impact_report.get("changed_functions", [])

    graph = nx.DiGraph()

    for edge in impact_report.get("graph", {}).get("edges", []):
        graph.add_edge(edge["caller"], edge["callee"])

    correlations = []
    unmatched_failures = []

    for failure in failures:
        test_name = failure.get("test", "")
        traceback = failure.get("traceback", "").replace("\\", "/")

        matching_candidates = [
            candidate
            for candidate in candidates
            if (
                candidate.get("name") == test_name
                or candidate.get("qualified_name", "").endswith(test_name)
            )
            and candidate.get("file", "").replace("\\", "/") in traceback
        ]

        if not matching_candidates:
            unmatched_failures.append(
                {
                    "failure": failure,
                    "reason": "Could not match failure to a discovered test.",
                }
            )
            continue

        matched = False

        for candidate in matching_candidates:
            test_id = candidate["id"]

            for changed in changed_functions:
                changed_id = changed["id"]

                if test_id not in graph or changed_id not in graph:
                    continue

                try:
                    path = nx.shortest_path(
                        graph,
                        source=test_id,
                        target=changed_id,
                    )
                except nx.NetworkXNoPath:
                    continue

                relationship = (
                    "direct" if len(path) == 2 else "indirect"
                )

                correlations.append(
                    {
                        "test": candidate["pytest_node_id"],
                        "changed_function": {
                            "id": changed_id,
                            "name": changed["name"],
                            "file": changed["file"],
                        },
                        "dependency_path": path,
                        "relationship": relationship,
                        "evidence": (
                            f"The failed test has a {relationship} "
                            f"dependency path to the changed function."
                        ),
                        "causality_confirmed": False,
                    }
                )

                matched = True

        if not matched:
            unmatched_failures.append(
                {
                    "failure": failure,
                    "reason": (
                        "The test was discovered, but no dependency "
                        "path to a changed function was found."
                    ),
                }
            )

    if correlations:
        status = "correlated"
    elif unmatched_failures:
        status = "uncorrelated"
    else:
        status = "no_failures"

    return {
        "status": status,
        "correlations": correlations,
        "unmatched_failures": unmatched_failures,
    }
