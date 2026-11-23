
import re
from collections import Counter
from typing import Any

SECRET_ASSIGNMENT = re.compile(
    r"""(?i)(\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|"""
    r"""client[_-]?secret|password|secret[_-]?key|"""
    r"""private[_-]?key|refresh[_-]?token)\b[ \t]*[:=][ \t]*)"""
    r"""(["']?)([^"'\s,;#]+)(["']?)"""
)

SECRET_PATTERNS = [
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def redact_secrets(source: str) -> str:
    """Redact common credentials while preserving surrounding syntax."""

    def replace_assignment(match: re.Match) -> str:
        return (
            match.group(1)
            + match.group(2)
            + "[REDACTED]"
            + match.group(4)
        )

    source = SECRET_ASSIGNMENT.sub(replace_assignment, source)

    for pattern in SECRET_PATTERNS:
        source = pattern.sub("[REDACTED]", source)

    return source


def build_context_package(
    report: dict[str, Any],
    max_chars: int = 12000,
) -> dict[str, Any]:
    """Build a limited, redacted context package from an Aegis report."""

    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero")

    selected = []
    seen = set()

    priorities = [
        ("changed_functions", "changed_function"),
        ("potentially_affected_callers", "affected_caller"),
        ("candidate_tests", "candidate_test"),
    ]

    for section, reason in priorities:
        for item in report.get(section, []):
            if not isinstance(item, dict):
                continue

            item_id = str(
                item.get("id")
                or f"{item.get('file')}:{item.get('name')}"
            )

            if item_id in seen:
                continue

            seen.add(item_id)
            selected.append((item, reason))

    snippets = []
    remaining = max_chars

    for item, reason in selected:
        if remaining <= 0:
            break

        source = item.get("source", "")

        if not isinstance(source, str) or not source:
            continue

        original_length = len(source)
        selected_source = source[:remaining]

        snippets.append(
            {
                "id": item.get("id"),
                "file": item.get("file"),
                "name": item.get("name"),
                "qualified_name": item.get("qualified_name"),
                "start_line": item.get("start_line"),
                "end_line": item.get("end_line"),
                "reason": reason,
                "source": redact_secrets(selected_source),
                "truncated": original_length > remaining,
            }
        )

        remaining -= min(original_length, remaining)

    reason_counts = Counter(
        snippet["reason"] for snippet in snippets
    )

    selected_chars = max_chars - remaining

    return {
        "schema_version": 1,
        "repository": report.get("repository"),
        "base_revision": report.get("base_revision"),
        "head_revision": report.get("head_revision"),
        "policy": {
            "mode": "local_only",
            "destination": "local_only",
            "approval_required": True,
            "automatic_upload": False,
            "selected_source_chars": selected_chars,
        },
        "summary": {
            "snippet_count": len(snippets),
            "characters_used": selected_chars,
            "characters_limit": max_chars,
            "reasons": dict(reason_counts),
        },
        "snippets": snippets,
    }
