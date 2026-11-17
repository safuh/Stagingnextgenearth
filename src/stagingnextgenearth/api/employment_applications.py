"""Secure employment application, review, and employee onboarding workflow."""

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
    Organization,
    OrganizationEmploymentApplication,
    OrganizationPerson,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["employment-applications"])
_ADMINS = {"admin", "founder", "executive"}


class EmploymentApplicationCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    desired_position: str = Field(min_length=2, max_length=160)
    qualifications: str = Field(min_length=20, max_length=5000)
    experience_summary: str | None = Field(default=None, max_length=5000)


class EmploymentApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    user_id: str
    full_name: str
    desired_position: str
    qualifications: str
    experience_summary: str | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    applicant_identifier: str | None = None


class EmploymentDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


@router.post(
    "/organizations/{organization_id}/employment-applications",
    response_model=EmploymentApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_employment_application(
    organization_id: str,
    body: EmploymentApplicationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EmploymentApplicationRead:
    """Accept an authenticated candidate's application; never create membership here."""
    organization = await session.scalar(
        select(Organization.id).where(Organization.id == organization_id)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    existing_membership = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
    )
    if existing_membership is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Existing organisation members must use the internal role-management process",
        )
    application = OrganizationEmploymentApplication(
        organization_id=organization_id,
        user_id=principal.user_id,
        full_name=body.full_name.strip(),
        desired_position=body.desired_position.strip(),
        qualifications=body.qualifications.strip(),
        experience_summary=body.experience_summary.strip() if body.experience_summary else None,
    )
    session.add(application)
    try:
        await session.commit()
        await session.refresh(application)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An employment application already exists"
        ) from exc
    return EmploymentApplicationRead.model_validate(application)


@router.post(
    "/public/organizations/{organization_slug}/employment-applications",
    response_model=EmploymentApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_public_employment_application(
    organization_slug: str,
    body: EmploymentApplicationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EmploymentApplicationRead:
    """Publicly discoverable application endpoint; authentication is still mandatory."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    existing_membership = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization.id,
            Membership.user_id == principal.user_id,
        )
    )
    if existing_membership is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Existing organisation members must use the internal role-management process",
        )
    application = OrganizationEmploymentApplication(
        organization_id=organization.id,
        user_id=principal.user_id,
        full_name=body.full_name.strip(),
        desired_position=body.desired_position.strip(),
        qualifications=body.qualifications.strip(),
        experience_summary=body.experience_summary.strip() if body.experience_summary else None,
    )
    session.add(application)
    try:
        await session.commit()
        await session.refresh(application)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An employment application already exists"
        ) from exc
    return EmploymentApplicationRead.model_validate(application)


@router.get(
    "/organizations/{organization_id}/my-employment-applications",
    response_model=list[EmploymentApplicationRead],
)
async def list_my_employment_applications(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EmploymentApplicationRead]:
    rows = await session.scalars(
        select(OrganizationEmploymentApplication).where(
            OrganizationEmploymentApplication.organization_id == organization_id,
            OrganizationEmploymentApplication.user_id == principal.user_id,
        ).order_by(OrganizationEmploymentApplication.created_at.desc()).limit(50)
    )
    return [EmploymentApplicationRead.model_validate(row) for row in rows.all()]


@router.get(
    "/organizations/{organization_id}/employment-applications",
    response_model=list[EmploymentApplicationRead],
)
async def list_employment_applications(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EmploymentApplicationRead]:
    if not await membership_has_any_role(session, membership, _ADMINS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    rows = await session.execute(
        select(OrganizationEmploymentApplication, User.identifier)
        .join(User, User.id == OrganizationEmploymentApplication.user_id)
        .where(OrganizationEmploymentApplication.organization_id == organization_id)
        .order_by(OrganizationEmploymentApplication.created_at.desc()).limit(500)
    )
    return [
        EmploymentApplicationRead.model_validate(item).model_copy(
            update={"applicant_identifier": identifier}
        )
        for item, identifier in rows.all()
    ]


@router.post(
    "/organizations/{organization_id}/employment-applications/{application_id}/decision",
    response_model=EmploymentApplicationRead,
)
async def decide_employment_application(
    organization_id: str,
    application_id: str,
    body: EmploymentDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EmploymentApplicationRead:
    if not await membership_has_any_role(session, membership, _ADMINS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    item = await session.scalar(
        select(OrganizationEmploymentApplication).where(
            OrganizationEmploymentApplication.id == application_id,
            OrganizationEmploymentApplication.organization_id == organization_id,
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
        existing = await session.scalar(
            select(Membership.id).where(
                Membership.organization_id == organization_id,
                Membership.user_id == item.user_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Applicant already has an organisation membership; resolve roles before approval",
            )
        session.add(Membership(
            organization_id=organization_id, user_id=item.user_id,
            role="employee", status="active",
        ))
        session.add(OrganizationPerson(
            organization_id=organization_id,
            full_name=item.full_name,
            positions=[item.desired_position],
            person_types=["employee"],
            review_state="pending",
            visibility="private",
            status="active",
            created_by=principal.user_id,
            updated_by=principal.user_id,
        ))
    item.status = body.decision
    item.reviewed_by = principal.user_id
    item.reviewed_at = datetime.now(UTC)
    item.review_note = body.note
    await session.commit()
    await session.refresh(item)
    return EmploymentApplicationRead.model_validate(item)
