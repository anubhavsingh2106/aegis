
import re
import subprocess
from pathlib import Path


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )  # Runs Git and raises an error if the command fails.

    return result.stdout


def analyze_diff(repo: str, base: str, head: str = "HEAD") -> dict:
    repo_path = Path(repo).resolve()  # Converts the repository path to an absolute path.

    run_git(repo_path, "rev-parse", "--is-inside-work-tree")  # Verifies this is a Git repository.
    run_git(repo_path, "rev-parse", "--verify", f"{base}^{{commit}}")  # Validates the base revision.
    run_git(repo_path, "rev-parse", "--verify", f"{head}^{{commit}}")  # Validates the head revision.

    changed_files = run_git(
        repo_path,
        "diff",
        "--name-status",
        "--find-renames",
        base,
        head,
        "--",
    ).splitlines()  # Lists changed files and their change statuses.

    file_changes = []

    for line in changed_files:
        parts = line.split("\t")
        status = parts[0]

        if status.startswith(("R", "C")):  # Checks rename or copy status in one call.
            old_file, new_file = parts[1], parts[2]
        else:
            old_file = parts[1]
            new_file = parts[1] if status != "D" else None

        if not any(
            name.endswith(".py")
            for name in (old_file, new_file)
            if name is not None
        ):
            continue  # Ignores changes unrelated to Python files.

        file_changes.append({
            "status": status,
            "old_file": old_file,
            "new_file": new_file,
            "added_lines": [],
            "deleted_lines": [],
        })

    for change in file_changes:
        old_file = change["old_file"]
        new_file = change["new_file"]

        if old_file is None or new_file is None:
            continue

        patch = run_git(
            repo_path,
            "diff",
            "--no-ext-diff",
            "--unified=0",
            base,
            head,
            "--",
            old_file,
            new_file,
        )  # Requests minimal diff context so changed line numbers are easier to extract.

        for match in re.finditer(
            r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
            patch,
        ):
            old_start = int(match.group(1))
            old_count = int(match.group(2) or 1)
            new_start = int(match.group(3))
            new_count = int(match.group(4) or 1)

            if old_count:
                change["deleted_lines"].append({
                    "start": old_start,
                    "end": old_start + old_count - 1,
                })

            if new_count:
                change["added_lines"].append({
                    "start": new_start,
                    "end": new_start + new_count - 1,
                })

    return {
        "repository": str(repo_path),
        "base_revision": base,
        "head_revision": head,
        "files": file_changes,
    }
