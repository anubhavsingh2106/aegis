
from aegis.verification.regression_analysis import correlate_failures


def make_report():
    test_id = "test-node"
    changed_id = "changed-node"

    return {
        "candidate_tests": [
            {
                "id": test_id,
                "name": "test_calculate_total",
                "qualified_name": "test_calculate_total",
                "file": "tests/test_pricing.py",
                "pytest_node_id": (
                    "tests/test_pricing.py::test_calculate_total"
                ),
            }
        ],
        "changed_functions": [
            {
                "id": changed_id,
                "name": "calculate_total",
                "file": "pricing.py",
            }
        ],
        "graph": {
            "edges": [
                {
                    "caller": test_id,
                    "callee": changed_id,
                }
            ]
        },
    }


def make_verification():
    return {
        "changed": {
            "failures": [
                {
                    "test": "test_calculate_total",
                    "failure_type": "assertion_error",
                    "expected": "20",
                    "actual": "12",
                    "traceback": (
                        "tests/test_pricing.py:5: AssertionError"
                    ),
                }
            ]
        }
    }


def test_correlates_failed_test_with_changed_function():
    report = correlate_failures(
        make_report(),
        make_verification(),
    )

    assert report["status"] == "correlated"
    assert len(report["correlations"]) == 1

    correlation = report["correlations"][0]

    assert correlation["relationship"] == "direct"
    assert correlation["changed_function"]["name"] == "calculate_total"
    assert correlation["causality_confirmed"] is False


def test_reports_missing_dependency_path():
    impact = make_report()
    impact["graph"]["edges"] = []

    report = correlate_failures(
        impact,
        make_verification(),
    )

    assert report["status"] == "uncorrelated"
    assert len(report["unmatched_failures"]) == 1


def test_reports_no_failures():
    verification = {"changed": {"failures": []}}

    report = correlate_failures(
        make_report(),
        verification,
    )

    assert report["status"] == "no_failures"
    assert report["correlations"] == []
