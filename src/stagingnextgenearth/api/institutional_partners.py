# ruff: noqa: E501, I001
# fmt: off
"""Tenant-scoped partner registry and programme links."""
from datetime import UTC, datetime
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from stagingnextgenearth.platform.models import InstitutionalPartner, InstitutionalPartnerContact, Membership, Organization, Programme, ProgrammePartner, OrganizationRecordAuditEvent
from .dependencies import Principal, get_current_principal, get_session, membership_has_any_role, require_membership

router = APIRouter(tags=["institutional-partners"])
PartnerType = Literal["university","government","ngo","private_sector","network","funder","community_org","other"]
class PartnerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=240)
    partner_type: PartnerType = "other"
    description: str | None = Field(default=None, max_length=5000)
    website_url: str | None = Field(default=None, max_length=1000)
    country_code: str = Field(default="KE", min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)
    source_url: str | None = Field(default=None, max_length=1000)
class PartnerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=240)
    partner_type: PartnerType | None = None
    description: str | None = Field(default=None, max_length=5000)
    website_url: str | None = Field(default=None, max_length=1000)
    region: str | None = Field(default=None, max_length=120)
    relationship_status: Literal["prospect","active","paused","ended"] | None = None
    verification_state: Literal["pending","verified","rejected"] | None = None
    visibility: Literal["private","public"] | None = None
class PartnerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    name: str
    partner_type: str
    description: str | None
    website_url: str | None
    country_code: str
    region: str | None
    relationship_status: str
    verification_state: str
    visibility: str
    source_url: str | None
class PartnerProgrammeLink(BaseModel):
    programme_id: str
    partner_role: Literal["implementing_partner","funding_partner","technical_partner","research_partner","community_partner"]
    status: Literal["planned","active","ended"] = "planned"
async def _admin(m: Membership, session: AsyncSession) -> None:
    if not await membership_has_any_role(session, m, {"admin", "founder", "executive"}):
        raise HTTPException(403, "Administrator role required")
@router.get("/organizations/{organization_id}/partners", response_model=list[PartnerRead])
async def list_partners(organization_id: str, membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> list[PartnerRead]:
    await _admin(membership, session)
    rows = await session.scalars(select(InstitutionalPartner).where(InstitutionalPartner.organization_id == organization_id).order_by(InstitutionalPartner.name).limit(500))
    return [PartnerRead.model_validate(x) for x in rows.all()]
@router.post("/organizations/{organization_id}/partners", response_model=PartnerRead, status_code=201)
async def create_partner(organization_id: str, body: PartnerCreate, principal: Annotated[Principal, Depends(get_current_principal)], membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> PartnerRead:
    _admin(membership)
    row = InstitutionalPartner(organization_id=organization_id, name=body.name.strip(), partner_type=body.partner_type, description=body.description, website_url=body.website_url, country_code=body.country_code.upper(), region=body.region, source_url=body.source_url, source_label="NextGen For Earth website", created_by=principal.user_id, updated_by=principal.user_id)
    session.add(row)
    await session.flush()
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="partner", entity_id=row.id,
        actor_user_id=principal.user_id, action="record.created",
        changed_fields=["name", "partner_type", "description", "website_url", "country_code", "region", "source_url"],
        state={"name": row.name, "partner_type": row.partner_type, "relationship_status": row.relationship_status,
               "verification_state": row.verification_state, "visibility": row.visibility},
    ))
    await session.commit()
    await session.refresh(row)
    return PartnerRead.model_validate(row)
