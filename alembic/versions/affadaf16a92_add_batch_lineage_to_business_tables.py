"""add batch lineage to business tables

Revision ID: affadaf16a92
Revises: d1840f70a61f
Create Date: 2026-10-26 15:47:43.187752
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "affadaf16a92"
down_revision: str | Sequence[str] | None = "d1840f70a61f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "accounts",
    "activities",
    "opportunities",
    "opportunity_snapshots",
)


def upgrade() -> None:
    """Add and backfill ingestion lineage columns."""
    # Add columns as nullable so existing rows remain valid.
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("batch_id", sa.String(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column(
                "ingested_at_utc",
                sa.TIMESTAMP(timezone=False),
                nullable=True,
            ),
        )

    # Use one timestamp for the entire backfill.
    backfill_timestamp = sa.text("timezone('UTC', now())")

    for table in TABLES:
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET batch_id = :batch_id,
                    ingested_at_utc = {backfill_timestamp}
                WHERE batch_id IS NULL
                   OR ingested_at_utc IS NULL
                """
            ).bindparams(batch_id="baseline_v2")
        )

    # Enforce the final schema after all existing rows are populated.
    for table in TABLES:
        op.alter_column(
            table,
            "batch_id",
            existing_type=sa.String(),
            nullable=False,
        )
        op.alter_column(
            table,
            "ingested_at_utc",
            existing_type=sa.TIMESTAMP(timezone=False),
            nullable=False,
        )


def downgrade() -> None:
    """Remove ingestion lineage columns."""
    for table in reversed(TABLES):
        op.drop_column(table, "ingested_at_utc")
        op.drop_column(table, "batch_id")
