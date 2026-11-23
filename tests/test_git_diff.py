
import subprocess

from aegis.git_analysis.diff import analyze_diff


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_detects_changed_python_lines(tmp_path):
    repo = tmp_path

    git(repo, "init")
    git(repo, "config", "user.name", "Aegis Test")
    git(repo, "config", "user.email", "test@example.com")

    file = repo / "pricing.py"
    file.write_text(
        "def total(price, quantity):\n"
        "    return price * quantity\n",
        encoding="utf-8",
    )

    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    base = git(repo, "rev-parse", "HEAD").strip()

    file.write_text(
        "def total(price, quantity):\n"
        "    return price + quantity\n",
        encoding="utf-8",
    )

    git(repo, "add", ".")
    git(repo, "commit", "-m", "change calculation")

    report = analyze_diff(str(repo), base)

    assert len(report["files"]) == 1
    assert report["files"][0]["new_file"] == "pricing.py"
    assert report["files"][0]["added_lines"] == [
        {"start": 2, "end": 2}
    ]
    assert report["files"][0]["deleted_lines"] == [
        {"start": 2, "end": 2}
    ]