@router.patch("/organizations/{organization_id}/partners/{partner_id}", response_model=PartnerRead)
async def update_partner(organization_id: str, partner_id: str, body: PartnerUpdate, principal: Annotated[Principal, Depends(get_current_principal)], membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> PartnerRead:
    _admin(membership)
    row = await session.scalar(select(InstitutionalPartner).where(InstitutionalPartner.id == partner_id, InstitutionalPartner.organization_id == organization_id))
    if row is None:
        raise HTTPException(404, "Partner not found")
    changes = body.model_dump(exclude_unset=True)
    changed_fields = sorted(changes)
    previous_state = {"relationship_status": row.relationship_status,
                       "verification_state": row.verification_state, "visibility": row.visibility}
    for key, value in changes.items():
        if value is not None or key == "description":
            setattr(row, key, value)
    row.updated_by = principal.user_id
    await session.flush()
    state_changed = any(
        key in changes and getattr(row, key) != previous_state.get(key)
        for key in ("relationship_status", "verification_state", "visibility")
    )
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="partner", entity_id=row.id,
        actor_user_id=principal.user_id,
        action="record.state_changed" if state_changed else "record.updated",
        changed_fields=changed_fields,
        state={"name": row.name, "partner_type": row.partner_type, "relationship_status": row.relationship_status,
               "verification_state": row.verification_state, "visibility": row.visibility},
    ))
    await session.commit()
    await session.refresh(row)
    return PartnerRead.model_validate(row)

class PartnerAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    entity_id: str
    actor_user_id: str
    action: str
    changed_fields: list[str]
    state: dict[str, object]
    created_at: object

@router.get("/organizations/{organization_id}/partners/{partner_id}/audit-events", response_model=list[PartnerAuditRead])
async def partner_audit_events(
    organization_id: str, partner_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PartnerAuditRead]:
    _admin(membership)
    partner_row = await session.scalar(select(InstitutionalPartner).where(
        InstitutionalPartner.id == partner_id, InstitutionalPartner.organization_id == organization_id
    ))
    if partner_row is None:
        raise HTTPException(404, "Partner not found")
    rows = await session.scalars(select(OrganizationRecordAuditEvent).where(
        OrganizationRecordAuditEvent.organization_id == organization_id,
        OrganizationRecordAuditEvent.entity_type == "partner",
        OrganizationRecordAuditEvent.entity_id == partner_id,
    ).order_by(OrganizationRecordAuditEvent.created_at.desc()).limit(200))
    return [PartnerAuditRead.model_validate(x) for x in rows.all()]

@router.post("/organizations/{organization_id}/partners/{partner_id}/programmes", status_code=201)
async def link_partner_programme(organization_id: str, partner_id: str, body: PartnerProgrammeLink, membership: Annotated[Membership, Depends(require_membership)], session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str,str]:
    _admin(membership)
    partner_row = await session.scalar(select(InstitutionalPartner).where(InstitutionalPartner.id == partner_id, InstitutionalPartner.organization_id == organization_id))
    programme = await session.scalar(select(Programme).where(Programme.id == body.programme_id, Programme.organization_id == organization_id))
    if partner_row is None or programme is None:
        raise HTTPException(404, "Partner or programme not found")
    link = ProgrammePartner(organization_id=organization_id, partner_id=partner_id, programme_id=programme.id, partner_role=body.partner_role, status=body.status)
    session.add(link)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Partner is already linked to this programme") from exc
    return {"id": link.id, "partner_id": partner_id, "programme_id": programme.id}
class PartnerContactCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    job_title: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)

class PartnerContactUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    job_title: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    contact_permission: bool | None = None
    status: Literal["active", "inactive"] | None = None

class PartnerContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    partner_id: str
    full_name: str
    job_title: str | None
    email: str | None
    phone: str | None
    contact_permission: bool
    permission_recorded_at: object | None
    status: str

@router.get("/organizations/{organization_id}/partners/{partner_id}/contacts", response_model=list[PartnerContactRead])
async def list_partner_contacts(
    organization_id: str, partner_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PartnerContactRead]:
    _admin(membership)
    partner = await session.scalar(select(InstitutionalPartner).where(
        InstitutionalPartner.id == partner_id,
        InstitutionalPartner.organization_id == organization_id,
    ))
    if partner is None:
        raise HTTPException(404, "Partner not found")
    rows = await session.scalars(select(InstitutionalPartnerContact).where(
        InstitutionalPartnerContact.organization_id == organization_id,
        InstitutionalPartnerContact.partner_id == partner_id,
        InstitutionalPartnerContact.status == "active",
    ).order_by(InstitutionalPartnerContact.full_name).limit(200))
    return [PartnerContactRead.model_validate(row) for row in rows.all()]

