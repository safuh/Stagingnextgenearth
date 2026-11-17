"""Introduce a normalized role-assignment table for organisation memberships.

The legacy Membership.role column remains the primary-role compatibility field.
Existing memberships are backfilled so this migration does not change access.
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0048_membership_role_assignments"
down_revision: str | None = "0047_learner_membership_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization_membership_roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "membership_id",
            sa.String(length=36),
            sa.ForeignKey("organization_memberships.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "membership_id", "role", name="uq_membership_role_assignment"
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'founder', 'executive', 'programme_manager', "
            "'researcher', 'youth_volunteer', 'employee', "
            "'institutional_partner', 'learner')",
            name="ck_membership_role_assignment",
        ),
    )
    op.create_index(
        "ix_membership_roles_membership_role",
        "organization_membership_roles",
        ["membership_id", "role"],
    )

    connection = op.get_bind()
    memberships = connection.execute(
        sa.text(
            "SELECT id, role, created_at FROM organization_memberships"
        )
    ).mappings()
    for membership in memberships:
        connection.execute(
            sa.text(
                "INSERT INTO organization_membership_roles "
                "(id, membership_id, role, created_at) "
                "VALUES (:id, :membership_id, :role, :created_at)"
            ),
            {
                "id": str(uuid4()),
                "membership_id": membership["id"],
                "role": membership["role"],
                "created_at": membership["created_at"],
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_membership_roles_membership_role",
        table_name="organization_membership_roles",
    )
    op.drop_table("organization_membership_roles")
