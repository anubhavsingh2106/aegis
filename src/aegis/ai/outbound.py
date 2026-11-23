
import hashlib
import hmac
import json
from typing import Any

from aegis.ai.context import redact_secrets


def payload_fingerprint(payload: dict[str, Any]) -> str:
    """Calculate a deterministic SHA-256 fingerprint of a payload."""

    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary")

    try:
        canonical_payload = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Payload must contain JSON-serializable data") from exc

    return hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def inspect_outbound_context(
    package: dict[str, Any],
) -> dict[str, Any]:
    """Prepare a redacted outbound preview without sending any data."""

    if not isinstance(package, dict):
        raise TypeError("Context package must be a dictionary")

    snippets = package.get("snippets", [])

    if not isinstance(snippets, list):
        raise TypeError("Invalid context package: snippets must be a list")

    safe_snippets = []

    for snippet in snippets:
        if not isinstance(snippet, dict):
            raise TypeError("Invalid context package: invalid snippet")

        source = snippet.get("source", "")

        if not isinstance(source, str):
            raise TypeError("Invalid context package: invalid source")

        safe_snippets.append(
            {
                "id": snippet.get("id"),
                "file": snippet.get("file"),
                "name": snippet.get("name"),
                "start_line": snippet.get("start_line"),
                "end_line": snippet.get("end_line"),
                "reason": snippet.get("reason"),
                "source": redact_secrets(source),
            }
        )

    payload = {
        "schema_version": 1,
        "repository": package.get("repository"),
        "base_revision": package.get("base_revision"),
        "head_revision": package.get("head_revision"),
        "snippets": safe_snippets,
    }

    fingerprint = payload_fingerprint(payload)

    return {
        "destination": None,
        "approval_required": True,
        "approved": False,
        "send_enabled": False,
        "network_requests": 0,
        "payload_sha256": fingerprint,
        "payload": payload,
    }


def create_outbound_approval(
    preview: dict[str, Any],
    *,
    user_confirmed: bool,
) -> dict[str, Any]:
    """Create an approval record for the exact inspected payload."""

    if user_confirmed is not True:
        raise PermissionError("Explicit user approval is required")

    if not isinstance(preview, dict):
        raise TypeError("Preview must be a dictionary")

    payload = preview.get("payload")
    stored_fingerprint = preview.get("payload_sha256")

    if not isinstance(payload, dict):
        raise TypeError("Preview has no valid payload")

    current_fingerprint = payload_fingerprint(payload)

    if not isinstance(stored_fingerprint, str) or not hmac.compare_digest(
        stored_fingerprint,
        current_fingerprint,
    ):
        raise PermissionError("Preview payload integrity check failed")

    return {
        "approved": True,
        "payload_sha256": current_fingerprint,
        "approval_version": 1,
    }


def verify_outbound_approval(
    preview: dict[str, Any],
    approval: dict[str, Any],
) -> bool:
    """Verify approval against the current payload before any transmission."""

    if not isinstance(preview, dict) or not isinstance(approval, dict):
        return False

    if approval.get("approved") is not True:
        return False

    if approval.get("approval_version") != 1:
        return False

    payload = preview.get("payload")
    stored_fingerprint = preview.get("payload_sha256")
    approved_fingerprint = approval.get("payload_sha256")

    if not isinstance(payload, dict):
        return False

    if not isinstance(stored_fingerprint, str):
        return False

    if not isinstance(approved_fingerprint, str):
        return False

    current_fingerprint = payload_fingerprint(payload)

    return (
        hmac.compare_digest(stored_fingerprint, current_fingerprint)
        and hmac.compare_digest(approved_fingerprint, current_fingerprint)
    )
