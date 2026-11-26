
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from aegis.git_analysis.diff import run_git
from aegis.verification.failure_parser import parse_pytest_failures
from aegis.verification.interface import TestRunner
from aegis.verification.policy import ExecutionMode, select_runner


def run_pytest_in_docker(
    repo: str,
    revision: str,
    image: str = "aegis-test-runner:local",
    timeout: int = 60,
    test_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run the selected pytest tests inside the Docker sandbox."""

    repo_path = Path(repo).resolve()

    try:
        commit = run_git(
            repo_path, "rev-parse", "--verify", f"{revision}^{{commit}}"
        ).strip()
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as exc:
        return {
            "revision": revision,
            "status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }

    with tempfile.TemporaryDirectory(prefix="aegis-") as temp:
        root = Path(temp)
        snapshot = root / "snapshot"
        snapshot.mkdir()

        archive_path = root / "source.tar"

        try:
            with archive_path.open("wb") as archive:
                result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_path),
                        "archive",
                        "--format=tar",
                        commit,
                    ],
                    stdout=archive,
                    stderr=subprocess.PIPE,
                    check=False,
                )

            if result.returncode != 0:
                return {
                    "revision": commit,
                    "status": "error",
                    "exit_code": result.returncode,
                    "stdout": "",
                    "stderr": result.stderr.decode(
                        "utf-8", errors="replace"
                    ),
                }

            with tarfile.open(archive_path, "r:") as archive:
                archive.extractall(snapshot, filter="data")

        except (OSError, tarfile.TarError, subprocess.SubprocessError) as exc:
            return {
                "revision": commit,
                "status": "error",
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            }

        mount_path = snapshot.resolve().as_posix()

        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--mount",
            f"type=bind,source={mount_path},target=/workspace,readonly",
            "--workdir",
            "/workspace",
            image,
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ]

        if test_ids is not None:
            command.extend(test_ids)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "revision": commit,
                "status": "timeout",
                "exit_code": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "test_ids": test_ids,
            }
        except OSError as exc:
            return {
                "revision": commit,
                "status": "error",
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
                "test_ids": test_ids,
            }

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        stdout_lower = stdout.lower()
        stderr_lower = stderr.lower()

        docker_error = any(
            marker in stderr_lower
            for marker in (
                "error response from daemon",
                "cannot connect to the docker daemon",
                "error during connect",
                "pull access denied",
                "image not found",
                "no such image",
                "mounts denied",
                "invalid mount config",
            )
        )

        pytest_finished = any(
            marker in stdout_lower
            for marker in (
                " passed",
                " failed",
                " error",
                " no tests ran",
            )
        )

        if docker_error or not pytest_finished:
            status = "error"
        elif result.returncode == 0 and " failed" not in stdout_lower:
            status = "passed"
        elif result.returncode != 0 and " failed" in stdout_lower:
            status = "failed"
        else:
            status = "error"

        return {
            "revision": commit,
            "status": status,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "test_ids": test_ids,
        }


def compare_revisions(
    repo: str,
    base: str,
    head: str = "HEAD",
    *,
    mode: ExecutionMode = "docker",
    trusted_repository: bool = False,
    docker_runner: TestRunner | None = None,
    remote_runner: TestRunner | None = None,
    native_runner: TestRunner | None = None,
    test_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Compare test results between baseline and changed revisions."""

    if test_ids is not None and not test_ids:
        return {
            "baseline": None,
            "changed": None,
            "status": "verification_skipped",
            "regression_detected": False,
            "execution_mode": mode,
            "test_ids": [],
            "reason": "No candidate tests were discovered.",
        }

    try:
        runner = select_runner(
            mode,
            trusted_repository=trusted_repository,
            docker_runner=docker_runner,
            remote_runner=remote_runner,
            native_runner=native_runner,
        )
    except (PermissionError, RuntimeError) as exc:
        failure = {
            "revision": "",
            "status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }

        return {
            "baseline": failure.copy(),
            "changed": failure.copy(),
            "status": "inconclusive",
            "regression_detected": False,
            "execution_mode": mode,
            "test_ids": test_ids,
        }

    if runner is None:
        return {
            "baseline": None,
            "changed": None,
            "status": "verification_skipped",
            "regression_detected": False,
            "execution_mode": mode,
            "test_ids": test_ids,
            "reason": "Analysis-only mode; no tests were executed.",
        }

    if test_ids is None:
        baseline_result = runner.run(repo, base)
        changed_result = runner.run(repo, head)
    else:
        baseline_result = runner.run(repo, base, test_ids)
        changed_result = runner.run(repo, head, test_ids)

    baseline = {
        **baseline_result,
        "failures": parse_pytest_failures(
            baseline_result.get("stdout", "")
        ),
    }

    changed = {
        **changed_result,
        "failures": parse_pytest_failures(
            changed_result.get("stdout", "")
        ),
    }

    regression = (
        baseline.get("status") == "passed"
        and changed.get("status") == "failed"
    )

    if regression:
        status = "regression_detected"
    elif (
        baseline.get("status") != "passed"
        or changed.get("status") not in {"passed", "failed"}
    ):
        status = "inconclusive"
    else:
        status = "no_new_failure_detected"

    return {
        "baseline": baseline,
        "changed": changed,
        "status": status,
        "regression_detected": regression,
        "execution_mode": mode,
        "test_ids": test_ids,
    }
