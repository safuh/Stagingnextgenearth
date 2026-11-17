"""Add learner as a first-class organisation membership role."""

from collections.abc import Sequence

from alembic import op

revision: str = "0047_learner_membership_role"
down_revision: str | None = "0046_climate_safeguarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint(
        "ck_membership_role",
        "organization_memberships",
        "role IN ('admin','founder','executive','programme_manager','researcher',"
        "'youth_volunteer','employee','institutional_partner','learner')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE organization_memberships SET role='youth_volunteer' WHERE role='learner'"
    )
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint(
        "ck_membership_role",
        "organization_memberships",
        "role IN ('admin','founder','executive','programme_manager','researcher',"
        "'youth_volunteer','employee','institutional_partner')",
    )
