
import subprocess

from aegis.graph.impact import analyze_impact


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_analyze_impact_discovers_and_ranks_candidate_tests(tmp_path):
    repo = tmp_path

    git(repo, "init")
    git(repo, "config", "user.name", "Aegis Test")
    git(repo, "config", "user.email", "test@example.com")

    (repo / "tests").mkdir()

    pricing = repo / "pricing.py"
    pricing.write_text(
        "def calculate_total(price, quantity):\n"
        "    return price * quantity\n",
        encoding="utf-8",
    )

    (repo / "support.py").write_text(
        "from pricing import calculate_total\n"
        "\n"
        "def calculate_via_helper():\n"
        "    return calculate_total(2, 3)\n",
        encoding="utf-8",
    )

    (repo / "tests" / "test_pricing.py").write_text(
        "from pricing import calculate_total\n"
        "from support import calculate_via_helper\n"
        "\n"
        "def test_direct():\n"
        "    assert calculate_total(2, 3) == 6\n"
        "\n"
        "def test_indirect():\n"
        "    assert calculate_via_helper() == 6\n"
        "\n"
        "def test_unrelated():\n"
        "    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")
    base = git(repo, "rev-parse", "HEAD").strip()

    pricing.write_text(
        "def calculate_total(price, quantity):\n"
        "    return price + quantity\n",
        encoding="utf-8",
    )

    git(repo, "add", ".")
    git(repo, "commit", "-m", "change calculation")

    report = analyze_impact(str(repo), base)

    candidates = report["candidate_tests"]

    assert len(candidates) == 2

    assert candidates[0]["name"] == "test_direct"
    assert candidates[1]["name"] == "test_indirect"

    assert candidates[0]["distance"] == 1
    assert candidates[1]["distance"] == 2

    assert candidates[0]["score"] == 100
    assert candidates[1]["score"] == 50

    assert candidates[0]["reason"] == (
        "Direct dependency on a changed function"
    )

    assert candidates[0]["pytest_node_id"] == (
        "tests/test_pricing.py::test_direct"
    )

    assert candidates[1]["pytest_node_id"] == (
        "tests/test_pricing.py::test_indirect"
    )

    assert "Indirect dependency" in candidates[1]["reason"]

    assert all(
        candidate["name"] != "test_unrelated"
        for candidate in candidates
    )
