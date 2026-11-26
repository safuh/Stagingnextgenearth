"""Allow governed climate insight records in the public CMS."""

from collections.abc import Sequence

from alembic import op

revision: str = "0066_climate_insight_type"
down_revision: str | None = "0065_climate_public_releases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("public_content_entries") as batch_op:
        batch_op.drop_constraint("ck_public_content_type", type_="check")
        batch_op.create_check_constraint(
            "ck_public_content_type",
            "content_type IN ('page','programme','training_track','initiative',"
            "'research_area','impact_metric','publication','climate_insight')",
        )


def downgrade() -> None:
    with op.batch_alter_table("public_content_entries") as batch_op:
        batch_op.drop_constraint("ck_public_content_type", type_="check")
        batch_op.create_check_constraint(
            "ck_public_content_type",
            "content_type IN ('page','programme','training_track','initiative',"
            "'research_area','impact_metric','publication')",
        )
