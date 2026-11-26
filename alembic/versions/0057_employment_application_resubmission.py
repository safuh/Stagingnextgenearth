"""Allow withdrawn or rejected employment applications to be resubmitted."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_employment_resubmit"
down_revision: str | None = "0056_research_governance_audit"
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
    op.drop_index(
        "uq_employment_applications_org_user_pending",
        table_name="organization_employment_applications",
    )
    with op.batch_alter_table("organization_employment_applications") as batch:
        batch.create_unique_constraint(
            "uq_employment_application_org_user",
            ["organization_id", "user_id"],
        )
