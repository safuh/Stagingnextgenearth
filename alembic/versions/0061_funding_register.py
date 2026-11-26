"""Add tenant-scoped grant and funding register."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_funding_register"
down_revision: str | None = "0060_odk_form_cursors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "funding_opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("donor_name", sa.String(240), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("reference_url", sa.String(1000)),
        sa.Column("deadline", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False, server_default="identified"),
        sa.Column("expected_amount", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('identified','reviewing','submitted','awarded','declined','closed')",
            name="ck_funding_opportunity_status",
        ),
        sa.CheckConstraint(
            "expected_amount IS NULL OR expected_amount >= 0", name="ck_funding_opportunity_amount"
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_funding_opportunity_currency"),
    )
    op.create_index(
        "ix_funding_opportunities_org_deadline",
        "funding_opportunities",
        ["organization_id", "deadline"],
    )
    op.create_table(
        "funding_awards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            sa.String(36),
            sa.ForeignKey("funding_opportunities.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "partner_id",
            sa.String(36),
            sa.ForeignKey("institutional_partners.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("donor_name", sa.String(240), nullable=False),
        sa.Column("award_reference", sa.String(120)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("award_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("restrictions", sa.Text()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("reporting_deadline", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','completed','suspended','closed')",
            name="ck_funding_award_status",
        ),
        sa.CheckConstraint("award_amount >= 0", name="ck_funding_award_amount"),
        sa.CheckConstraint("length(currency) = 3", name="ck_funding_award_currency"),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_funding_award_date_order",
        ),
    )
    op.create_index("ix_funding_awards_org_status", "funding_awards", ["organization_id", "status"])
    op.create_table(
        "funding_budget_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "award_id",
            sa.String(36),
            sa.ForeignKey("funding_awards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "programme_id", sa.String(36), sa.ForeignKey("programmes.id", ondelete="SET NULL")
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("budget_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("budget_amount >= 0", name="ck_funding_budget_line_amount"),
    )
    op.create_index(
        "ix_funding_budget_lines_org_award", "funding_budget_lines", ["organization_id", "award_id"]
    )
    op.create_table(
        "funding_ledger_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "award_id",
            sa.String(36),
            sa.ForeignKey("funding_awards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "budget_line_id",
            sa.String(36),
            sa.ForeignKey("funding_budget_lines.id", ondelete="SET NULL"),
        ),
        sa.Column("entry_type", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(120)),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column(
            "entered_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "entry_type IN ('pledge','commitment','expenditure')",
            name="ck_funding_ledger_entry_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_funding_ledger_entry_amount"),
    )
    op.create_index(
        "ix_funding_ledger_org_award_date",
        "funding_ledger_entries",
        ["organization_id", "award_id", "occurred_on"],
    )
    op.create_table(
        "funding_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(24), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "entity_type IN ('opportunity','award','budget_line','ledger_entry')",
            name="ck_funding_audit_entity_type",
        ),
        sa.CheckConstraint(
            "action IN ('record.created','record.updated')", name="ck_funding_audit_action"
        ),
    )
    op.create_index(
        "ix_funding_audit_org_time", "funding_audit_events", ["organization_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_funding_audit_org_time", table_name="funding_audit_events")
    op.drop_table("funding_audit_events")
    op.drop_index("ix_funding_ledger_org_award_date", table_name="funding_ledger_entries")
    op.drop_table("funding_ledger_entries")
    op.drop_index("ix_funding_budget_lines_org_award", table_name="funding_budget_lines")
    op.drop_table("funding_budget_lines")
    op.drop_index("ix_funding_awards_org_status", table_name="funding_awards")
    op.drop_table("funding_awards")
    op.drop_index("ix_funding_opportunities_org_deadline", table_name="funding_opportunities")
    op.drop_table("funding_opportunities")
