import io
import subprocess
import tarfile
from unittest.mock import patch

from aegis.verification.docker_runner import run_pytest_in_docker


@patch("aegis.verification.docker_runner.subprocess.run")
@patch("aegis.verification.docker_runner.tempfile.TemporaryDirectory")
@patch("aegis.verification.docker_runner.run_git")
def test_docker_startup_error_is_not_test_failure(
    mock_git, mock_temp, mock_run, tmp_path
):
    mock_git.return_value = "abc123\n"
    mock_temp.return_value.__enter__.return_value = str(tmp_path)

    # Simulate a Docker daemon error instead of a pytest failure.
    def fake_run(command, **kwargs):
        if command[0] == "git":
            # Write a valid tar archive to the runner's output file.
            with tarfile.open(fileobj=kwargs["stdout"], mode="w") as archive:
                info = tarfile.TarInfo("README.md")
                content = b"test fixture"
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))

            return subprocess.CompletedProcess(
                args=command, returncode=0, stdout=None, stderr=b""
            )

        # Simulate Docker failing before pytest can start.
        return subprocess.CompletedProcess(
            args=command,
            returncode=125,
            stdout="",
            stderr="Error response from daemon: Docker unavailable",
        )

    mock_run.side_effect = fake_run

    # Create the archive path expected by the runner.
    # Create a valid, empty tar archive for the runner to extract.
    with tarfile.open(tmp_path / "source.tar", "w") as archive:
        info = tarfile.TarInfo("README.md")
        content = b"test fixture"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))

    report = run_pytest_in_docker("demo", "HEAD")

    assert report["status"] == "error"
    assert report["status"] != "failed"
