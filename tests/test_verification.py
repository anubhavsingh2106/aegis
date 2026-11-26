
from unittest.mock import patch

from aegis.verification.docker_runner import compare_revisions


def result(status):
    return {
        "revision": "abc123",
        "status": status,
        "exit_code": 0 if status == "passed" else 1,
        "stdout": "",
        "stderr": "",
    }


@patch("aegis.verification.docker_runner.run_pytest_in_docker")
def test_detects_regression(mock_run):
    mock_run.side_effect = [result("passed"), result("failed")]

    report = compare_revisions("demo", "base")

    assert report["status"] == "regression_detected"
    assert report["regression_detected"] is True


@patch("aegis.verification.docker_runner.run_pytest_in_docker")
def test_does_not_confirm_regression_when_baseline_fails(mock_run):
    mock_run.side_effect = [result("failed"), result("failed")]

    report = compare_revisions("demo", "base")

    assert report["status"] == "inconclusive"
    assert report["regression_detected"] is False


@patch("aegis.verification.docker_runner.run_pytest_in_docker")
def test_does_not_confirm_regression_on_timeout(mock_run):
    mock_run.side_effect = [result("passed"), result("timeout")]

    report = compare_revisions("demo", "base")

    assert report["status"] == "inconclusive"
    assert report["regression_detected"] is False


@patch("aegis.verification.docker_runner.run_pytest_in_docker")
def test_extracts_structured_failures_from_changed_revision(mock_run):
    failure_output = """
____________________________ test_calculate_total ____________________________

    def test_calculate_total():
>       assert calculate_total(10, 2) == 20
E       assert 12 == 20

tests/test_pricing.py:5: AssertionError
"""

    baseline = result("passed")
    changed = result("failed")
    changed["stdout"] = failure_output

    mock_run.side_effect = [baseline, changed]

    report = compare_revisions("demo", "base")

    failures = report["changed"]["failures"]

    assert len(failures) == 1
    assert failures[0]["test"] == "test_calculate_total"
    assert failures[0]["failure_type"] == "assertion_error"
    assert failures[0]["expected"] == "20"
    assert failures[0]["actual"] == "12"
    assert failures[0]["message"] == "assert 12 == 20"


@patch("aegis.verification.docker_runner.run_pytest_in_docker")
def test_successful_execution_has_empty_failures(mock_run):
    mock_run.side_effect = [
        result("passed"),
        result("passed"),
    ]

    report = compare_revisions("demo", "base")

    assert report["baseline"]["failures"] == []
    assert report["changed"]["failures"] == []
