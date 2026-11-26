
import networkx as nx

from aegis.discovery.test_discovery import (
    discover_tests,
    to_pytest_node_id,
)


def test_discovers_directly_connected_test():
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("test_checkout", "checkout"),
        ("checkout", "calculate_total"),
    ])

    result = discover_tests(
        graph,
        {
            "test_checkout": {
                "name": "test_checkout",
                "qualified_name": "test_checkout",
                "file": "tests/test_shop.py",
            }
        },
        ["calculate_total"],
    )

    assert len(result) == 1
    assert result[0]["id"] == "test_checkout"
    assert result[0]["distance"] == 2
    assert result[0]["pytest_node_id"] == (
        "tests/test_shop.py::test_checkout"
    )


def test_ranks_closer_tests_higher():
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("test_direct", "calculate_total"),
        ("test_indirect", "checkout"),
        ("checkout", "calculate_total"),
    ])

    tests = {
        "test_direct": {
            "name": "test_direct",
            "qualified_name": "test_direct",
            "file": "tests/test_shop.py",
        },
        "test_indirect": {
            "name": "test_indirect",
            "qualified_name": "test_indirect",
            "file": "tests/test_shop.py",
        },
    }

    result = discover_tests(graph, tests, ["calculate_total"])

    assert result[0]["id"] == "test_direct"
    assert result[0]["distance"] < result[1]["distance"]


def test_does_not_include_unrelated_tests():
    graph = nx.DiGraph()
    graph.add_edge("test_payment", "process_payment")

    tests = {
        "test_payment": {
            "name": "test_payment",
            "qualified_name": "test_payment",
            "file": "tests/test_payment.py",
        },
        "test_cart": {
            "name": "test_cart",
            "qualified_name": "test_cart",
            "file": "tests/test_cart.py",
        },
    }

    result = discover_tests(graph, tests, ["calculate_total"])

    assert result == []


def test_handles_multiple_changed_functions():
    graph = nx.DiGraph()
    graph.add_edges_from([
        ("test_shop", "calculate_total"),
        ("test_tax", "calculate_tax"),
    ])

    tests = {
        "test_shop": {
            "name": "test_shop",
            "qualified_name": "test_shop",
            "file": "tests/test_shop.py",
        },
        "test_tax": {
            "name": "test_tax",
            "qualified_name": "test_tax",
            "file": "tests/test_tax.py",
        },
    }

    result = discover_tests(
        graph,
        tests,
        ["calculate_total", "calculate_tax"],
    )

    assert len(result) == 2


def test_returns_relevance_score_and_reason():
    graph = nx.DiGraph()
    graph.add_edge("test_checkout", "calculate_total")

    tests = {
        "test_checkout": {
            "name": "test_checkout",
            "qualified_name": "test_checkout",
            "file": "tests/test_shop.py",
        },
    }

    result = discover_tests(graph, tests, ["calculate_total"])

    assert "score" in result[0]
    assert "reason" in result[0]
    assert result[0]["score"] > 0


def test_converts_class_test_to_pytest_node_id():
    test_data = {
        "file": "tests/test_pricing.py",
        "qualified_name": "TestPricing.test_total",
    }

    assert to_pytest_node_id(test_data) == (
        "tests/test_pricing.py::TestPricing::test_total"
    )


def test_normalizes_windows_path():
    test_data = {
        "file": r"tests\test_pricing.py",
        "qualified_name": "test_total",
    }

    assert to_pytest_node_id(test_data) == (
        "tests/test_pricing.py::test_total"
    )
