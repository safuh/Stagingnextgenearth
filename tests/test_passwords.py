import pytest

from stagingnextgenearth.auth import PasswordHasher


def test_password_hash_round_trip() -> None:
    hasher = PasswordHasher()
    password = "correct horse battery staple"

    password_hash = hasher.hash(password)

    assert password_hash != password
    assert hasher.verify(password, password_hash)
    assert not hasher.verify("wrong password", password_hash)


def test_password_hashes_are_salted() -> None:
    hasher = PasswordHasher()
    password = "same password"

    first = hasher.hash(password)
    second = hasher.hash(password)

    assert first != second
    assert hasher.verify(password, first)
    assert hasher.verify(password, second)


def test_malformed_hash_is_not_accepted() -> None:
    hasher = PasswordHasher()

    assert not hasher.verify("password", "not-a-password-hash")


def test_needs_rehash_accepts_current_hash() -> None:
    hasher = PasswordHasher()
    password_hash = hasher.hash("password")

    assert not hasher.needs_rehash(password_hash)


def test_non_string_password_is_rejected() -> None:
    hasher = PasswordHasher()

    with pytest.raises((TypeError, ValueError)):
        hasher.hash(None)  # type: ignore[arg-type]
