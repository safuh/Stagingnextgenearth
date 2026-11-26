"""Guard PostgreSQL's Alembic version_num width for every migration."""

import ast
from pathlib import Path


def test_revision_identifiers_fit_alembic_version_column() -> None:
    versions = Path(__file__).parents[1] / "alembic" / "versions"
    revisions: list[str] = []
    for path in versions.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "revision"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                revisions.append(node.value.value)
    assert revisions, "Alembic migration revisions must be discoverable"
    assert len(revisions) == len(set(revisions)), "Migration revision IDs must be unique"
    assert all(len(revision) <= 32 for revision in revisions), (
        "Alembic revision IDs must fit the PostgreSQL version_num VARCHAR(32) column"
    )
