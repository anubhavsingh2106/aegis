import json

import pytest

from aegis import cli


def sample_report():
    return {
        "changed_functions": [{"id": "f1"}],
        "potentially_affected_callers": [{"id": "f2"}, {"id": "f3"}],
    }


def test_analysis_only_skips_verification(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", [
        "aegis", "demo", "--base", "base123",
        "--verify-mode", "analysis-only", "--output", str(output),
    ])
    monkeypatch.setattr(cli, "analyze_impact", lambda *args: sample_report())

    def fail_if_called(*args, **kwargs):
        pytest.fail("Verification must not run in analysis-only mode")

    monkeypatch.setattr(cli, "compare_revisions", fail_if_called)

    cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["verification"]["status"] == "verification_skipped"


def test_native_mode_requires_trust(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "aegis", "demo", "--base", "base123",
        "--verify-mode", "native",
    ])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2


def test_docker_remains_default(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", [
        "aegis", "demo", "--base", "base123",
        "--verify", "--output", str(output),
    ])
    monkeypatch.setattr(cli, "analyze_impact", lambda *args: sample_report())

    def fake_compare(repo, base, **kwargs):
        assert kwargs["mode"] == "docker"
        return {
            "status": "inconclusive",
            "regression_detected": False,
        }

    monkeypatch.setattr(cli, "compare_revisions", fake_compare)

    cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["verification"]["status"] == "inconclusive"


def test_native_mode_passes_explicit_trust(tmp_path, monkeypatch):
    output = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", [
        "aegis", "demo", "--base", "base123",
        "--verify-mode", "native", "--trust-repo",
        "--output", str(output),
    ])
    monkeypatch.setattr(cli, "analyze_impact", lambda *args: sample_report())

    def fake_compare(repo, base, **kwargs):
        assert kwargs["mode"] == "native"
        assert kwargs["trusted_repository"] is True
        assert kwargs["native_runner"] is not None
        return {
            "status": "inconclusive",
            "regression_detected": False,
        }

    monkeypatch.setattr(cli, "compare_revisions", fake_compare)

    cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["verification"]["status"] == "inconclusive"


def test_inspect_context_adds_preview_to_report(tmp_path, monkeypatch):
    output = tmp_path / "report.json"

    report_data = {
        "repository": "demo",
        "base_revision": "base123",
        "head_revision": "head123",
        "changed_functions": [
            {
                "id": "f1",
                "file": "app.py",
                "name": "login",
                "source": 'API_KEY = "secret123"',
            }
        ],
        "potentially_affected_callers": [],
        "candidate_tests": [],
    }

    monkeypatch.setattr(
        "sys.argv",
        [
            "aegis",
            "demo",
            "--base",
            "base123",
            "--inspect-context",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        cli,
        "analyze_impact",
        lambda *args: report_data,
    )

    cli.main()

    result = json.loads(output.read_text(encoding="utf-8"))

    assert "context_package" in result
    assert "outbound_preview" in result
    assert len(result["context_package"]["snippets"]) == 1


def test_inspect_context_redacts_secrets_in_report(tmp_path, monkeypatch):
    output = tmp_path / "report.json"

    report_data = {
        "repository": "demo",
        "base_revision": "base123",
        "head_revision": "head123",
        "changed_functions": [
            {
                "id": "f1",
                "file": "app.py",
                "name": "login",
                "source": 'API_KEY = "secret123"',
            }
        ],
        "potentially_affected_callers": [],
        "candidate_tests": [],
    }

    monkeypatch.setattr(
        "sys.argv",
        [
            "aegis",
            "demo",
            "--base",
            "base123",
            "--inspect-context",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        cli,
        "analyze_impact",
        lambda *args: report_data,
    )

    cli.main()

    result = json.loads(output.read_text(encoding="utf-8"))

    preview_source = (
        result["outbound_preview"]["payload"]["snippets"][0]["source"]
    )

    assert "secret123" not in preview_source
    assert "[REDACTED]" in preview_source


def test_inspect_context_does_not_send_data(tmp_path, monkeypatch):
    output = tmp_path / "report.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "aegis",
            "demo",
            "--base",
            "base123",
            "--inspect-context",
            "--output",
            str(output),
        ],
    )
    monkeypatch.setattr(
        cli,
        "analyze_impact",
        lambda *args: sample_report(),
    )

    cli.main()

    result = json.loads(output.read_text(encoding="utf-8"))
    preview = result["outbound_preview"]

    assert preview["approved"] is False
    assert preview["send_enabled"] is False
    assert preview["network_requests"] == 0
    assert preview["approval_required"] is True


def test_cli_creates_approval_after_explicit_confirmation(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "report.json"
    approval_output = tmp_path / "approval.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "aegis",
            "demo",
            "--base",
            "base123",
            "--inspect-context",
            "--approve-context",
            "--output",
            str(output),
            "--approval-output",
            str(approval_output),
        ],
    )
    monkeypatch.setattr(
        cli,
        "analyze_impact",
        lambda *args: sample_report(),
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "APPROVE",
    )

    cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))
    approval = json.loads(
        approval_output.read_text(encoding="utf-8")
    )

    assert report["outbound_preview"]["approved"] is False
    assert approval["approved"] is True
    assert (
        approval["payload_sha256"]
        == report["outbound_preview"]["payload_sha256"]
    )


def test_cli_does_not_create_approval_without_confirmation(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "report.json"
    approval_output = tmp_path / "approval.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "aegis",
            "demo",
            "--base",
            "base123",
            "--inspect-context",
            "--approve-context",
            "--output",
            str(output),
            "--approval-output",
            str(approval_output),
        ],
    )
    monkeypatch.setattr(
        cli,
        "analyze_impact",
        lambda *args: sample_report(),
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: "no",
    )

    cli.main()

    assert output.exists()
    assert not approval_output.exists()
