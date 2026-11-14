"""Add employee membership role for invitation onboarding."""
from collections.abc import Sequence
from alembic import op
revision: str = "0034_employee_membership_role"
down_revision: str | None = "0033_founder_executive_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint("ck_membership_role", "organization_memberships",
        "role IN ('admin','founder','executive','programme_manager','researcher','youth_volunteer','employee','institutional_partner')")

def downgrade() -> None:
    op.execute("UPDATE organization_memberships SET role='programme_manager' WHERE role='employee'")
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint("ck_membership_role", "organization_memberships",
        "role IN ('admin','founder','executive','programme_manager','researcher','youth_volunteer','institutional_partner')")
