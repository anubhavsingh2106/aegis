
import pytest

from aegis.ai.context import build_context_package


def make_function(symbol_id, name, source):
    return {
        "id": symbol_id,
        "file": "src/example.py",
        "name": name,
        "qualified_name": name,
        "start_line": 1,
        "end_line": 3,
        "source": source,
    }


def test_selects_changed_functions_callers_and_tests():
    report = {
        "repository": "demo",
        "base_revision": "base123",
        "head_revision": "head123",
        "changed_functions": [
            make_function("f1", "calculate", "def calculate(): pass")
        ],
        "potentially_affected_callers": [
            make_function("f2", "checkout", "def checkout(): pass")
        ],
        "candidate_tests": [
            make_function("f3", "test_checkout", "def test_checkout(): pass")
        ],
    }

    package = build_context_package(report)

    assert len(package["snippets"]) == 3
    assert [item["reason"] for item in package["snippets"]] == [
        "changed_function",
        "affected_caller",
        "candidate_test",
    ]
    assert package["policy"]["mode"] == "local_only"


def test_deduplicates_symbols():
    function = make_function("f1", "calculate", "def calculate(): pass")
    report = {
        "changed_functions": [function],
        "potentially_affected_callers": [function],
        "candidate_tests": [],
    }

    package = build_context_package(report)

    assert len(package["snippets"]) == 1
    assert package["snippets"][0]["reason"] == "changed_function"


def test_respects_source_character_budget():
    report = {
        "changed_functions": [
            make_function("f1", "calculate", "abcdefghij"),
            make_function("f2", "checkout", "klmnopqrst"),
        ],
        "potentially_affected_callers": [],
        "candidate_tests": [],
    }

    package = build_context_package(report, max_chars=12)

    assert package["policy"]["selected_source_chars"] == 12
    assert package["snippets"][0]["source"] == "abcdefghij"
    assert package["snippets"][1]["source"] == "kl"
    assert package["snippets"][1]["truncated"] is True


def test_rejects_nonpositive_budget():
    with pytest.raises(ValueError):
        build_context_package({}, max_chars=0)
