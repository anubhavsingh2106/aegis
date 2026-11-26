
from typing import Any, Protocol


class TestRunner(Protocol):
    """Interface implemented by Aegis test execution backends."""

    def run(
        self,
        repo: str,
        revision: str,
        test_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        ...


class DockerRunner:
    """Adapter for the existing Docker-based verification runner."""

    def __init__(
        self,
        image: str = "aegis-test-runner:local",
        timeout: int = 60,
    ) -> None:
        self.image = image
        self.timeout = timeout

    def run(
        self,
        repo: str,
        revision: str,
        test_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        from aegis.verification.docker_runner import run_pytest_in_docker

        return run_pytest_in_docker(
            repo,
            revision,
            image=self.image,
            timeout=self.timeout,
            test_ids=test_ids,
        )
