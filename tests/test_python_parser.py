
from aegis.parsing.python_parser import parse_python_source


def test_extracts_functions_and_calls():
    source = """
def calculate(price, quantity):
    return multiply(price, quantity)

def checkout(price, quantity):
    return calculate(price, quantity)
"""
    functions = parse_python_source(source, "shop.py")
    by_name = {fn.name: fn for fn in functions}

    assert set(by_name) == {"calculate", "checkout"}
    assert by_name["calculate"].start_line == 2
    assert "multiply" in by_name["calculate"].calls
    assert "calculate" in by_name["checkout"].calls


def test_extracts_class_methods():
    source = """
class Cart:
    def total(self):
        return calculate()
"""
    functions = parse_python_source(source, "cart.py")

    assert len(functions) == 1
    assert functions[0].qualified_name == "Cart.total"
    assert "calculate" in functions[0].calls


def test_extracts_qualified_method_calls():
    source = """
class Cart:
    def checkout(self):
        self.validate()
        Cart.calculate()
        payment.calculate()
"""

    functions = parse_python_source(source, "cart.py")
    checkout = next(fn for fn in functions if fn.name == "checkout")

    assert "self.validate" in checkout.calls
    assert "Cart.calculate" in checkout.calls
    assert "payment.calculate" in checkout.calls


def test_extracts_multiple_calls_without_losing_qualification():
    source = """
def checkout():
    payment.calculate()
    tax.calculate()
    calculate()
"""

    functions = parse_python_source(source, "checkout.py")
    checkout = functions[0]

    assert set(checkout.calls) == {
        "payment.calculate",
        "tax.calculate",
        "calculate",
    }


def test_extracts_imports_and_aliases():
    source = """
import payment
import payment as p
from tax import calculate
from fees import calculate as calc

def checkout():
    payment.calculate()
    p.calculate()
    calculate()
    calc()
"""

    functions = parse_python_source(source, "checkout.py")
    checkout = next(fn for fn in functions if fn.name == "checkout")

    assert checkout.imports == {
        "payment": "payment",
        "p": "payment",
        "calculate": "tax.calculate",
        "calc": "fees.calculate",
    }


def test_resolves_single_dot_relative_import():
    source = """
from .payment import calculate

def checkout():
    return calculate()
"""

    functions = parse_python_source(
        source,
        "app/services/checkout.py",
    )

    checkout = next(
        fn for fn in functions if fn.name == "checkout"
    )

    assert checkout.imports["calculate"] == (
        "app.services.payment.calculate"
    )


def test_resolves_parent_relative_import():
    source = """
from ..utils import helper

def checkout():
    return helper()
"""

    functions = parse_python_source(
        source,
        "app/services/checkout.py",
    )

    checkout = next(
        fn for fn in functions if fn.name == "checkout"
    )

    assert checkout.imports["helper"] == "app.utils.helper"


from aegis.parsing.python_parser import parse_python_module


def test_extracts_imports_from_empty_init_file():
    source = """
from .payment import calculate
"""

    functions, imports = parse_python_module(
        source,
        "app/services/__init__.py",
    )

    assert functions == []

    assert imports == {
        "calculate": "app.services.payment.calculate"
    }
