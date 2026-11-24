
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from aegis.parsing.symbols import FunctionSymbol

LANGUAGE = Language(tspython.language())
PARSER = Parser(LANGUAGE)


def text_of(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def get_call_name(node, source: bytes) -> str | None:
    if node.type == "identifier":
        return text_of(node, source)

    if node.type == "attribute":
        obj = node.child_by_field_name("object")
        attr = node.child_by_field_name("attribute")

        if obj is None or attr is None:
            return None

        object_name = get_call_name(obj, source)

        if object_name is None:
            return None

        return f"{object_name}.{text_of(attr, source)}"

    return None


def find_calls(node, source: bytes) -> set[str]:
    calls = set()

    def visit(current):
        if current.type in {
            "function_definition",
            "class_definition",
            "lambda",
        }:
            return

        if current.type == "call":
            target = current.child_by_field_name("function")

            if target is not None:
                call_name = get_call_name(target, source)

                if call_name:
                    calls.add(call_name)

        for child in current.children:
            visit(child)

    if node is not None:
        visit(node)

    return calls


def resolve_relative_module(module: str, file: str) -> str:
    """Resolve a relative import using the importing file's path."""

    level = len(module) - len(module.lstrip("."))
    remainder = module[level:]

    package = file.replace("\\", "/").split("/")[:-1]

    if level > len(package):
        return "<unresolved>"

    if level > 1:
        package = package[:-(level - 1)]

    if remainder:
        package.extend(remainder.split("."))

    return ".".join(package)


def extract_imports(
    node,
    source: bytes,
    file: str,
) -> dict[str, str]:
    imports = {}
    ambiguous = set()

    def add_import(alias: str, target: str):
        if alias in ambiguous:
            return

        if alias in imports and imports[alias] != target:
            imports[alias] = "<ambiguous>"
            ambiguous.add(alias)
        else:
            imports[alias] = target

    def visit(current):
        if current.type == "import_statement":
            for child in current.named_children:
                if child.type == "dotted_name":
                    module = text_of(child, source)
                    add_import(module.split(".")[0], module)

                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")

                    if name_node is not None:
                        module = text_of(name_node, source)

                        alias = (
                            text_of(alias_node, source)
                            if alias_node is not None
                            else module.split(".")[0]
                        )

                        add_import(alias, module)

        elif current.type == "import_from_statement":
            module_node = current.child_by_field_name("module_name")

            if module_node is None:
                return

            module = text_of(module_node, source)

            if module.startswith("."):
                module = resolve_relative_module(module, file)

            for child in current.named_children:
                if (
                    child.start_byte == module_node.start_byte
                    and child.end_byte == module_node.end_byte
                ):
                    continue

                if child.type == "dotted_name":
                    imported = text_of(child, source)

                    add_import(
                        imported,
                        f"{module}.{imported}",
                    )

                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")

                    if name_node is not None:
                        imported = text_of(name_node, source)

                        alias = (
                            text_of(alias_node, source)
                            if alias_node is not None
                            else imported
                        )

                        add_import(
                            alias,
                            f"{module}.{imported}",
                        )

        for child in current.named_children:
            if child.type not in {
                "function_definition",
                "class_definition",
            }:
                visit(child)

    visit(node)

    return imports


def parse_python_module(
    source: str,
    file: str,
) -> tuple[list[FunctionSymbol], dict[str, str]]:
    """Parse a Python module and retain its imports and class inheritance."""

    encoded = source.encode("utf-8")
    tree = PARSER.parse(encoded)
    functions = []

    module_imports = extract_imports(
        tree.root_node,
        encoded,
        file,
    )

    def visit(node, scope=(), class_bases=()):
        if node.type == "class_definition":
            name_node = node.child_by_field_name("name")

            name = (
                text_of(name_node, encoded)
                if name_node
                else "<class>"
            )

            bases_node = node.child_by_field_name("superclasses")
            bases = []

            if bases_node is not None:
                for child in bases_node.named_children:
                    base_name = get_call_name(child, encoded)

                    if base_name:
                        bases.append(base_name)

            for child in node.children:
                visit(child, (*scope, name), tuple(bases))

            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")

            if name_node is None:
                return

            name = text_of(name_node, encoded)
            qualified_name = ".".join((*scope, name))

            start = node.start_point.row + 1
            end = node.end_point.row + 1

            body = node.child_by_field_name("body")

            functions.append(
                FunctionSymbol(
                    id=f"{file}:{qualified_name}:{start}",
                    file=file,
                    name=name,
                    qualified_name=qualified_name,
                    start_line=start,
                    end_line=end,
                    calls=sorted(find_calls(body, encoded)),
                    source=text_of(node, encoded),
                    imports=module_imports.copy(),
                    class_bases=list(class_bases),
                )
            )

            for child in node.children:
                visit(child, (*scope, name), class_bases)

            return

        for child in node.children:
            visit(child, scope, class_bases)

    visit(tree.root_node)

    return functions, module_imports


def parse_python_source(
    source: str,
    file: str,
) -> list[FunctionSymbol]:
    """Backward-compatible function-only parser."""

    functions, _ = parse_python_module(source, file)

    return functions
