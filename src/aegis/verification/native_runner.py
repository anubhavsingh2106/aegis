
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from aegis.git_analysis.diff import run_git


def _classify_pytest_result(
    returncode: int,
    stdout: str,
) -> str:
    output = stdout.lower()

    if "no tests ran" in output:
        return "error"

    has_summary = any(
        re.search(rf"\b\d+\s+{word}\b", output)
        for word in ("passed", "failed", "error", "errors")
    )

    if not has_summary:
        return "error"

    if returncode != 0 and re.search(r"\b\d+\s+failed\b", output):
        return "failed"

    if returncode == 0 and not re.search(r"\b\d+\s+failed\b", output):
        return "passed"

    return "error"


def run_pytest_natively(
    repo: str,
    revision: str,
    timeout: int = 60,
) -> dict[str, Any]:
    """Run pytest locally for a trusted repository. This is not a sandbox."""
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

    with tempfile.TemporaryDirectory(prefix="aegis-native-") as temp:
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

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ]

        try:
            result = subprocess.run(
                command,
                cwd=snapshot,
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
            }
        except OSError as exc:
            return {
                "revision": commit,
                "status": "error",
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            }

        status = _classify_pytest_result(
            result.returncode,
            result.stdout or "",
        )

        return {
            "revision": commit,
            "status": status,
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }


class NativeRunner:
    """TestRunner-compatible backend for trusted local repositories."""

    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout

    def run(self, repo: str, revision: str) -> dict[str, Any]:
        return run_pytest_natively(
            repo,
            revision,
            timeout=self.timeout,
        )
