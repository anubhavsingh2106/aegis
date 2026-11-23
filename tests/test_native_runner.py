
from aegis.verification.native_runner import _classify_pytest_result


def test_passed_tests():
    assert _classify_pytest_result(0, "3 passed in 0.10s") == "passed"


def test_failed_tests():
    assert (
        _classify_pytest_result(1, "1 failed, 2 passed in 0.10s")
        == "failed"
    )


def test_collection_error_is_not_a_regression():
    output = "ERROR collecting tests/test_example.py\n1 error in 0.10s"

    assert _classify_pytest_result(2, output) == "error"


def test_missing_pytest_summary_is_an_error():
    assert _classify_pytest_result(2, "ImportError: pytest unavailable") == "error"


def test_no_tests_is_an_error():
    assert _classify_pytest_result(5, "no tests ran") == "error"
