"""Security regression tests for authentication boundaries."""

from datetime import timedelta

from stagingnextgenearth.auth.tokens import TokenError, TokenService

SECRET = "test-secret-key-that-is-at-least-32-bytes"


def test_token_protects_security_claims_from_custom_claim_override() -> None:
    service = TokenService(SECRET)

    token = service.create(
        "user-123",
        timedelta(minutes=15),
        token_type="access",
        claims={
            "sub": "attacker",
            "iat": 0,
            "exp": 0,
            "type": "refresh",
        },
    )

    payload = service.decode(token, expected_type="access")

    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["iat"] != 0


def test_tampered_token_is_rejected() -> None:
    service = TokenService(SECRET)
    token = service.create("user-123", timedelta(minutes=15))
    tampered_token = token[:-1] + ("A" if token[-1] != "A" else "B")

    try:
        service.decode(tampered_token)
    except TokenError as exc:
        assert str(exc) == "Invalid or expired token"
    else:
        raise AssertionError("Tampered token was accepted")


def test_refresh_token_cannot_be_accepted_as_access_token() -> None:
    service = TokenService(SECRET)
    token = service.create(
        "user-123",
        timedelta(days=7),
        token_type="refresh",
    )

    try:
        service.decode(token, expected_type="access")
    except TokenError as exc:
        assert str(exc) == "Unexpected token type"
    else:
        raise AssertionError("Refresh token was accepted as an access token")


def test_access_token_cannot_be_accepted_as_refresh_token() -> None:
    service = TokenService(SECRET)
    token = service.create("user-123", timedelta(minutes=15), token_type="access")

    try:
        service.decode(token, expected_type="refresh")
    except TokenError as exc:
        assert str(exc) == "Unexpected token type"
    else:
        raise AssertionError("Access token was accepted as a refresh token")


def test_short_jwt_secret_is_rejected() -> None:
    try:
        TokenService("too-short")
    except ValueError as exc:
        assert str(exc) == "JWT secret_key must contain at least 32 characters"
    else:
        raise AssertionError("Short JWT secret was accepted")
