"""Add funder as a distinct organisation membership role."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0071_funder_membership_role"
down_revision: str | None = "0070_identity_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ROLES = (
    "'admin', 'founder', 'executive', 'programme_manager', 'researcher', "
    "'youth_volunteer', 'employee', 'institutional_partner', 'funder', 'learner'"
)


def upgrade() -> None:
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint(
        "ck_membership_role", "organization_memberships", f"role IN ({_ROLES})"
    )
    op.drop_constraint(
        "ck_membership_role_assignment", "organization_membership_roles", type_="check"
    )
    op.create_check_constraint(
        "ck_membership_role_assignment",
        "organization_membership_roles",
        f"role IN ({_ROLES})",
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_funder_memberships = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM organization_memberships WHERE role = 'funder') "
            "OR EXISTS (SELECT 1 FROM organization_membership_roles WHERE role = 'funder')"
        )
    ).scalar_one()
    if has_funder_memberships:
        raise RuntimeError(
            "Cannot downgrade funder role while funder memberships exist; "
            "migrate or reassign them first"
        )
    op.drop_constraint("ck_membership_role", "organization_memberships", type_="check")
    op.create_check_constraint(
        "ck_membership_role",
        "organization_memberships",
        "role IN ('admin', 'founder', 'executive', 'programme_manager', 'researcher', "
        "'youth_volunteer', 'employee', 'institutional_partner', 'learner')",
    )
    op.drop_constraint(
        "ck_membership_role_assignment", "organization_membership_roles", type_="check"
    )
    op.create_check_constraint(
        "ck_membership_role_assignment",
        "organization_membership_roles",
        "role IN ('admin', 'programme_manager', 'founder', 'executive', 'employee', "
        "'researcher', 'youth_volunteer', 'institutional_partner', 'learner')",
    )
