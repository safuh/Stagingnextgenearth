"""Organisation-scoped programme read and create endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import Membership, Programme

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(prefix="/organizations/{organization_id}/programmes", tags=["programmes"])


class ProgrammeCreate(BaseModel):
    """Programme creation contract."""

    title: str = Field(min_length=2, max_length=240)
    slug: str = Field(min_length=2, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    summary: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ProgrammeCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class ProgrammeRead(BaseModel):
    """Programme response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    title: str
    slug: str
    summary: str | None
    status: str
    start_date: date | None
    end_date: date | None


@router.post("", response_model=ProgrammeRead, status_code=status.HTTP_201_CREATED)
async def create_programme(
    organization_id: str,
    body: ProgrammeCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProgrammeRead:
    """Create a draft programme; only administrators and programme managers may write."""
    if membership.role not in {"admin", "programme_manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient organisation permissions")
    programme = Programme(
        organization_id=organization_id,
        title=body.title.strip(),
        slug=body.slug,
        summary=body.summary,
        status="draft",
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=principal.user_id,
    )
    session.add(programme)
    try:
        await session.commit()
        await session.refresh(programme)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Programme slug already exists") from exc
    return ProgrammeRead.model_validate(programme)


@router.get("", response_model=list[ProgrammeRead])
async def list_programmes(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProgrammeRead]:
    """List programmes only inside an organisation the caller actively belongs to."""
    result = await session.scalars(
        select(Programme)
        .where(Programme.organization_id == organization_id)
        .order_by(Programme.created_at.desc())
    )
    return [ProgrammeRead.model_validate(item) for item in result.all()]
