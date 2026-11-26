"""Tenant-scoped grants, budgets and non-payment funding records."""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    FundingAuditEvent,
    FundingAward,
    FundingBudgetLine,
    FundingLedgerEntry,
    FundingOpportunity,
    InstitutionalPartner,
    Membership,
    Programme,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["funding-management"])
_ADMIN_ROLES = {"admin", "founder", "executive"}
Currency = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


async def _require_funding_admin(membership: Membership, session: AsyncSession) -> None:
    if not await membership_has_any_role(session, membership, _ADMIN_ROLES):
        raise HTTPException(403, "Organisation administrator role required")


async def _audit(
    session: AsyncSession,
    *,
    organization_id: str,
    actor_id: str,
    entity_type: str,
    entity_id: str,
    fields: list[str],
    state: dict[str, object],
    action: str = "record.created",
) -> None:
    session.add(
        FundingAuditEvent(
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_id,
            action=action,
            changed_fields=fields,
            state=state,
        )
    )


class OpportunityCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    donor_name: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    reference_url: str | None = Field(default=None, max_length=1000)
    deadline: date | None = None
    status: Literal["identified", "reviewing", "submitted", "awarded", "declined", "closed"] = (
        "identified"
    )
    expected_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: Currency = "KES"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    donor_name: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    reference_url: str | None = Field(default=None, max_length=1000)
    deadline: date | None = None
    status: (
        Literal["identified", "reviewing", "submitted", "awarded", "declined", "closed"] | None
    ) = None
    expected_amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class AwardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    donor_name: str | None = Field(default=None, min_length=2, max_length=240)
    award_amount: Money | None = None
    restrictions: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    end_date: date | None = None
    reporting_deadline: date | None = None
    status: Literal["draft", "active", "completed", "suspended", "closed"] | None = None


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    title: str
    donor_name: str
    description: str | None
    reference_url: str | None
    deadline: date | None
    status: str
    expected_amount: Decimal | None
    currency: str
    created_at: object
    updated_at: object


class AwardCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    donor_name: str = Field(min_length=2, max_length=240)
    award_amount: Money
    currency: Currency = "KES"
    opportunity_id: str | None = None
    partner_id: str | None = None
    award_reference: str | None = Field(default=None, max_length=120)
    restrictions: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    end_date: date | None = None
    reporting_deadline: date | None = None
    status: Literal["draft", "active", "completed", "suspended", "closed"] = "draft"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class AwardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    opportunity_id: str | None
    partner_id: str | None
    title: str
    donor_name: str
    award_reference: str | None
    currency: str
    award_amount: Decimal
    restrictions: str | None
    start_date: date | None
    end_date: date | None
    reporting_deadline: date | None
    status: str
    created_at: object
    updated_at: object


class BudgetLineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=3000)
    budget_amount: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    programme_id: str | None = None


class BudgetLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    award_id: str
    programme_id: str | None
    name: str
    description: str | None
    budget_amount: Decimal
    created_at: object


class LedgerEntryCreate(BaseModel):
    entry_type: Literal["pledge", "commitment", "expenditure"]
    amount: Money
    occurred_on: date
    description: str = Field(min_length=2, max_length=2000)
    reference: str | None = Field(default=None, max_length=120)
    budget_line_id: str | None = None


class LedgerEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    award_id: str
    budget_line_id: str | None
    entry_type: str
    amount: Decimal
    occurred_on: date
    reference: str | None
    description: str
    entered_by: str
    created_at: object


class FundingSummary(BaseModel):
    award_id: str
    title: str
    donor_name: str
    currency: str
    award_amount: Decimal
    budgeted_amount: Decimal
    pledged_amount: Decimal
    committed_amount: Decimal
    expenditure_amount: Decimal
    unallocated_amount: Decimal
    reporting_deadline: date | None
    status: str


