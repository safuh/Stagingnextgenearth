"""Programme volunteer applications and safeguarding-gated onboarding."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeVolunteerApplication,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["volunteer-applications"])
_ADMINS = {"admin", "founder", "executive"}
_PROGRAMME_MANAGERS = _ADMINS | {"programme_manager"}


class VolunteerApplicationCreate(BaseModel):
    participation_type: Literal["volunteer", "ambassador"] = "volunteer"
    interest: str = Field(min_length=20, max_length=5000)
    availability: str | None = Field(default=None, max_length=500)


class VolunteerDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=2000)
    # This is a staff attestation after checking the required safeguarding/guardian
    # consent process outside the portal; applicants cannot set this field.
    safeguarding_verified: bool = False


class VolunteerApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    user_id: str
    participation_type: str
    interest: str
    availability: str | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    safeguarding_confirmed: bool
    created_at: datetime
    applicant_identifier: str | None = None
    programme_title: str | None = None


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications",
    response_model=VolunteerApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_volunteer_application(
    organization_id: str,
    programme_id: str,
    body: VolunteerApplicationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerApplicationRead:
    """Submit an authenticated expression of interest without granting membership."""
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    if programme.status not in {"planned", "active"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This programme is not accepting applications"
        )
    existing_membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
    )
    # Existing active youth volunteers may apply to additional programmes.
    # Other members must use their organisation's internal assignment workflow.
    if existing_membership is not None and (
        existing_membership.status != "active"
        or not await membership_has_any_role(
            session, existing_membership, {"youth_volunteer"}
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only active youth volunteers can apply as existing organisation members",
        )
    item = ProgrammeVolunteerApplication(
        organization_id=organization_id,
        programme_id=programme_id,
        user_id=principal.user_id,
        participation_type=body.participation_type,
        interest=body.interest.strip(),
        availability=body.availability.strip() if body.availability else None,
        status="pending",
        safeguarding_confirmed=False,
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An application already exists for this programme",
        ) from exc
    return VolunteerApplicationRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications",
    response_model=list[VolunteerApplicationRead],
)
async def list_volunteer_applications(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolunteerApplicationRead]:
    """Return private applicant details only to programme management roles."""
    if not await membership_has_any_role(session, membership, _PROGRAMME_MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    programme = await session.scalar(
        select(Programme.id).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    rows = await session.execute(
        select(ProgrammeVolunteerApplication, User.identifier)
        .join(User, User.id == ProgrammeVolunteerApplication.user_id)
        .where(
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.programme_id == programme_id,
        )
        .order_by(ProgrammeVolunteerApplication.created_at.desc())
        .limit(500)
    )
    return [
        VolunteerApplicationRead.model_validate(item).model_copy(
            update={"applicant_identifier": identifier}
        )
        for item, identifier in rows.all()
    ]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications/{application_id}/decision",
    response_model=VolunteerApplicationRead,
)
async def decide_volunteer_application(
    organization_id: str,
    programme_id: str,
    application_id: str,
    body: VolunteerDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerApplicationRead:
    """Approve only after staff have verified safeguarding requirements."""
    if not await membership_has_any_role(session, membership, _PROGRAMME_MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    item = await session.scalar(
        select(ProgrammeVolunteerApplication).where(
            ProgrammeVolunteerApplication.id == application_id,
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if item.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Application has already been decided")
    if item.user_id == principal.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Applicants cannot review their own applications"
        )

    if body.decision == "approved":
        if not body.safeguarding_verified:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                (
                    "Verify safeguarding requirements and any required parent or guardian "
                    "consent before approval"
                ),
            )
        existing = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == item.user_id,
            )
        )
        if existing is not None and (
            existing.status != "active"
            or not await membership_has_any_role(
                session, existing, {"youth_volunteer"}
            )
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Applicant already has a non-volunteer or inactive organisation membership",
            )
        if existing is None:
            session.add(
                Membership(
                    organization_id=organization_id,
                    user_id=item.user_id,
                    role="youth_volunteer",
                    status="active",
                )
            )
        item.safeguarding_confirmed = True

    item.status = body.decision
    item.reviewed_by = principal.user_id
    item.reviewed_at = datetime.now(UTC)
    item.review_note = body.review_note
    await session.commit()
    await session.refresh(item)
    return VolunteerApplicationRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/volunteer-applications",
    response_model=list[VolunteerApplicationRead],
)
async def list_organization_volunteer_applications(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolunteerApplicationRead]:
    """Return one bounded, organisation-wide volunteer review queue."""
    if not await membership_has_any_role(session, membership, _PROGRAMME_MANAGERS):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Programme management permission required"
        )
    rows = await session.execute(
        select(ProgrammeVolunteerApplication, User.identifier, Programme.title)
        .join(User, User.id == ProgrammeVolunteerApplication.user_id)
        .join(Programme, Programme.id == ProgrammeVolunteerApplication.programme_id)
        .where(
            ProgrammeVolunteerApplication.organization_id == organization_id,
            Programme.organization_id == organization_id,
        )
        .order_by(ProgrammeVolunteerApplication.created_at.desc())
        .limit(500)
    )
    return [
        VolunteerApplicationRead.model_validate(item).model_copy(
            update={
                "applicant_identifier": identifier,
                "programme_title": programme_title,
            }
        )
        for item, identifier, programme_title in rows.all()
    ]
