"""Create individual programme activity attendance records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045_activity_attendance"
down_revision: str | None = "0044_activity_volunteer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programme_activity_attendance",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("programme_id", sa.String(length=36), nullable=False),
        sa.Column("activity_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("attendance_status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=1000), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attendance_status IN ('present', 'late', 'absent', 'excused')",
            name="ck_activity_attendance_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_id"], ["programme_activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("activity_id", "user_id", name="uq_activity_attendance_user"),
    )
    op.create_index(
        "ix_activity_attendance_org_activity",
        "programme_activity_attendance",
        ["organization_id", "activity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_attendance_org_activity", table_name="programme_activity_attendance")
    op.drop_table("programme_activity_attendance")