@router.post("/organizations/{organization_id}/partners/{partner_id}/contacts", response_model=PartnerContactRead, status_code=201)
async def create_partner_contact(
    organization_id: str, partner_id: str, body: PartnerContactCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PartnerContactRead:
    _admin(membership)
    partner = await session.scalar(select(InstitutionalPartner).where(
        InstitutionalPartner.id == partner_id,
        InstitutionalPartner.organization_id == organization_id,
    ))
    if partner is None:
        raise HTTPException(404, "Partner not found")
    row = InstitutionalPartnerContact(
        organization_id=organization_id, partner_id=partner_id,
        full_name=body.full_name.strip(), job_title=body.job_title,
        email=body.email.strip().lower() if body.email else None,
        phone=body.phone, contact_permission=False,
        created_by=principal.user_id, updated_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="partner", entity_id=partner_id,
        actor_user_id=principal.user_id, action="record.created",
        changed_fields=["contacts"],
        state={"contact_id": row.id, "contact_status": row.status, "contact_permission": False},
    ))
    await session.commit()
    await session.refresh(row)
    return PartnerContactRead.model_validate(row)

@router.patch("/organizations/{organization_id}/partners/{partner_id}/contacts/{contact_id}", response_model=PartnerContactRead)
async def update_partner_contact(
    organization_id: str, partner_id: str, contact_id: str, body: PartnerContactUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PartnerContactRead:
    _admin(membership)
    row = await session.scalar(select(InstitutionalPartnerContact).where(
        InstitutionalPartnerContact.id == contact_id,
        InstitutionalPartnerContact.partner_id == partner_id,
        InstitutionalPartnerContact.organization_id == organization_id,
    ))
    if row is None:
        raise HTTPException(404, "Partner contact not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("contact_permission") is True:
        row.permission_recorded_at = datetime.now(UTC)
    elif changes.get("contact_permission") is False:
        row.permission_recorded_at = None
    for key, value in changes.items():
        if value is not None or key in {"job_title", "email", "phone"}:
            setattr(row, key, value)
    if "email" in changes and row.email:
        row.email = row.email.strip().lower()
    if "full_name" in changes and row.full_name:
        row.full_name = row.full_name.strip()
    row.updated_by = principal.user_id
    session.add(OrganizationRecordAuditEvent(
        organization_id=organization_id, entity_type="partner", entity_id=partner_id,
        actor_user_id=principal.user_id, action="record.updated",
        changed_fields=["contact." + key for key in sorted(changes)],
        state={"contact_id": row.id, "contact_status": row.status,
               "contact_permission": row.contact_permission},
    ))
    await session.commit()
    await session.refresh(row)
    return PartnerContactRead.model_validate(row)

class PublicPartnerRead(BaseModel):
    """Public partner fields; moderation and source metadata remain private."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    partner_type: str
    description: str | None
    website_url: str | None
    country_code: str
    region: str | None

@router.get("/public/organizations/{organization_slug}/partners", response_model=list[PublicPartnerRead])
async def public_partners(organization_slug: str, session: Annotated[AsyncSession, Depends(get_session)]) -> list[PublicPartnerRead]:
    org = await session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if org is None:
        raise HTTPException(404, "Organisation not found")
    rows = await session.scalars(select(InstitutionalPartner).where(InstitutionalPartner.organization_id == org.id, InstitutionalPartner.relationship_status == "active", InstitutionalPartner.verification_state == "verified", InstitutionalPartner.visibility == "public").order_by(InstitutionalPartner.name))
    return [PublicPartnerRead.model_validate(x) for x in rows.all()]

# fmt: on
