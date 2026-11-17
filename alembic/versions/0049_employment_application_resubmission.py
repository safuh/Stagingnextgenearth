"""Allow candidates to resubmit after withdrawing or receiving a decision."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_employment_resubmission"
down_revision: str | None = "0048_membership_role_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organization_employment_applications") as batch:
        batch.drop_constraint("uq_employment_application_org_user", type_="unique")
    op.create_index(
        "uq_employment_applications_org_user_pending",
        "organization_employment_applications",
        ["organization_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM organization_employment_applications "
            "GROUP BY organization_id, user_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot restore one-application-per-user uniqueness while resubmission history exists"
        )
    op.drop_index(
        "uq_employment_applications_org_user_pending",
        table_name="organization_employment_applications",
    )
    with op.batch_alter_table("organization_employment_applications") as batch:
        batch.create_unique_constraint(
            "uq_employment_application_org_user",
            ["organization_id", "user_id"],
        )
