from datetime import UTC, datetime, timedelta

import pytest

from stagingnextgenearth.auth import TokenError, TokenService


def test_access_token_round_trip() -> None:
    service = TokenService("x" * 32)
    token = service.create("user-123", timedelta(minutes=15))
    payload = service.decode(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_wrong_token_type_is_rejected() -> None:
    service = TokenService("x" * 32)
    token = service.create("user-123", timedelta(days=1), token_type="refresh")
    with pytest.raises(TokenError, match="Unexpected token type"):
        service.decode(token, expected_type="access")


def test_short_secret_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least 32"):
        TokenService("too-short")


def test_reserved_claims_cannot_be_overridden() -> None:
    service = TokenService("x" * 32)
    token = service.create(
        "user-123",
        timedelta(minutes=15),
        token_type="access",
        claims={
            "sub": "attacker",
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(days=365),
        },
    )
    payload = service.decode(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_invalid_token_parameters_are_rejected() -> None:
    service = TokenService("x" * 32)

    with pytest.raises(ValueError, match="subject"):
        service.create("", timedelta(minutes=15))
    with pytest.raises(ValueError, match="positive"):
        service.create("user-123", timedelta(0))
    with pytest.raises(ValueError, match="token_type"):
        service.create("user-123", timedelta(minutes=15), token_type="")
