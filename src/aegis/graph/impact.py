from pathlib import Path

from aegis.discovery.test_discovery import discover_tests
from aegis.git_analysis.diff import analyze_diff
from aegis.graph.call_graph import build_call_graph, find_affected_callers
from aegis.parsing.python_parser import parse_python_module

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".pytest_cache",
}


def analyze_impact(repo: str, base: str, head: str = "HEAD") -> dict:
    repo_path = Path(repo).resolve()
    diff = analyze_diff(str(repo_path), base, head)

    functions = []
    module_imports = {}

    for path in repo_path.rglob("*.py"):
        relative = path.relative_to(repo_path)

        if any(part in SKIP_DIRS for part in relative.parts):
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        parsed_functions, imports = parse_python_module(
            source,
            relative.as_posix(),
        )

        functions.extend(parsed_functions)
        module_imports[relative.as_posix()] = imports

    graph = build_call_graph(
        functions,
        module_imports=module_imports,
    )

    changed_functions = []

    for change in diff["files"]:
        if change["new_file"] is None:
            continue

        changed_ranges = change["added_lines"]

        for fn in functions:
            if fn.file != change["new_file"]:
                continue

            if any(
                fn.start_line <= line["end"]
                and fn.end_line >= line["start"]
                for line in changed_ranges
            ):
                changed_functions.append(fn.id)

    changed_functions = sorted(set(changed_functions))
    affected = find_affected_callers(graph, changed_functions)

    by_id = {fn.id: fn for fn in functions}

    test_functions = {
        fn.id: fn.to_dict()
        for fn in functions
        if fn.name.startswith("test_")
    }

    candidate_tests = discover_tests(
        graph,
        test_functions,
        changed_functions,
    )

    return {
        "repository": str(repo_path),
        "base_revision": diff["base_revision"],
        "head_revision": diff["head_revision"],
        "changed_files": diff["files"],
        "changed_functions": [
            by_id[symbol_id].to_dict()
            for symbol_id in changed_functions
        ],
        "potentially_affected_callers": [
            by_id[symbol_id].to_dict()
            for symbol_id in affected
        ],
        "candidate_tests": candidate_tests,
        "graph": {
            "nodes": [
                {"id": fn.id, "file": fn.file, "name": fn.name}
                for fn in functions
            ],
            "edges": [
                {"caller": caller, "callee": callee}
                for caller, callee in graph.edges()
            ],
        },
    }
