from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Opportunity(BaseModel):
    """Validated opportunity record for the GTM analytics platform."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    opportunity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    opportunity_name: str = Field(min_length=1)

    stage: Literal[
        "qualification",
        "discovery",
        "evaluation",
        "proposal",
        "negotiation",
        "closed_won",
        "closed_lost",
    ]

    amount: Decimal = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    close_date: date | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_timestamp_to_naive_utc(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        """Require timezone-aware input and normalize it to naive UTC."""
        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include timezone information")

        return value.astimezone(UTC).replace(tzinfo=None)