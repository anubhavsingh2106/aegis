
from aegis.ai.context import redact_secrets


def test_redacts_api_key_assignment():
    source = 'API_KEY = "example-secret-value"'

    result = redact_secrets(source)

    assert "example-secret-value" not in result
    assert "[REDACTED]" in result


def test_redacts_password_assignment():
    source = "password = supersecret123"

    result = redact_secrets(source)

    assert "supersecret123" not in result
    assert "[REDACTED]" in result


def test_redacts_bearer_token():
    source = "Authorization: Bearer abc.def.ghi"

    result = redact_secrets(source)

    assert "abc.def.ghi" not in result
    assert "[REDACTED]" in result


def test_preserves_normal_code():
    source = "total = price * quantity"

    assert redact_secrets(source) == source


def test_preserves_quotes_after_redaction():
    source = 'API_KEY = "my-secret-value"'

    result = redact_secrets(source)

    assert result == 'API_KEY = "[REDACTED]"'


def test_redacts_github_token():
    source = "token = ghp_12345678901234567890"

    result = redact_secrets(source)

    assert "ghp_12345678901234567890" not in result
    assert "[REDACTED]" in result


def test_redacts_aws_access_key():
    source = "AWS_ACCESS_KEY = AKIAIOSFODNN7EXAMPLE"

    result = redact_secrets(source)

    assert "AKIAIOSFODNN7EXAMPLE" not in result


def test_preserves_normal_strings():
    source = 'message = "hello world"'

    assert redact_secrets(source) == source


def test_redacts_multiple_secrets():
    source = (
        'API_KEY = "secret123"\n'
        "password = mypassword123\\n"
        "Authorization: Bearer abc.def.ghi"
    )

    result = redact_secrets(source)

    assert "secret123" not in result
    assert "mypassword123" not in result
    assert "abc.def.ghi" not in result

