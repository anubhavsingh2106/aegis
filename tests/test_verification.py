
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
