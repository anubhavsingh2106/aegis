
from typing import Literal

from aegis.verification.interface import DockerRunner, TestRunner

ExecutionMode = Literal["docker", "remote", "native", "analysis-only"]


def select_runner(
    mode: ExecutionMode,
    *,
    trusted_repository: bool = False,
    docker_runner: TestRunner | None = None,
    remote_runner: TestRunner | None = None,
    native_runner: TestRunner | None = None,
) -> TestRunner | None:
    """Select a verification backend without unsafe automatic fallback."""

    if mode == "analysis-only":
        return None

    if mode == "docker":
        # Docker errors must remain errors; never fall back silently.
        return docker_runner if docker_runner is not None else DockerRunner()

    if mode == "remote":
        if remote_runner is None:
            raise RuntimeError(
                "Remote verification is unavailable. "
                "No fallback runner will be selected."
            )
        return remote_runner

    if mode == "native":
        if not trusted_repository:
            raise PermissionError(
                "Native execution is permitted only for trusted repositories."
            )

        if native_runner is None:
            raise RuntimeError(
                "Native runner is not configured."
            )

        return native_runner

    raise ValueError(f"Unsupported execution mode: {mode}")
