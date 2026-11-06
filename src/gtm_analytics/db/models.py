from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gtm_analytics.db.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__: ClassVar[dict[str, str]] = {"schema": "raw"}

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String, nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )

    batch_id: Mapped[str] = mapped_column(String, nullable=False)

    ingested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
    )


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "event_name IN "
            "('feature_used', 'campaign_published', 'report_viewed', "
            "'meeting', 'email')",
            name="ck_activities_event_name",
        ),
        Index("ix_activities_account_id", "account_id"),
        Index("ix_activities_activity_timestamp_utc", "activity_timestamp_utc"),
        Index(
            "ix_activities_account_timestamp",
            "account_id",
            "activity_timestamp_utc",
        ),
        {"schema": "raw"},
    )

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("raw.accounts.account_id"),
        nullable=False,
    )

    event_name: Mapped[str] = mapped_column(String, nullable=False)
    activity_timestamp_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    batch_id: Mapped[str] = mapped_column(String, nullable=False)

    ingested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
    )


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "stage IN "
            "('qualification', 'discovery', 'evaluation', 'proposal', "
            "'negotiation', 'closed_won', 'closed_lost')",
            name="ck_opportunities_stage",
        ),
        CheckConstraint("amount >= 0", name="ck_opportunities_amount_nonnegative"),
        Index("ix_opportunities_account_id", "account_id"),
        {"schema": "raw"},
    )

    opportunity_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("raw.accounts.account_id"),
        nullable=False,
    )
    opportunity_name: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)

    created_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    batch_id: Mapped[str] = mapped_column(String, nullable=False)

    ingested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
    )


class OpportunitySnapshot(Base):
    __tablename__ = "opportunity_snapshots"
    __table_args__ = (
        CheckConstraint(
            "stage IN "
            "('qualification', 'discovery', 'evaluation', 'proposal', "
            "'negotiation', 'closed_won', 'closed_lost')",
            name="ck_opportunity_snapshots_stage",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_opportunity_snapshots_amount_nonnegative",
        ),
        Index("ix_opportunity_snapshots_account_date", "account_id", "snapshot_date"),
        {"schema": "raw"},
    )

    opportunity_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("raw.opportunities.opportunity_id"),
        primary_key=True,
    )
    account_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("raw.accounts.account_id"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(), nullable=False)

    batch_id: Mapped[str] = mapped_column(String, nullable=False)

    ingested_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False),
        nullable=False,
    )


class BatchAudit(Base):
    __tablename__ = "batch_audit"
    __table_args__ = (
        CheckConstraint(
            "status IN ('loading', 'completed', 'failed')",
            name="ck_batch_audit_status",
        ),
        {"schema": "raw"},
    )

    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_prefix: Mapped[str] = mapped_column(String, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False)

    started_at_utc: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=False), nullable=False
    )
    completed_at_utc: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=False), nullable=True
    )

    record_counts: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
