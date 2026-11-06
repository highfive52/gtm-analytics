from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Account(BaseModel):
    """Validated account record for the GTM analytics platform."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    account_id: str = Field(min_length=1)
    account_name: str = Field(min_length=1)
    industry: str = Field(min_length=1)

    created_at_utc: datetime
    updated_at_utc: datetime

    @field_validator("created_at_utc", "updated_at_utc")
    @classmethod
    def normalize_timestamp_to_naive_utc(
        cls,
        value: datetime,
    ) -> datetime:
        """Require timezone-aware input and normalize it to naive UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include timezone information")

        return value.astimezone(UTC).replace(tzinfo=None)
