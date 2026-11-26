
import re


def parse_pytest_failures(output: str) -> list[dict]:
    """Extract structured failure information from pytest output."""

    failures = []

    failure_pattern = re.compile(
        r"_{5,}\s+(?P<test>.+?)\s+_{5,}\n"
        r"(?P<body>.*?)(?=\n_{5,}\s+.+?\s+_{5,}|\n=+ short test summary info =+|\Z)",
        re.DOTALL,
    )

    for match in failure_pattern.finditer(output):
        test_name = match.group("test").strip()
        body = match.group("body").strip()

        evaluated_assertion = re.search(
            r"^\s*E\s+assert\s+(?P<actual>.+?)\s*==\s*(?P<expected>.+)$",
            body,
            re.MULTILINE,
        )

        failure_type = "unknown"
        expected = None
        actual = None

        if "AssertionError" in body or evaluated_assertion:
            failure_type = "assertion_error"

        if evaluated_assertion:
            actual = evaluated_assertion.group("actual").strip()
            expected = evaluated_assertion.group("expected").strip()

        message = None

        if evaluated_assertion:
            message = (
                f"assert {actual} == {expected}"
            )
        else:
            for line in body.splitlines():
                line = line.strip()

                if line.startswith("E   "):
                    message = line[4:].strip()
                    break

        failures.append(
            {
                "test": test_name,
                "failure_type": failure_type,
                "expected": expected,
                "actual": actual,
                "message": message,
                "traceback": body,
            }
        )

    return failures
