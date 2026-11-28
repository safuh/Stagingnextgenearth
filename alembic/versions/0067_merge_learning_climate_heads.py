"""Merge the learning cohort and climate insight migration heads."""

from collections.abc import Sequence

revision: str = "0067_merge_lrn_climate"
down_revision: tuple[str, str] = (
    "0065_learning_cohorts",
    "0066_climate_insight_type",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the independently developed learning and climate schema branches."""


def downgrade() -> None:
    """The merge revision has no schema operations to reverse."""
