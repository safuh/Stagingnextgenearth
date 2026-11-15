# ruff: noqa: E501, I001
# fmt: off
"""Moderated CMS API consumed by the public website."""
from datetime import UTC, datetime
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stagingnextgenearth.platform.models import Membership, Organization, PublicContentEntry, OrganizationRecordAuditEvent
from .dependencies import Principal, get_current_principal, get_session, require_membership
router = APIRouter(tags=["public-content"])
ContentType = Literal["page","programme","training_track","initiative","research_area","impact_metric","publication"]
class ContentCreate(BaseModel):
    content_type: ContentType
    slug: str = Field(min_length=2, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=2, max_length=240)
    summary: str | None = Field(default=None, max_length=5000)
    body: str | None = Field(default=None, max_length=30000)
    metadata_json: dict[str, object] = Field(default_factory=dict)
    source_url: str | None = Field(default=None, max_length=1000)
class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    summary: str | None = Field(default=None, max_length=5000)
    body: str | None = Field(default=None, max_length=30000)
    metadata_json: dict[str, object] | None = None
    publication_state: Literal["draft","review","approved","published","archived"] | None = None
class ContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    content_type: str
    slug: str
    title: str
    summary: str | None
    body: str | None
    metadata_json: dict[str, object]
    publication_state: str
    source_url: str | None
    published_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
def _admin(m: Membership) -> None:
    if m.role not in {"admin", "founder", "executive"}:
        raise HTTPException(403, "Administrator role required")
@router.get("/organizations/{organization_id}/content", response_model=list[ContentRead])
async def list_content(organization_id: str, membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> list[ContentRead]:
    _admin(membership)
    rows = await session.scalars(select(PublicContentEntry).where(PublicContentEntry.organization_id == organization_id).order_by(PublicContentEntry.content_type, PublicContentEntry.title).limit(1000))
    return [ContentRead.model_validate(x) for x in rows.all()]
@router.post("/organizations/{organization_id}/content", response_model=ContentRead, status_code=201)
async def create_content(organization_id: str, body: ContentCreate, principal: Annotated[Principal, Depends(get_current_principal)], membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> ContentRead:
    _admin(membership)
    row = PublicContentEntry(organization_id=organization_id, content_type=body.content_type, slug=body.slug, title=body.title.strip(), summary=body.summary, body=body.body, metadata_json=body.metadata_json, publication_state="draft", source_url=body.source_url, source_label="NextGen For Earth website", created_by=principal.user_id, updated_by=principal.user_id)
    session.add(row)
    await session.flush()
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="content", entity_id=row.id,
        actor_user_id=principal.user_id, action="record.created",
        changed_fields=["content_type", "slug", "title", "summary", "body", "metadata_json", "source_url"],
        state={"content_type": row.content_type, "slug": row.slug, "title": row.title,
               "publication_state": row.publication_state},
    ))
    await session.commit()
    await session.refresh(row)
    return ContentRead.model_validate(row)
@router.patch("/organizations/{organization_id}/content/{content_id}", response_model=ContentRead)
async def update_content(organization_id: str, content_id: str, body: ContentUpdate, principal: Annotated[Principal, Depends(get_current_principal)], membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> ContentRead:
    _admin(membership)
    row = await session.scalar(select(PublicContentEntry).where(PublicContentEntry.id == content_id, PublicContentEntry.organization_id == organization_id))
    if row is None:
        raise HTTPException(404, "Content entry not found")
    changes = body.model_dump(exclude_unset=True)
    next_state = changes.pop("publication_state", None)
    changed_fields = sorted([*changes, *([ "publication_state" ] if next_state is not None else [])])
    previous_state = row.publication_state
    if changes and previous_state in {"review", "approved", "published"}:
        if next_state is not None:
            raise HTTPException(
                409,
                "Edit content separately; changes invalidate the current review and publication state",
            )
    for key, value in changes.items():
        if value is not None or key in {"summary", "body"}:
            setattr(row, key, value)
    if changes and previous_state in {"review", "approved", "published"}:
        row.publication_state = "draft"
        row.approved_by = None
        row.approved_at = None
        row.published_at = None
    if next_state is not None:
        if next_state == "approved" and row.created_by == principal.user_id:
            raise HTTPException(403, "A different authorised reviewer must approve this content")
        allowed = {
            "draft": {"review", "archived"},
            "review": {"draft", "approved", "archived"},
            "approved": {"draft", "published", "archived"},
            "published": {"draft", "archived"},
            "archived": {"draft"},
        }
        if next_state not in allowed[row.publication_state]:
            raise HTTPException(409, f"Invalid CMS transition: {row.publication_state} -> {next_state}")
        if next_state == "approved":
            row.approved_by = principal.user_id
            row.approved_at = datetime.now(UTC)
        elif next_state == "published":
            if row.approved_at is None or row.approved_by is None:
                raise HTTPException(409, "Content must be approved before publication")
            row.published_at = datetime.now(UTC)
        elif next_state == "draft":
            row.approved_by = None
            row.approved_at = None
            row.published_at = None
        elif next_state == "archived":
            row.published_at = None
        row.publication_state = next_state
    row.published_at = row.published_at if row.publication_state == "published" else None
    row.updated_by = principal.user_id
    await session.flush()
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="content", entity_id=row.id,
        actor_user_id=principal.user_id,
        action="record.state_changed" if previous_state != row.publication_state else "record.updated",
        changed_fields=changed_fields,
        state={"content_type": row.content_type, "slug": row.slug, "title": row.title,
               "publication_state": row.publication_state, "approved_by": row.approved_by,
               "approved_at": row.approved_at.isoformat() if row.approved_at else None,
               "published_at": row.published_at.isoformat() if row.published_at else None},
    ))
    await session.commit()
    await session.refresh(row)
    return ContentRead.model_validate(row)

class ContentAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    entity_id: str
    actor_user_id: str
    action: str
    changed_fields: list[str]
    state: dict[str, object]
    created_at: object

@router.get("/organizations/{organization_id}/content/{content_id}/audit-events", response_model=list[ContentAuditRead])
async def content_audit_events(
    organization_id: str, content_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ContentAuditRead]:
    _admin(membership)
    entry = await session.scalar(select(PublicContentEntry).where(
        PublicContentEntry.id == content_id, PublicContentEntry.organization_id == organization_id
    ))
    if entry is None:
        raise HTTPException(404, "Content entry not found")
    rows = await session.scalars(select(OrganizationRecordAuditEvent).where(
        OrganizationRecordAuditEvent.organization_id == organization_id,
        OrganizationRecordAuditEvent.entity_type == "content",
        OrganizationRecordAuditEvent.entity_id == content_id,
    ).order_by(OrganizationRecordAuditEvent.created_at.desc()).limit(200))
    return [ContentAuditRead.model_validate(x) for x in rows.all()]

class PublicContentRead(BaseModel):
    """Public content fields without internal source or moderation metadata."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    content_type: str
    slug: str
    title: str
    summary: str | None
    body: str | None
    published_at: datetime | None

@router.get("/public/organizations/{organization_slug}/content", response_model=list[PublicContentRead])
async def public_content(organization_slug: str, session: Annotated[AsyncSession, Depends(get_session)]) -> list[PublicContentRead]:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    rows = await session.scalars(select(PublicContentEntry).where(PublicContentEntry.organization_id == org.id, PublicContentEntry.publication_state == "published").order_by(PublicContentEntry.content_type, PublicContentEntry.title).limit(500))
    return [PublicContentRead.model_validate(x) for x in rows.all()]

# fmt: on
