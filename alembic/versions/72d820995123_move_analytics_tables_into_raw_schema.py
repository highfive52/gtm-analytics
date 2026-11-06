"""move analytics tables into raw schema

Revision ID: 72d820995123
Revises: affadaf16a92
Create Date: 2026-10-28 17:14:42.144299

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "72d820995123"
down_revision: str | Sequence[str] | None = "affadaf16a92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Move application tables from public into raw."""
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for table_name in (
        "accounts",
        "activities",
        "opportunities",
        "opportunity_snapshots",
        "batch_audit",
    ):
        op.execute(f"ALTER TABLE public.{table_name} SET SCHEMA raw")


def downgrade() -> None:
    """Move application tables back into public."""
    for table_name in (
        "batch_audit",
        "opportunity_snapshots",
        "activities",
        "opportunities",
        "accounts",
    ):
        op.execute(f"ALTER TABLE raw.{table_name} SET SCHEMA public")

    op.execute("DROP SCHEMA raw")
