
import pytest

from aegis.verification.policy import select_runner


class FakeRunner:
    def run(self, repo: str, revision: str) -> dict:
        return {"revision": revision, "status": "passed"}


def test_native_runner_requires_trusted_repository():
    with pytest.raises(PermissionError):
        select_runner(
            "native",
            trusted_repository=False,
            native_runner=FakeRunner(),
        )


def test_native_runner_requires_explicit_configuration():
    with pytest.raises(RuntimeError, match="not configured"):
        select_runner("native", trusted_repository=True)


def test_remote_runner_does_not_fall_back():
    with pytest.raises(RuntimeError, match="No fallback"):
        select_runner("remote")


def test_analysis_only_does_not_select_a_runner():
    assert select_runner("analysis-only") is None


def test_docker_runner_can_be_injected():
    runner = FakeRunner()

    assert select_runner("docker", docker_runner=runner) is runner


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        select_runner("unsafe-mode")  # type: ignore[arg-type]

