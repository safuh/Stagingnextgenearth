"""Add append-only audit events for organisation people.

Revision ID: 0031_organization_people_audit
Revises: 0030_organization_people
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_organization_people_audit"
down_revision: str | None = "0030_organization_people"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_person_audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.String(length=36),
            sa.ForeignKey("organization_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "action IN ('person.created', 'person.updated', 'person.review_changed', "
            "'person.publication_changed', 'person.archived', 'person.reactivated')",
            name="ck_org_person_audit_action",
        ),
    )
    op.create_index(
        "ix_org_person_audit_org_person_time",
        "organization_person_audit_events",
        ["organization_id", "person_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_person_audit_org_person_time",
        table_name="organization_person_audit_events",
    )
    op.drop_table("organization_person_audit_events")
