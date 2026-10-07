import json

import pytest

from app.ai.context.redactor import redact


@pytest.mark.parametrize(
    "value",
    [
        "password=CANARY",
        "password = 'CANARY'",
        '"password": "CANARY"',
        "Authorization: Bearer CANARY",
        "Authorization: Basic CANARY",
        '"Authorization": "Bearer CANARY"',
        '"Cookie": "session=CANARY"',
        "AUTH PLAIN CANARY",
        "api_key=CANARY",
        "API-token:CANARY",
        "Cookie: session=CANARY; other=CANARY",
        "session_id=CANARY",
        "cowrie_password=CANARY",
        "smtp_password=CANARY",
        "postgresql://user:CANARY@database/service",
        "smtp://user:CANARY@mail/service",
        "-----BEGIN PRIVATE KEY-----\nCANARY\n-----END PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----\nCANARY",
        {"credentials": {"value": "CANARY"}},
        {"captured_password": "CANARY", "nested": [{"sessionId": "CANARY"}]},
    ],
)
def test_required_secret_patterns(value):
    result = json.dumps(redact(value))
    assert "CANARY" not in result
    assert "REDACTED" in result


def test_jwt_and_api_token():
    assert "eyJ" not in redact("eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZGVtbyJ9.testSignature")
    assert "sk-" not in redact("sk-syntheticCanaryToken123")


def test_normal_evidence_ids_preserved():
    value = {"incident_id": "SZ-000042", "event_uid": "EVT-001", "summary": "test process observed"}
    assert redact(value) == value
