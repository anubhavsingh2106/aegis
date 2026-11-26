
from aegis.verification.failure_parser import parse_pytest_failures


def test_parses_assertion_failure():
    output = """
____________________________ test_calculate_total ____________________________

    def test_calculate_total():
>       assert calculate_total(10, 2) == 20
E       assert 12 == 20

tests/test_pricing.py:5: AssertionError
"""

    failures = parse_pytest_failures(output)

    assert len(failures) == 1

    failure = failures[0]

    assert failure["test"] == "test_calculate_total"
    assert failure["failure_type"] == "assertion_error"
    assert failure["expected"] == "20"
    assert failure["actual"] == "12"
    assert failure["message"] == "assert 12 == 20"


def test_returns_empty_list_without_failures():
    output = "1 passed in 0.03s"

    assert parse_pytest_failures(output) == []


def test_preserves_traceback():
    output = """
____________________________ test_example ____________________________

    def test_example():
>       assert 5 == 10
E       assert 5 == 10

tests/test_example.py:4: AssertionError
"""

    failures = parse_pytest_failures(output)

    assert "tests/test_example.py:4" in failures[0]["traceback"]

def test_extracts_primary_assertion_message():
    output = """
____________________________ test_calculate_total ____________________________

    def test_calculate_total():
>       assert calculate_total(10, 2) == 20
E       assert 12 == 20
E        +  where 12 = calculate_total(10, 2)

tests/test_pricing.py:5: AssertionError
"""

    failures = parse_pytest_failures(output)

    assert failures[0]["message"] == "assert 12 == 20"