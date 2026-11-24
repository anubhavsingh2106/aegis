from aegis.graph.call_graph import build_call_graph, find_affected_callers
from aegis.parsing.python_parser import parse_python_module, parse_python_source


def test_finds_direct_and_indirect_callers():
    source = """
def calculate_total():
    return 10

def checkout():
    return calculate_total()

def generate_invoice():
    return checkout()
"""
    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    changed = [
        fn.id for fn in functions if fn.name == "calculate_total"
    ]
    affected = find_affected_callers(graph, changed)

    names = {graph.nodes[node]["symbol"].name for node in affected}

    assert names == {"checkout", "generate_invoice"}


def test_does_not_connect_ambiguous_function_names():
    payment = parse_python_source(
        "def calculate(): return 10",
        "payment.py",
    )
    tax = parse_python_source(
        "def calculate(): return 20",
        "tax.py",
    )
    checkout = parse_python_source(
        "def checkout(): return calculate()",
        "checkout.py",
    )

    functions = payment + tax + checkout
    graph = build_call_graph(functions)

    checkout_fn = next(fn for fn in functions if fn.name == "checkout")

    assert graph.out_degree(checkout_fn.id) == 0


def test_resolves_self_method_call():
    source = """
class Cart:
    def calculate(self):
        return 10

    def checkout(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "cart.py")
    graph = build_call_graph(functions)

    calculate = next(
        fn for fn in functions if fn.name == "calculate"
    )
    checkout = next(
        fn for fn in functions if fn.name == "checkout"
    )

    assert graph.has_edge(checkout.id, calculate.id)


def test_resolves_aliased_module_import():
    payment = parse_python_source(
        "def calculate(): return 10",
        "payment.py",
    )

    checkout = parse_python_source(
        """
import payment as p

def checkout():
    return p.calculate()
""",
        "checkout.py",
    )

    functions = payment + checkout
    graph = build_call_graph(functions)

    calculate = payment[0]
    checkout_fn = next(fn for fn in checkout if fn.name == "checkout")

    assert graph.has_edge(checkout_fn.id, calculate.id)


def test_resolves_from_import():
    payment = parse_python_source(
        "def calculate(): return 10",
        "payment.py",
    )

    checkout = parse_python_source(
        """
from payment import calculate

def checkout():
    return calculate()
""",
        "checkout.py",
    )

    functions = payment + checkout
    graph = build_call_graph(functions)

    calculate = payment[0]
    checkout_fn = next(fn for fn in checkout if fn.name == "checkout")

    assert graph.has_edge(checkout_fn.id, calculate.id)


def test_does_not_resolve_ambiguous_imported_function():
    payment = parse_python_source(
        "def calculate(): return 10",
        "payment.py",
    )

    tax = parse_python_source(
        "def calculate(): return 20",
        "tax.py",
    )

    checkout = parse_python_source(
        """
from payment import calculate
from tax import calculate

def checkout():
    return calculate()
""",
        "checkout.py",
    )

    functions = payment + tax + checkout
    graph = build_call_graph(functions)

    checkout_fn = next(fn for fn in checkout if fn.name == "checkout")

    assert graph.out_degree(checkout_fn.id) == 0


def test_resolves_single_dot_relative_import():
    payment = parse_python_source(
        "def calculate(): return 10",
        "app/services/payment.py",
    )

    checkout = parse_python_source(
        """
from .payment import calculate

def checkout():
    return calculate()
""",
        "app/services/checkout.py",
    )

    functions = payment + checkout
    graph = build_call_graph(functions)

    assert graph.has_edge(
        checkout[0].id,
        payment[0].id,
    )


def test_resolves_parent_relative_import():
    utils = parse_python_source(
        "def helper(): return 10",
        "app/utils.py",
    )

    checkout = parse_python_source(
        """
from ..utils import helper

def checkout():
    return helper()
""",
        "app/services/checkout.py",
    )

    functions = utils + checkout
    graph = build_call_graph(functions)

    assert graph.has_edge(
        checkout[0].id,
        utils[0].id,
    )


def test_resolves_aliased_relative_import():
    payment = parse_python_source(
        "def calculate(): return 10",
        "app/services/payment.py",
    )

    checkout = parse_python_source(
        """
from .payment import calculate as calc

def checkout():
    return calc()
""",
        "app/services/checkout.py",
    )

    functions = payment + checkout
    graph = build_call_graph(functions)

    assert graph.has_edge(
        checkout[0].id,
        payment[0].id,
    )


def test_does_not_fallback_when_import_target_is_missing():
    other = parse_python_source(
        "def calculate(): return 10",
        "other.py",
    )

    checkout = parse_python_source(
        """
