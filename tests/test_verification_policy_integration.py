
from aegis.verification.docker_runner import compare_revisions


class FakeRunner:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.calls = []

    def run(self, repo, revision):
        self.calls.append((repo, revision))
        return {
            "revision": revision,
            "status": next(self.statuses),
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }


def test_native_mode_rejects_untrusted_repository():
    runner = FakeRunner(["passed", "failed"])

    result = compare_revisions(
        "demo",
        "base",
        mode="native",
        trusted_repository=False,
        native_runner=runner,
    )

    assert result["status"] == "inconclusive"
    assert result["regression_detected"] is False
    assert runner.calls == []


def test_missing_remote_runner_never_falls_back():
    result = compare_revisions(
        "demo",
        "base",
        mode="remote",
    )

    assert result["status"] == "inconclusive"
    assert result["regression_detected"] is False


def test_analysis_only_skips_execution():
    result = compare_revisions(
        "demo",
        "base",
        mode="analysis-only",
    )

    assert result["status"] == "verification_skipped"
    assert result["baseline"] is None
    assert result["changed"] is None


def test_injected_docker_runner_detects_regression():
    runner = FakeRunner(["passed", "failed"])

    result = compare_revisions(
        "demo",
        "base",
        mode="docker",
        docker_runner=runner,
    )

    assert result["status"] == "regression_detected"
    assert result["regression_detected"] is True
    assert len(runner.calls) == 2
