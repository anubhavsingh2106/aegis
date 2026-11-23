
import networkx as nx

from aegis.parsing.symbols import FunctionSymbol


def _unique_target(candidates):
    if len(candidates) == 1:
        return candidates[0]

    return None


def _module_name(file):
    module = file.replace("\\", "/")

    if module.endswith("/__init__.py"):
        module = module[:-12]
    elif module == "__init__.py":
        module = ""
    elif module.endswith(".py"):
        module = module[:-3]

    return module.strip("/").replace("/", ".")


def _resolve_canonical_target(
    target,
    by_module_and_name,
    module_imports_by_name,
):
    visited = set()

    while target and target not in visited:
        visited.add(target)

        module, separator, name = target.rpartition(".")

        if not separator:
            return None

        imports = module_imports_by_name.get(module, {})
        imported_target = imports.get(name)

        if imported_target in {"<ambiguous>", "<unresolved>"}:
            return None

        if imported_target:
            target = imported_target
            continue

        return _unique_target(
            by_module_and_name.get((module, name), [])
        )

    return None


def _resolve_imported_call(
    caller,
    call,
    by_module_and_name,
    module_imports_by_name,
):
    alias, separator, suffix = call.partition(".")

    if alias not in caller.imports:
        return None

    imported = caller.imports[alias]

    if imported in {"<ambiguous>", "<unresolved>"}:
        return None

    if separator:
        imported = f"{imported}.{suffix}"

    return _resolve_canonical_target(
        imported,
        by_module_and_name,
        module_imports_by_name,
    )


def _resolve_call(
    caller,
    call,
    by_qualified_name,
    by_name,
    by_module_and_name,
    module_imports_by_name,
):
    alias = call.split(".", 1)[0]

    if alias in caller.imports:
        return _resolve_imported_call(
            caller,
            call,
            by_module_and_name,
            module_imports_by_name,
        )

    if call.startswith(("self.", "cls.")):
        parts = caller.qualified_name.split(".")

        if len(parts) >= 2:
            class_name = parts[-2]
            method_name = call.split(".", 1)[1]

            candidates = [
                fn
                for fn in by_qualified_name.get(
                    f"{class_name}.{method_name}", []
                )
                if fn.file == caller.file
            ]

            return _unique_target(candidates)

        return None

    if "." in call:
        return _unique_target(by_qualified_name.get(call, []))

    same_file = [
        fn for fn in by_name.get(call, [])
        if fn.file == caller.file
    ]

    if same_file:
        return _unique_target(same_file)

    return _unique_target(by_name.get(call, []))


def build_call_graph(
    functions: list[FunctionSymbol],
    module_imports: dict[str, dict[str, str]] | None = None,
) -> nx.DiGraph:
    graph = nx.DiGraph()

    by_name = {}
    by_qualified_name = {}
    by_module_and_name = {}
    module_imports_by_name = {}

    module_imports = module_imports or {}

    for file, imports in module_imports.items():
        module = _module_name(file)
        module_imports_by_name[module] = imports

    for fn in functions:
        graph.add_node(fn.id, symbol=fn)

        by_name.setdefault(fn.name, []).append(fn)

        by_qualified_name.setdefault(
            fn.qualified_name, []
        ).append(fn)

        module = _module_name(fn.file)

        by_module_and_name.setdefault(
            (module, fn.name), []
        ).append(fn)

    for caller in functions:
        for call in caller.calls:
            target = _resolve_call(
                caller,
                call,
                by_qualified_name,
                by_name,
                by_module_and_name,
                module_imports_by_name,
            )

            if target is not None:
                graph.add_edge(caller.id, target.id)

    return graph


def find_affected_callers(graph, changed_ids):
    affected = set()

    for symbol_id in changed_ids:
        if symbol_id in graph:
            affected.update(
                nx.ancestors(graph, symbol_id)
            )

    affected.difference_update(changed_ids)

    return sorted(affected)