from missing import calculate

def checkout():
    return calculate()
""",
        "checkout.py",
    )

    functions = other + checkout
    graph = build_call_graph(functions)

    assert graph.out_degree(checkout[0].id) == 0

def test_resolves_package_reexport():
    payment_functions = parse_python_source(
        """
def calculate():
    return 100
""",
        "app/services/payment.py",
    )

    _, init_imports = parse_python_module(
        """
from .payment import calculate
""",
        "app/services/__init__.py",
    )

    main_functions = parse_python_source(
        """
from app.services import calculate

def checkout():
    return calculate()
""",
        "app/main.py",
    )

    functions = payment_functions + main_functions

    module_imports = {
        "app/services/__init__.py": init_imports,
        "app/main.py": main_functions[0].imports,
    }

    graph = build_call_graph(
        functions,
        module_imports=module_imports,
    )

    checkout = next(
        fn for fn in main_functions
        if fn.name == "checkout"
    )

    calculate = next(
        fn for fn in payment_functions
        if fn.name == "calculate"
    )

    assert graph.has_edge(checkout.id, calculate.id)


def test_does_not_resolve_unimported_function_from_another_file():
    payment = parse_python_source(
        """
def calculate():
    return 100
""",
        "payment.py",
    )

    checkout = parse_python_source(
        """
def checkout():
    return calculate()
""",
        "checkout.py",
    )

    functions = payment + checkout
    graph = build_call_graph(functions)

    checkout_fn = next(
        fn for fn in checkout
        if fn.name == "checkout"
    )

    assert graph.out_degree(checkout_fn.id) == 0


def test_resolves_methods_to_their_own_class():
    source = """
class Cart:
    def calculate(self):
        return 100

    def checkout(self):
        return self.calculate()


class Tax:
    def calculate(self):
        return 20

    def apply(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    cart_calculate = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.calculate"
    )

    cart_checkout = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.checkout"
    )

    tax_calculate = next(
        fn for fn in functions
        if fn.qualified_name == "Tax.calculate"
    )

    tax_apply = next(
        fn for fn in functions
        if fn.qualified_name == "Tax.apply"
    )

    assert graph.has_edge(cart_checkout.id, cart_calculate.id)
    assert graph.has_edge(tax_apply.id, tax_calculate.id)

    assert not graph.has_edge(cart_checkout.id, tax_calculate.id)
    assert not graph.has_edge(tax_apply.id, cart_calculate.id)


def test_resolves_inherited_method_call():
    source = """
class Base:
    def calculate(self):
        return 100


class Cart(Base):
    def checkout(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    calculate = next(
        fn for fn in functions
        if fn.qualified_name == "Base.calculate"
    )

    checkout = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.checkout"
    )

    assert graph.has_edge(checkout.id, calculate.id)

def test_child_method_overrides_parent_method():
    source = """
class Base:
    def calculate(self):
        return 100


class Cart(Base):
    def calculate(self):
        return 200

    def checkout(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    calculate_methods = {
        fn.qualified_name: fn
        for fn in functions
        if fn.name == "calculate"
    }

    checkout = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.checkout"
    )

    assert graph.has_edge(
        checkout.id,
        calculate_methods["Cart.calculate"].id,
    )

    assert not graph.has_edge(
        checkout.id,
        calculate_methods["Base.calculate"].id,
    )


def test_resolves_multi_level_inherited_method_call():
    source = """
class Entity:
    def calculate(self):
        return 100


class BaseCart(Entity):
    pass


class Cart(BaseCart):
    def checkout(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    calculate = next(
        fn for fn in functions
        if fn.qualified_name == "Entity.calculate"
    )

    checkout = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.checkout"
    )

    assert graph.has_edge(checkout.id, calculate.id)


def test_does_not_resolve_method_from_unrelated_class():
    source = """
class Base:
    def calculate(self):
        return 100


class Unrelated:
    def calculate(self):
        return 200


class Cart:
    def checkout(self):
        return self.calculate()
"""

    functions = parse_python_source(source, "shop.py")
    graph = build_call_graph(functions)

    checkout = next(
        fn for fn in functions
        if fn.qualified_name == "Cart.checkout"
    )

    unrelated = next(
        fn for fn in functions
        if fn.qualified_name == "Unrelated.calculate"
    )

    assert not graph.has_edge(checkout.id, unrelated.id)
