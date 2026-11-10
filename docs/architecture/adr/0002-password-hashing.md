# ADR 0002: Password Hashing Strategy

## Status

Accepted

## Context

The identity layer needs a password-hashing primitive before registration and
login flows can safely persist credentials. Passwords must never be stored in
plaintext or protected with a general-purpose fast hash.

The backbone is intended to provide reusable infrastructure while keeping the
identity domain extensible. The hashing mechanism therefore needs a small,
stable boundary that does not couple user persistence to a particular database
model.

## Decision

Use `pwdlib` with its recommended Argon2-backed configuration behind the
`stagingnextgenearth.auth.PasswordHasher` abstraction.

The abstraction exposes only the operations required by an identity module:

- `hash(password)` for creating a salted encoded password hash;
- `verify(password, password_hash)` for credential verification; and
- `needs_rehash(password_hash)` for detecting hashes that should be upgraded
  when the configured hashing parameters change.

The application identity layer is responsible for persistence and credential
policy. The backbone does not define a user model, password-reset workflow,
login endpoint, or account policy in this change.

## Consequences

- Password hashing is deliberately separated from user persistence.
- Argon2 is used instead of a fast general-purpose digest.
- Encoded hashes remain self-describing through the hashing library's format,
  allowing parameter upgrades without changing the persistence contract.
- The dependency becomes part of the core authentication primitive and is
  therefore installed with the package rather than only as a development extra.
- Registration, login, refresh-token rotation, revocation, rate limiting, and
  other identity behavior remain separate follow-up work.

## Security requirements

Consumers must never log, serialize, or persist plaintext passwords. Successful
credential verification should be followed by a `needs_rehash()` check when
appropriate, with the upgraded hash persisted atomically with the identity
record.
