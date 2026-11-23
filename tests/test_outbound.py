
import pytest

from aegis.ai.outbound import (
    create_outbound_approval,
    inspect_outbound_context,
    payload_fingerprint,
    verify_outbound_approval,
)


def sample_package():
    return {
        "repository": "demo",
        "base_revision": "base123",
        "head_revision": "head123",
        "snippets": [
            {
                "id": "f1",
                "file": "src/app.py",
                "name": "calculate",
                "start_line": 1,
                "end_line": 3,
                "reason": "changed_function",
                "source": 'API_KEY = "secret123"',
            }
        ],
    }


def test_preview_requires_approval():
    preview = inspect_outbound_context(sample_package())

    assert preview["approval_required"] is True
    assert preview["approved"] is False
    assert preview["send_enabled"] is False
    assert preview["network_requests"] == 0


def test_preview_redacts_secrets():
    preview = inspect_outbound_context(sample_package())

    source = preview["payload"]["snippets"][0]["source"]

    assert "secret123" not in source
    assert "[REDACTED]" in source


def test_preview_contains_only_selected_snippets():
    preview = inspect_outbound_context(sample_package())

    assert len(preview["payload"]["snippets"]) == 1
    assert "graph" not in preview["payload"]


def test_preview_rejects_invalid_snippets():
    package = {"snippets": "invalid"}

    with pytest.raises(TypeError):
        inspect_outbound_context(package)


def test_preview_rejects_invalid_source():
    package = {"snippets": [{"source": 123}]}

    with pytest.raises(TypeError):
        inspect_outbound_context(package)


def test_payload_fingerprint_is_deterministic():
    first = {"name": "demo", "version": 1}
    second = {"version": 1, "name": "demo"}

    assert payload_fingerprint(first) == payload_fingerprint(second)


def test_preview_contains_payload_fingerprint():
    preview = inspect_outbound_context({"snippets": []})

    assert len(preview["payload_sha256"]) == 64
    assert preview["approved"] is False


def test_approval_requires_explicit_confirmation():
    preview = inspect_outbound_context({"snippets": []})

    with pytest.raises(PermissionError):
        create_outbound_approval(
            preview,
            user_confirmed=False,
        )


def test_approval_is_bound_to_payload():
    preview = inspect_outbound_context({"snippets": []})

    approval = create_outbound_approval(
        preview,
        user_confirmed=True,
    )

    assert approval["approved"] is True
    assert verify_outbound_approval(preview, approval) is True


def test_modified_payload_invalidates_approval():
    preview = inspect_outbound_context({"snippets": []})

    approval = create_outbound_approval(
        preview,
        user_confirmed=True,
    )

    preview["payload"]["repository"] = "modified-repository"

    assert verify_outbound_approval(preview, approval) is False


def test_modified_fingerprint_invalidates_approval():
    preview = inspect_outbound_context({"snippets": []})

    approval = create_outbound_approval(
        preview,
        user_confirmed=True,
    )

    preview["payload_sha256"] = "0" * 64

    assert verify_outbound_approval(preview, approval) is False


def test_unapproved_payload_is_rejected():
    preview = inspect_outbound_context({"snippets": []})

    approval = {
        "approved": False,
        "payload_sha256": preview["payload_sha256"],
        "approval_version": 1,
    }

    assert verify_outbound_approval(preview, approval) is False
