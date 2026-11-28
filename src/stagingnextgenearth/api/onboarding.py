"""Invitation-first onboarding and account recovery endpoints."""

import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from html import escape
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.auth import AuthenticationError, LoginRequest, PasswordHasher
from stagingnextgenearth.core.errors import BackboneError
from stagingnextgenearth.identity.models import IdentityActionToken, User
from stagingnextgenearth.identity.refresh_tokens import RefreshToken
from stagingnextgenearth.platform.models import (
    LearningCohort,
    LearningCourse,
    LearningEnrollment,
    Membership,
    MembershipRole,
    Organization,
    OrganizationAuditEvent,
    Programme,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["identity-onboarding"])
_audit_logger = structlog.get_logger("stagingnextgenearth.audit")
InvitableRole = Literal[
    "admin",
    "founder",
    "executive",
    "programme_manager",
    "researcher",
    "youth_volunteer",
    "employee",
    "institutional_partner",
    "funder",
    "learner",
]


class InvitationCreate(BaseModel):
    email: str = Field(min_length=6, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    roles: list[InvitableRole] = Field(min_length=1, max_length=6)
    expires_in_hours: int = Field(default=168, ge=1, le=720)
    programme_id: str | None = Field(default=None, max_length=36)
    course_id: str | None = Field(default=None, max_length=36)
    cohort_id: str | None = Field(default=None, max_length=36)
    message: str | None = Field(default=None, max_length=1000)


class InvitationRead(BaseModel):
    id: str
    email: str
    roles: list[str]
    status: str
    expires_at: datetime
    created_at: datetime
    invitation_url: str | None = None


class InvitationAccept(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class InvitationSessionResponse(BaseModel):
    subject: str
    access_token: str
    refresh_token: str
    roles: list[str]
    organization_id: str


class TokenActionRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=6, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordResetConfirm(TokenActionRequest):
    new_password: str = Field(min_length=12, max_length=256)


class EmailChangeRequest(BaseModel):
    new_email: str = Field(min_length=6, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    current_password: str = Field(min_length=1, max_length=256)


class ActionMessage(BaseModel):
    message: str


def _normalise_email(value: str) -> str:
    return value.strip().casefold()


def _token_digest(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def _issue_action_token(
    session: AsyncSession,
    *,
    purpose: str,
    email: str,
    user_id: str | None = None,
    organization_id: str | None = None,
    created_by_user_id: str | None = None,
    payload: dict[str, object] | None = None,
    expires_at: datetime,
) -> tuple[IdentityActionToken, str]:
    now = datetime.now(UTC)
    token_statement = select(IdentityActionToken).where(
        IdentityActionToken.purpose == purpose,
        IdentityActionToken.email == email,
        IdentityActionToken.organization_id == organization_id,
        IdentityActionToken.consumed_at.is_(None),
        IdentityActionToken.revoked_at.is_(None),
    )
    if purpose != "invitation":
        token_statement = token_statement.where(IdentityActionToken.user_id == user_id)
    existing = await session.scalars(token_statement.with_for_update())
    for item in existing.all():
        item.revoked_at = now
    raw = secrets.token_urlsafe(40)
    record = IdentityActionToken(
        purpose=purpose,
        token_hash=_token_digest(raw),
        user_id=user_id,
        organization_id=organization_id,
        email=email,
        payload=payload or {},
        expires_at=expires_at,
        created_by_user_id=created_by_user_id,
    )
    session.add(record)
    await session.flush()
    return record, raw


async def _active_token(session: AsyncSession, raw_token: str, purpose: str) -> IdentityActionToken:
    record = await session.scalar(
        select(IdentityActionToken)
        .where(
            IdentityActionToken.token_hash == _token_digest(raw_token),
            IdentityActionToken.purpose == purpose,
            IdentityActionToken.consumed_at.is_(None),
            IdentityActionToken.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if record is None or _aware(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This link is invalid or has expired")
    return record


async def _send_action_email(
    request: Request,
    *,
    recipient: str,
    subject: str,
    path: str,
    raw_token: str,
    intro: str,
    message: str | None = None,
) -> bool:
    sender = getattr(request.app.state, "email_sender", None)
    if sender is None:
        return False
    base = str(request.app.state.settings.public_base_url).rstrip("/")
    url = f"{base}{path}#token={raw_token}"
    safe_intro = escape(intro)
    safe_message = f"<p>{escape(message)}</p>" if message else ""
    text_body = (
        f"{intro}\n\n{message or ''}\n\nContinue securely: {url}\n\n"
        "If you did not expect this message, you can ignore it."
    )
    html_body = (
        "<div style='font-family:Arial,sans-serif;max-width:600px;margin:auto'>"
        f"<p>{safe_intro}</p>{safe_message}"
        f"<p><a href='{escape(url, quote=True)}'>Continue securely</a></p>"
        "<p>If you did not expect this message, you can ignore it.</p></div>"
    )
    await sender.send(recipient, subject, text_body, html_body)
    return True


@router.post(
    "/organizations/{organization_id}/onboarding-invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_onboarding_invitation(
    organization_id: str,
    body: InvitationCreate,
    request: Request,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvitationRead:
    """Create an expiring role-scoped invitation for a new or existing email identity."""
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    roles: list[str] = list(dict.fromkeys(body.roles))
    if not roles:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "At least one role is required")
    if set(roles) & {"admin", "founder", "executive"}:
        owner_id = await session.scalar(
            select(Organization.owner_user_id).where(Organization.id == organization_id)
        )
        if owner_id != membership.user_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Only the owner can invite administrator or executive roles",
            )
    email = _normalise_email(str(body.email))
    user = await session.scalar(select(User).where(func.lower(User.identifier) == email))
    if user is not None:
        existing_membership = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == user.id,
            )
        )
        if existing_membership is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "An organisation membership already exists"
            )
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    if body.programme_id is not None:
        programme = await session.scalar(
            select(Programme).where(
                Programme.id == body.programme_id,
                Programme.organization_id == organization_id,
            )
        )
        if programme is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Programme not found in this organisation"
            )
    if body.course_id is not None:
        course = await session.scalar(
            select(LearningCourse).where(
                LearningCourse.id == body.course_id,
                LearningCourse.organization_id == organization_id,
                LearningCourse.status == "published",
            )
        )
        if course is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Published course not found in this organisation"
            )
        if body.programme_id and course.programme_id != body.programme_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Course does not belong to the selected programme",
            )
    if body.cohort_id is not None:
        cohort = await session.scalar(
            select(LearningCohort).where(
                LearningCohort.id == body.cohort_id,
                LearningCohort.organization_id == organization_id,
                LearningCohort.status.in_({"open", "active"}),
            )
        )
        if cohort is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Open cohort not found in this organisation"
            )
        if body.programme_id and cohort.programme_id != body.programme_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Cohort does not belong to the selected programme",
            )
        if body.course_id and course is not None and course.programme_id != cohort.programme_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Course and cohort programmes do not match"
            )
    if body.programme_id is not None and body.course_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A learner programme scope must include a published course",
        )
    if body.cohort_id is not None and body.course_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A cohort invitation must include a published course",
        )
    if (body.programme_id or body.course_id or body.cohort_id) and set(roles) - {"learner"}:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Programme and course scopes currently apply to learner-only invitations",
        )
    if body.course_id is not None and "learner" not in roles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Course scope can only be assigned to a learner"
        )
    scope = {
        key: value
        for key, value in {
            "programme_id": body.programme_id,
            "course_id": body.course_id,
            "cohort_id": body.cohort_id,
        }.items()
        if value is not None
    }
    record, raw = await _issue_action_token(
        session,
        purpose="invitation",
        email=email,
        user_id=user.id if user else None,
        organization_id=organization_id,
        created_by_user_id=membership.user_id,
        payload={"roles": roles, "scope": scope},
        expires_at=datetime.now(UTC) + timedelta(hours=body.expires_in_hours),
    )
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=membership.user_id,
            subject_user_id=user.id if user else None,
            action="membership.invited",
            changes={"email": email, "roles": roles, "invitation_id": record.id},
        )
    )
    await session.commit()
    delivered = False
    try:
        delivered = await _send_action_email(
            request,
            recipient=email,
            subject=f"Invitation to {organization.name} on NextGen for Earth",
            path="/onboarding/accept",
            raw_token=raw,
            intro=f"You have been invited to join {organization.name}.",
            message=body.message,
        )
    except Exception:
        _audit_logger.warning(
            "identity_email_delivery",
            audit_action="invitation_delivery",
            audit_outcome="failure",
            invitation_id=record.id,
            organization_id=organization_id,
        )
    manual_link_allowed = (
        request.app.state.settings.identity_manual_invitation_links_enabled
        and request.app.state.settings.deployment_stage.value == "staging"
    )
    delivery_status = (
        "delivered" if delivered else "manual_link_ready" if manual_link_allowed else "failed"
    )
    record.payload = {**record.payload, "delivery_status": delivery_status}
    await session.commit()
    if (
        not delivered
        and not manual_link_allowed
        and request.app.state.settings.environment.value == "production"
    ):
        raise BackboneError(
            "invitation_delivery_unavailable",
            "Invitation was recorded, but email delivery is unavailable. "
            "Configure SMTP and resend the invitation.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return InvitationRead(
        id=record.id,
        email=email,
        roles=roles,
        status="delivered" if delivered else "pending_delivery",
        expires_at=record.expires_at,
        created_at=record.created_at or datetime.now(UTC),
        invitation_url=(
            f"{str(request.app.state.settings.public_base_url).rstrip('/')}/onboarding/accept#token={raw}"
            if not delivered
            else None
        ),
    )