@router.get(
    "/organizations/{organization_id}/funding/opportunities", response_model=list[OpportunityRead]
)
async def list_opportunities(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OpportunityRead]:
    await _require_funding_admin(membership, session)
    rows = await session.scalars(
        select(FundingOpportunity)
        .where(
            FundingOpportunity.organization_id == organization_id,
        )
        .order_by(
            FundingOpportunity.deadline.asc().nullslast(), FundingOpportunity.created_at.desc()
        )
        .limit(500)
    )
    return [OpportunityRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/funding/opportunities",
    response_model=OpportunityRead,
    status_code=201,
)
async def create_opportunity(
    organization_id: str,
    body: OpportunityCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpportunityRead:
    await _require_funding_admin(membership, session)
    row = FundingOpportunity(
        organization_id=organization_id,
        title=body.title.strip(),
        donor_name=body.donor_name.strip(),
        description=body.description,
        reference_url=body.reference_url,
        deadline=body.deadline,
        status=body.status,
        expected_amount=body.expected_amount,
        currency=body.currency,
        created_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="opportunity",
        entity_id=row.id,
        fields=["title", "donor_name", "deadline", "status", "expected_amount", "currency"],
        state={
            "title": row.title,
            "donor_name": row.donor_name,
            "status": row.status,
            "expected_amount": str(row.expected_amount)
            if row.expected_amount is not None
            else None,
            "currency": row.currency,
        },
    )
    await session.commit()
    await session.refresh(row)
    return OpportunityRead.model_validate(row)


@router.patch(
    "/organizations/{organization_id}/funding/opportunities/{opportunity_id}",
    response_model=OpportunityRead,
)
async def update_opportunity(
    organization_id: str,
    opportunity_id: str,
    body: OpportunityUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OpportunityRead:
    await _require_funding_admin(membership, session)
    row = await session.scalar(
        select(FundingOpportunity)
        .where(
            FundingOpportunity.id == opportunity_id,
            FundingOpportunity.organization_id == organization_id,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Funding opportunity not found")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one field must be supplied")
    if any(changes.get(key) is None for key in ("title", "donor_name") if key in changes):
        raise HTTPException(422, "Title and donor name cannot be cleared")
    for key, value in changes.items():
        setattr(
            row,
            key,
            value.strip() if isinstance(value, str) and key in {"title", "donor_name"} else value,
        )
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="opportunity",
        entity_id=row.id,
        fields=sorted(changes),
        state={"title": row.title, "donor_name": row.donor_name, "status": row.status},
        action="record.updated",
    )
    await session.commit()
    await session.refresh(row)
    return OpportunityRead.model_validate(row)


@router.get("/organizations/{organization_id}/funding/awards", response_model=list[AwardRead])
async def list_awards(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AwardRead]:
    await _require_funding_admin(membership, session)
    rows = await session.scalars(
        select(FundingAward)
        .where(
            FundingAward.organization_id == organization_id,
        )
        .order_by(FundingAward.reporting_deadline.asc().nullslast(), FundingAward.created_at.desc())
        .limit(500)
    )
    return [AwardRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/funding/awards", response_model=AwardRead, status_code=201
)
async def create_award(
    organization_id: str,
    body: AwardCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AwardRead:
    await _require_funding_admin(membership, session)
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise HTTPException(422, "Award end date must not precede its start date")
    if body.opportunity_id:
        opportunity = await session.scalar(
            select(FundingOpportunity).where(
                FundingOpportunity.id == body.opportunity_id,
                FundingOpportunity.organization_id == organization_id,
            )
        )
        if opportunity is None:
            raise HTTPException(404, "Funding opportunity not found")
    if body.partner_id:
        partner = await session.scalar(
            select(InstitutionalPartner).where(
                InstitutionalPartner.id == body.partner_id,
                InstitutionalPartner.organization_id == organization_id,
            )
        )
        if partner is None:
            raise HTTPException(404, "Institutional partner not found")
    row = FundingAward(
        organization_id=organization_id,
        opportunity_id=body.opportunity_id,
        partner_id=body.partner_id,
        title=body.title.strip(),
        donor_name=body.donor_name.strip(),
        award_reference=body.award_reference,
        currency=body.currency,
        award_amount=body.award_amount,
        restrictions=body.restrictions,
        start_date=body.start_date,
        end_date=body.end_date,
        reporting_deadline=body.reporting_deadline,
        status=body.status,
        created_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="award",
        entity_id=row.id,
        fields=[
            "title",
            "donor_name",
            "award_amount",
            "currency",
            "restrictions",
            "reporting_deadline",
            "status",
        ],
        state={
            "title": row.title,
            "donor_name": row.donor_name,
            "award_amount": str(row.award_amount),
            "currency": row.currency,
            "status": row.status,
        },
    )
    await session.commit()
    await session.refresh(row)
    return AwardRead.model_validate(row)


@router.patch(
    "/organizations/{organization_id}/funding/awards/{award_id}",
    response_model=AwardRead,
)
async def update_award(
    organization_id: str,
    award_id: str,
    body: AwardUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AwardRead:
    await _require_funding_admin(membership, session)
    row = await _award_or_404(session, organization_id, award_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "At least one field must be supplied")
    if any(
        changes.get(key) is None
        for key in ("title", "donor_name", "award_amount")
        if key in changes
    ):
        raise HTTPException(422, "Title, donor name and award amount cannot be cleared")
    start_date = changes.get("start_date", row.start_date)
    end_date = changes.get("end_date", row.end_date)
    if start_date and end_date and end_date < start_date:
        raise HTTPException(422, "Award end date must not precede its start date")
    if "award_amount" in changes:
        budgeted = await session.scalar(
            select(func.coalesce(func.sum(FundingBudgetLine.budget_amount), 0)).where(
                FundingBudgetLine.organization_id == organization_id,
                FundingBudgetLine.award_id == award_id,
            )
        )
        spent = await session.scalar(
            select(func.coalesce(func.sum(FundingLedgerEntry.amount), 0)).where(
                FundingLedgerEntry.organization_id == organization_id,
                FundingLedgerEntry.award_id == award_id,
                FundingLedgerEntry.entry_type == "expenditure",
            )
        )
        minimum = max(Decimal(str(budgeted or 0)), Decimal(str(spent or 0)))
        if changes["award_amount"] < minimum:
            raise HTTPException(
                409,
                "Award amount cannot be reduced below budget allocations or recorded expenditure",
            )
    for key, value in changes.items():
        setattr(
            row,
            key,
            value.strip() if isinstance(value, str) and key in {"title", "donor_name"} else value,
        )
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="award",
        entity_id=row.id,
        fields=sorted(changes),
        state={
            "title": row.title,
            "donor_name": row.donor_name,
            "award_amount": str(row.award_amount),
            "currency": row.currency,
            "status": row.status,
        },
        action="record.updated",
    )
    await session.commit()
    await session.refresh(row)
    return AwardRead.model_validate(row)


async def _award_or_404(
    session: AsyncSession,
    organization_id: str,
    award_id: str,
    *,
    lock: bool = False,
) -> FundingAward:
    statement = select(FundingAward).where(
        FundingAward.id == award_id,
        FundingAward.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    award = await session.scalar(statement)
    if award is None:
        raise HTTPException(404, "Funding award not found")
    return award


@router.get(
    "/organizations/{organization_id}/funding/awards/{award_id}/budget-lines",
    response_model=list[BudgetLineRead],
)
async def list_budget_lines(
    organization_id: str,
    award_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[BudgetLineRead]:
    await _require_funding_admin(membership, session)
    await _award_or_404(session, organization_id, award_id)
    rows = await session.scalars(
        select(FundingBudgetLine)
        .where(
            FundingBudgetLine.organization_id == organization_id,
            FundingBudgetLine.award_id == award_id,
        )
        .order_by(FundingBudgetLine.name)
        .limit(300)
    )
    return [BudgetLineRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/funding/awards/{award_id}/budget-lines",
    response_model=BudgetLineRead,
    status_code=201,
)
async def create_budget_line(
    organization_id: str,
    award_id: str,
    body: BudgetLineCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BudgetLineRead:
    await _require_funding_admin(membership, session)
    award = await _award_or_404(session, organization_id, award_id, lock=True)
    if body.programme_id:
        programme = await session.scalar(
            select(Programme).where(
                Programme.id == body.programme_id,
                Programme.organization_id == organization_id,
            )
        )
        if programme is None:
            raise HTTPException(404, "Programme not found")
    existing_total = await session.scalar(
        select(func.coalesce(func.sum(FundingBudgetLine.budget_amount), 0)).where(
            FundingBudgetLine.organization_id == organization_id,
            FundingBudgetLine.award_id == award_id,
        )
    )
    if Decimal(str(existing_total or 0)) + body.budget_amount > award.award_amount:
        raise HTTPException(409, "Budget lines cannot exceed the award amount")
    row = FundingBudgetLine(
        organization_id=organization_id,
        award_id=award_id,
        programme_id=body.programme_id,
        name=body.name.strip(),
        description=body.description,
        budget_amount=body.budget_amount,
        created_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="budget_line",
        entity_id=row.id,
        fields=["award_id", "programme_id", "name", "budget_amount"],
        state={"award_id": award_id, "name": row.name, "budget_amount": str(row.budget_amount)},
    )
    await session.commit()
    await session.refresh(row)
    return BudgetLineRead.model_validate(row)


@router.get(
    "/organizations/{organization_id}/funding/awards/{award_id}/ledger",
    response_model=list[LedgerEntryRead],
)
async def list_ledger_entries(
    organization_id: str,
    award_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[LedgerEntryRead]:
    await _require_funding_admin(membership, session)
    await _award_or_404(session, organization_id, award_id)
    rows = await session.scalars(
        select(FundingLedgerEntry)
        .where(
            FundingLedgerEntry.organization_id == organization_id,
            FundingLedgerEntry.award_id == award_id,
        )
        .order_by(FundingLedgerEntry.occurred_on.desc(), FundingLedgerEntry.created_at.desc())
        .limit(1000)
    )
    return [LedgerEntryRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/funding/awards/{award_id}/ledger",
    response_model=LedgerEntryRead,
    status_code=201,
)
async def create_ledger_entry(
    organization_id: str,
    award_id: str,
    body: LedgerEntryCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerEntryRead:
    await _require_funding_admin(membership, session)
    award = await _award_or_404(session, organization_id, award_id, lock=True)
    budget_line: FundingBudgetLine | None = None
    if body.budget_line_id:
        budget_line = await session.scalar(
            select(FundingBudgetLine).where(
                FundingBudgetLine.id == body.budget_line_id,
                FundingBudgetLine.organization_id == organization_id,
                FundingBudgetLine.award_id == award_id,
            )
        )
        if budget_line is None:
            raise HTTPException(404, "Budget line not found")
    if body.entry_type == "expenditure":
        if budget_line is not None:
            prior = await session.scalar(
                select(func.coalesce(func.sum(FundingLedgerEntry.amount), 0)).where(
                    FundingLedgerEntry.organization_id == organization_id,
                    FundingLedgerEntry.award_id == award_id,
                    FundingLedgerEntry.budget_line_id == body.budget_line_id,
                    FundingLedgerEntry.entry_type == "expenditure",
                )
            )
            if Decimal(str(prior or 0)) + body.amount > budget_line.budget_amount:
                raise HTTPException(409, "Expenditure would exceed the budget line")
        total_spend = await session.scalar(
            select(func.coalesce(func.sum(FundingLedgerEntry.amount), 0)).where(
                FundingLedgerEntry.organization_id == organization_id,
                FundingLedgerEntry.award_id == award_id,
                FundingLedgerEntry.entry_type == "expenditure",
            )
        )
        if Decimal(str(total_spend or 0)) + body.amount > award.award_amount:
            raise HTTPException(409, "Expenditure would exceed the award amount")
    row = FundingLedgerEntry(
        organization_id=organization_id,
        award_id=award_id,
        budget_line_id=body.budget_line_id,
        entry_type=body.entry_type,
        amount=body.amount,
        occurred_on=body.occurred_on,
        reference=body.reference,
        description=body.description.strip(),
        entered_by=principal.user_id,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        organization_id=organization_id,
        actor_id=principal.user_id,
        entity_type="ledger_entry",
        entity_id=row.id,
        fields=["award_id", "budget_line_id", "entry_type", "amount", "occurred_on"],
        state={
            "award_id": award_id,
            "entry_type": row.entry_type,
            "amount": str(row.amount),
            "occurred_on": row.occurred_on.isoformat(),
        },
    )
    await session.commit()
    await session.refresh(row)
    return LedgerEntryRead.model_validate(row)


async def _summary_rows(session: AsyncSession, organization_id: str) -> list[FundingSummary]:
    awards = (
        await session.scalars(
            select(FundingAward)
            .where(
                FundingAward.organization_id == organization_id,
            )
            .order_by(FundingAward.reporting_deadline.asc().nullslast(), FundingAward.title)
            .limit(500)
        )
    ).all()
    summaries: list[FundingSummary] = []
    for award in awards:
        budgeted = await session.scalar(
            select(func.coalesce(func.sum(FundingBudgetLine.budget_amount), 0)).where(
                FundingBudgetLine.organization_id == organization_id,
                FundingBudgetLine.award_id == award.id,
            )
        )
        values: dict[str, Decimal] = {}
        for kind in ("pledge", "commitment", "expenditure"):
            amount = await session.scalar(
                select(func.coalesce(func.sum(FundingLedgerEntry.amount), 0)).where(
                    FundingLedgerEntry.organization_id == organization_id,
                    FundingLedgerEntry.award_id == award.id,
                    FundingLedgerEntry.entry_type == kind,
                )
            )
            values[kind] = Decimal(str(amount or 0))
        budgeted_amount = Decimal(str(budgeted or 0))
        summaries.append(
            FundingSummary(
                award_id=award.id,
                title=award.title,
                donor_name=award.donor_name,
                currency=award.currency,
                award_amount=award.award_amount,
                budgeted_amount=budgeted_amount,
                pledged_amount=values["pledge"],
                committed_amount=values["commitment"],
                expenditure_amount=values["expenditure"],
                unallocated_amount=award.award_amount - budgeted_amount,
                reporting_deadline=award.reporting_deadline,
                status=award.status,
            )
        )
    return summaries


@router.get("/organizations/{organization_id}/funding/report", response_model=list[FundingSummary])
async def funding_report(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[FundingSummary]:
    await _require_funding_admin(membership, session)
    return await _summary_rows(session, organization_id)


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    probe = text.lstrip(" \t\r\n")
    if probe.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/organizations/{organization_id}/funding/report.csv")
async def export_funding_report(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await _require_funding_admin(membership, session)
    rows = await _summary_rows(session, organization_id)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "award_id",
            "title",
            "donor",
            "currency",
            "award_amount",
            "budgeted_amount",
            "pledged_amount",
            "committed_amount",
            "expenditure_amount",
            "unallocated_amount",
            "reporting_deadline",
            "status",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                _csv_cell(getattr(row, key))
                for key in (
                    "award_id",
                    "title",
                    "donor_name",
                    "currency",
                    "award_amount",
                    "budgeted_amount",
                    "pledged_amount",
                    "committed_amount",
                    "expenditure_amount",
                    "unallocated_amount",
                    "reporting_deadline",
                    "status",
                )
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="funding-report.csv"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/organizations/{organization_id}/funding/audit-events")
async def funding_audit_events(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    await _require_funding_admin(membership, session)
    rows = await session.scalars(
        select(FundingAuditEvent)
        .where(
            FundingAuditEvent.organization_id == organization_id,
        )
        .order_by(FundingAuditEvent.created_at.desc())
        .limit(500)
    )
    return [
        {
            "id": row.id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "changed_fields": row.changed_fields,
            "state": row.state,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows.all()
    ]
