# ruff: noqa: E501, I001
# fmt: off
"""Add founder and executive organisation roles."""
from collections.abc import Sequence
from alembic import op

revision: str = "0033_founder_executive_roles"
down_revision: str | None = "0032_partner_cms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint("ck_membership_role", "organization_memberships",
        "role IN ('admin','founder','executive','programme_manager','researcher','youth_volunteer','institutional_partner')")

def downgrade() -> None:
    op.execute("UPDATE organization_memberships SET role='admin' WHERE role IN ('founder','executive')")
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint("ck_membership_role", "organization_memberships",
        "role IN ('admin','programme_manager','researcher','youth_volunteer','institutional_partner')")

# fmt: on