@router.get(
    "/organizations/{organization_id}/onboarding-invitations",
    response_model=list[InvitationRead],
)
async def list_onboarding_invitations(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[InvitationRead]:
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    rows = await session.scalars(
        select(IdentityActionToken)
        .where(
            IdentityActionToken.organization_id == organization_id,
            IdentityActionToken.purpose == "invitation",
        )
        .order_by(IdentityActionToken.created_at.desc())
        .limit(200)
    )
    result: list[InvitationRead] = []
    now = datetime.now(UTC)
    for item in rows.all():
        state = (
            "revoked"
            if item.revoked_at
            else "accepted"
            if item.consumed_at
            else ("expired" if _aware(item.expires_at) <= now else "pending")
        )
        roles = item.payload.get("roles", [])
        result.append(
            InvitationRead(
                id=item.id,
                email=item.email,
                roles=[str(role) for role in roles] if isinstance(roles, list) else [],
                status=state,
                expires_at=item.expires_at,
                created_at=item.created_at,
            )
        )
    return result


@router.post(
    "/organizations/{organization_id}/onboarding-invitations/{invitation_id}/resend",
    response_model=InvitationRead,
)
async def resend_onboarding_invitation(
    organization_id: str,
    invitation_id: str,
    request: Request,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvitationRead:
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    old = await session.scalar(
        select(IdentityActionToken)
        .where(
            IdentityActionToken.id == invitation_id,
            IdentityActionToken.organization_id == organization_id,
            IdentityActionToken.purpose == "invitation",
        )
        .with_for_update()
    )
    if old is None or old.consumed_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pending invitation not found")
    if old.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invitation has been revoked")
    organization = await session.get(Organization, organization_id)
    old.revoked_at = datetime.now(UTC)
    roles = old.payload.get("roles", [])
    invited_user = await session.scalar(
        select(User).where(func.lower(User.identifier) == old.email)
    )
    record, raw = await _issue_action_token(
        session,
        purpose="invitation",
        email=old.email,
        user_id=invited_user.id if invited_user is not None else None,
        organization_id=organization_id,
        created_by_user_id=membership.user_id,
        payload=old.payload,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    await session.commit()
    delivered = False
    if organization is not None:
        try:
            delivered = await _send_action_email(
                request,
                recipient=old.email,
                subject=f"Your invitation to {organization.name} on NextGen for Earth",
                path="/onboarding/accept",
                raw_token=raw,
                intro=f"Your invitation to join {organization.name} has been renewed.",
            )
        except Exception:
            delivered = False
    manual_link_allowed = (
        request.app.state.settings.identity_manual_invitation_links_enabled
        and request.app.state.settings.deployment_stage.value == "staging"
    )
    delivery_status = (
        "delivered" if delivered else "manual_link_ready" if manual_link_allowed else "failed"
    )
    record.payload = {**record.payload, "delivery_status": delivery_status}
    await session.commit()
    if (
        not delivered
        and not manual_link_allowed
        and request.app.state.settings.environment.value == "production"
    ):
        raise BackboneError(
            "invitation_delivery_unavailable", "Invitation delivery is unavailable", 503
        )
    return InvitationRead(
        id=record.id,
        email=record.email,
        roles=[str(role) for role in roles] if isinstance(roles, list) else [],
        status="delivered" if delivered else "pending_delivery",
        expires_at=record.expires_at,
        created_at=record.created_at or datetime.now(UTC),
        invitation_url=(
            f"{str(request.app.state.settings.public_base_url).rstrip('/')}/onboarding/accept#token={raw}"
            if not delivered
            else None
        ),
    )


@router.delete(
    "/organizations/{organization_id}/onboarding-invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_onboarding_invitation(
    organization_id: str,
    invitation_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    if not await membership_has_any_role(session, membership, {"admin", "founder", "executive"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    record = await session.scalar(
        select(IdentityActionToken)
        .where(
            IdentityActionToken.id == invitation_id,
            IdentityActionToken.organization_id == organization_id,
            IdentityActionToken.purpose == "invitation",
            IdentityActionToken.consumed_at.is_(None),
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pending invitation not found")
    record.revoked_at = datetime.now(UTC)
    await session.commit()


@router.post("/auth/invitations/accept", response_model=InvitationSessionResponse)
async def accept_onboarding_invitation(
    body: InvitationAccept,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> InvitationSessionResponse:
    """Verify mailbox ownership, create/reuse identity and activate only invited roles."""
    record = await _active_token(session, body.token, "invitation")
    if record.organization_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation is incomplete")
    roles_value = record.payload.get("roles", [])
    roles = (
        list(dict.fromkeys(str(role) for role in roles_value))
        if isinstance(roles_value, list)
        else []
    )
    allowed = {
        "admin",
        "founder",
        "executive",
        "programme_manager",
        "researcher",
        "youth_volunteer",
        "employee",
        "institutional_partner",
        "funder",
        "learner",
    }
    if not roles or not set(roles).issubset(allowed):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation roles are invalid")
    organization = await session.get(Organization, record.organization_id)
    if organization is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation organisation is unavailable")
    email = _normalise_email(record.email)
    user = await session.scalar(
        select(User).where(func.lower(User.identifier) == email).with_for_update()
    )
    hasher = PasswordHasher()
    if record.user_id is not None and (user is None or user.id != record.user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation identity is no longer valid")
    if user is None:
        if len(body.password) < 12:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "New account passwords must contain at least 12 characters",
            )
        user = User(
            identifier=email,
            password_hash=hasher.hash(body.password),
            email_verified_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()
    elif not hasher.verify(body.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Sign in with the password for this account"
        )
    existing = await session.scalar(
        select(Membership).where(
            Membership.organization_id == record.organization_id,
            Membership.user_id == user.id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This account already has an organisation membership"
        )
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    scope_value = record.payload.get("scope", {})
    scope = scope_value if isinstance(scope_value, dict) else {}
    course_id = scope.get("course_id")
    cohort_id = scope.get("cohort_id")
    if isinstance(course_id, str):
        course = await session.scalar(
            select(LearningCourse).where(
                LearningCourse.id == course_id,
                LearningCourse.organization_id == record.organization_id,
                LearningCourse.status == "published",
            )
        )
        if course is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "The invited course is no longer available"
            )
        if isinstance(cohort_id, str):
            cohort = await session.scalar(
                select(LearningCohort).where(
                    LearningCohort.id == cohort_id,
                    LearningCohort.organization_id == record.organization_id,
                    LearningCohort.programme_id == course.programme_id,
                    LearningCohort.status.in_({"open", "active"}),
                )
            )
            if cohort is None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "The invited cohort is no longer available"
                )
    membership = Membership(
        organization_id=record.organization_id,
        user_id=user.id,
        role=roles[0],
        status="active",
    )
    session.add(membership)
    await session.flush()
    for role in roles:
        session.add(MembershipRole(membership_id=membership.id, role=role))
    if "learner" in roles and isinstance(course_id, str):
        enrollment = await session.scalar(
            select(LearningEnrollment)
            .where(
                LearningEnrollment.course_id == course_id,
                LearningEnrollment.learner_id == user.id,
            )
            .with_for_update()
        )
        if enrollment is None:
            enrollment = LearningEnrollment(
                course_id=course_id,
                cohort_id=cohort_id if isinstance(cohort_id, str) else None,
                learner_id=user.id,
                status="approved",
                progress_percent=0,
                reviewed_by=record.created_by_user_id,
                reviewed_at=datetime.now(UTC),
            )
            session.add(enrollment)
        else:
            enrollment.cohort_id = cohort_id if isinstance(cohort_id, str) else None
            enrollment.status = "approved"
            enrollment.reviewed_by = record.created_by_user_id
            enrollment.reviewed_at = datetime.now(UTC)
    record.consumed_at = datetime.now(UTC)
    session.add(
        OrganizationAuditEvent(
            organization_id=record.organization_id,
            actor_user_id=user.id,
            subject_user_id=user.id,
            action="membership.invitation_accepted",
            changes={"roles": roles, "invitation_id": record.id, "status": "active"},
        )
    )
    auth_factory = getattr(request.app.state, "auth_application_factory", None)
    if auth_factory is None:
        raise BackboneError("auth_not_configured", "Authentication is not configured", 503)
    try:
        tokens = await auth_factory(session).login(
            LoginRequest(identifier=user.identifier, password=body.password)
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Unable to establish account session"
        ) from exc
    await session.commit()
    return InvitationSessionResponse(
        subject=tokens.subject,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        roles=roles,
        organization_id=record.organization_id,
    )


@router.post("/auth/password-reset/request", response_model=ActionMessage, status_code=202)
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    """Return the same response regardless of account existence."""
    email = _normalise_email(str(body.email))
    user = await session.scalar(select(User).where(func.lower(User.identifier) == email))
    if user is not None and request.app.state.email_sender is not None:
        record, raw = await _issue_action_token(
            session,
            purpose="password_reset",
            email=email,
            user_id=user.id,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=request.app.state.settings.identity_action_token_minutes),
        )
        await session.commit()
        try:
            await _send_action_email(
                request,
                recipient=email,
                subject="Reset your NextGen for Earth password",
                path="/account/recover",
                raw_token=raw,
                intro="A password reset was requested for your account.",
            )
        except Exception:
            # Never reveal delivery or account existence to the caller.
            _ = record
    return ActionMessage(
        message="If an account exists for that address, recovery instructions will be sent."
    )


@router.post("/auth/password-reset/confirm", response_model=ActionMessage)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    record = await _active_token(session, body.token, "password_reset")
    if record.user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recovery link is invalid")
    user = await session.get(User, record.user_id, with_for_update=True)
    if user is None or user.identifier.casefold() != record.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Recovery link is invalid")
    user.password_hash = PasswordHasher().hash(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)
    record.consumed_at = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.subject == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await session.commit()
    return ActionMessage(message="Password reset. Sign in again with your new password.")


@router.post("/auth/email-verification/request", response_model=ActionMessage, status_code=202)
async def request_email_verification(
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    user = await session.get(User, principal.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable")
    if user.email_verified_at is not None:
        return ActionMessage(message="This email address is already verified.")
    if request.app.state.email_sender is None:
        raise BackboneError("email_delivery_unavailable", "Email delivery is not configured", 503)
    _, raw = await _issue_action_token(
        session,
        purpose="email_verification",
        email=user.identifier,
        user_id=user.id,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=request.app.state.settings.identity_action_token_minutes),
    )
    await session.commit()
    await _send_action_email(
        request,
        recipient=user.identifier,
        subject="Verify your NextGen for Earth email",
        path="/account/verify",
        raw_token=raw,
        intro="Confirm that this email address belongs to you.",
    )
    return ActionMessage(message="Verification instructions have been sent.")


@router.post("/auth/email-verification/confirm", response_model=ActionMessage)
async def confirm_email_verification(
    body: TokenActionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    record = await _active_token(session, body.token, "email_verification")
    if record.user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification link is invalid")
    user = await session.get(User, record.user_id, with_for_update=True)
    if user is None or user.identifier.casefold() != record.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification link is invalid")
    user.email_verified_at = datetime.now(UTC)
    record.consumed_at = datetime.now(UTC)
    await session.commit()
    return ActionMessage(message="Email address verified.")


@router.post("/auth/email-change/request", response_model=ActionMessage, status_code=202)
async def request_email_change(
    body: EmailChangeRequest,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    user = await session.get(User, principal.user_id, with_for_update=True)
    if user is None or not PasswordHasher().verify(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    new_email = _normalise_email(str(body.new_email))
    if new_email == user.identifier:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a different email address"
        )
    if (
        await session.scalar(select(User.id).where(func.lower(User.identifier) == new_email))
        is not None
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email address is already in use")
    if request.app.state.email_sender is None:
        raise BackboneError("email_delivery_unavailable", "Email delivery is not configured", 503)
    _, raw = await _issue_action_token(
        session,
        purpose="email_change",
        email=new_email,
        user_id=user.id,
        payload={"previous_email": user.identifier},
        expires_at=datetime.now(UTC)
        + timedelta(minutes=request.app.state.settings.identity_action_token_minutes),
    )
    await session.commit()
    await _send_action_email(
        request,
        recipient=new_email,
        subject="Confirm your new NextGen for Earth email",
        path="/account/confirm-email-change",
        raw_token=raw,
        intro="Confirm this new email address to update your account.",
    )
    return ActionMessage(message="A confirmation link has been sent to your new email address.")


@router.post("/auth/email-change/confirm", response_model=ActionMessage)
async def confirm_email_change(
    body: TokenActionRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActionMessage:
    record = await _active_token(session, body.token, "email_change")
    if record.user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email change link is invalid")
    user = await session.get(User, record.user_id, with_for_update=True)
    previous_email = record.payload.get("previous_email")
    if user is None or previous_email != user.identifier:
        record.revoked_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email change request is no longer current")
    if await session.scalar(select(User.id).where(func.lower(User.identifier) == record.email)):
        record.revoked_at = datetime.now(UTC)
        await session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email address is no longer available")
    user.identifier = record.email
    user.email_verified_at = datetime.now(UTC)
    user.password_changed_at = datetime.now(UTC)
    record.consumed_at = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.subject == user.id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await session.commit()
    return ActionMessage(message="Email address updated. Sign in again.")
