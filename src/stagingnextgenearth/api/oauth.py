"""Google OpenID Connect authorization-code flow with state, nonce and PKCE."""

import asyncio
import base64
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Annotated, Literal
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import ExternalIdentity, IdentityActionToken, User

from .dependencies import get_session

router = APIRouter(prefix="/auth/google", tags=["authentication"])


class GoogleAuthorizationResponse(BaseModel):
    authorization_url: str


class GoogleSessionResponse(BaseModel):
    subject: str
    access_token: str
    refresh_token: str
    portal: Literal["learner", "staff"]


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@router.get("/start", response_model=GoogleAuthorizationResponse)
async def google_authorization_start(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    portal: Literal["learner", "staff"] = "staff",
) -> GoogleAuthorizationResponse:
    settings = request.app.state.settings
    if (
        not settings.google_oidc_client_id
        or settings.google_oidc_client_secret is None
        or settings.google_oidc_redirect_uri is None
    ):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(sha256(verifier.encode("ascii")).digest())
    session.add(
        IdentityActionToken(
            purpose="google_oidc_state",
            token_hash=_digest(state),
            email="",
            payload={"nonce": nonce, "code_verifier": verifier, "portal": portal},
            expires_at=datetime.now(UTC)
            + timedelta(minutes=min(settings.identity_action_token_minutes, 10)),
        )
    )
    await session.commit()
    parameters = {
        "client_id": settings.google_oidc_client_id,
        "redirect_uri": str(settings.google_oidc_redirect_uri),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return GoogleAuthorizationResponse(
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(parameters)
    )


def _verify_google_id_token(id_token: str, client_id: str, nonce: str) -> dict[str, object]:
    jwks = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs", timeout=10)
    signing_key = jwks.get_signing_key_from_jwt(id_token).key
    claims = jwt.decode(
        id_token,
        signing_key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=["https://accounts.google.com", "accounts.google.com"],
        options={"require": ["exp", "iat", "iss", "sub", "aud"]},
    )
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValueError("Google OIDC nonce validation failed")
    if claims.get("email_verified") is not True:
        raise ValueError("Google account email is not verified")
    if not isinstance(claims.get("email"), str) or not isinstance(claims.get("sub"), str):
        raise ValueError("Google identity claims are incomplete")
    return claims


@router.get("/callback", response_model=GoogleSessionResponse)
async def google_authorization_callback(
    code: str,
    state: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoogleSessionResponse:
    settings = request.app.state.settings
    if (
        not settings.google_oidc_client_id
        or settings.google_oidc_client_secret is None
        or settings.google_oidc_redirect_uri is None
    ):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google sign-in is not configured")
    state_record = await session.scalar(
        select(IdentityActionToken)
        .where(
            IdentityActionToken.purpose == "google_oidc_state",
            IdentityActionToken.token_hash == _digest(state),
            IdentityActionToken.consumed_at.is_(None),
            IdentityActionToken.revoked_at.is_(None),
        )
        .with_for_update()
    )
    state_expires_at = (
        state_record.expires_at.replace(tzinfo=UTC)
        if state_record is not None and state_record.expires_at.tzinfo is None
        else state_record.expires_at.astimezone(UTC)
        if state_record is not None
        else datetime.min.replace(tzinfo=UTC)
    )
    if state_record is None or state_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Google sign-in state is invalid or expired"
        )
    nonce = state_record.payload.get("nonce")
    verifier = state_record.payload.get("code_verifier")
    portal = state_record.payload.get("portal", "staff")
    if not isinstance(nonce, str) or not isinstance(verifier, str):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google sign-in state is incomplete")
    state_record.consumed_at = datetime.now(UTC)
    await session.commit()

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_oidc_client_id,
                    "client_secret": settings.google_oidc_client_secret.get_secret_value(),
                    "redirect_uri": str(settings.google_oidc_redirect_uri),
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str):
            raise ValueError("Google did not return an ID token")
        claims = await asyncio.to_thread(
            _verify_google_id_token, id_token, settings.google_oidc_client_id, nonce
        )
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Google sign-in could not be verified"
        ) from exc

    google_subject = str(claims["sub"])
    email = str(claims["email"]).casefold()
    external = await session.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "google",
            ExternalIdentity.provider_subject == google_subject,
        )
    )
    if external is not None:
        user = await session.get(User, external.user_id)
    else:
        user = await session.scalar(
            select(User).where(func.lower(User.identifier) == email).with_for_update()
        )
        if user is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "No platform account is associated with this verified Google email. "
                "Ask an administrator for an invitation first.",
            )
        existing_google_link = await session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.user_id == user.id,
                ExternalIdentity.provider == "google",
            )
        )
        if existing_google_link is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "A different Google identity is already linked to this account",
            )
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        session.add(
            ExternalIdentity(
                user_id=user.id,
                provider="google",
                provider_subject=google_subject,
                email=email,
            )
        )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Linked account is unavailable")
    auth_factory = getattr(request.app.state, "auth_application_factory", None)
    if auth_factory is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured")
    auth_application = auth_factory(session)
    tokens = await auth_application.refresh_token_service.issue(user.id)
    await session.commit()
    selected_portal: Literal["learner", "staff"] = "learner" if portal == "learner" else "staff"
    return GoogleSessionResponse(
        subject=tokens.subject,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        portal=selected_portal,
    )
