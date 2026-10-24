from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class FeatureUsedProperties(BaseModel):
    """Properties for a product feature usage event."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    feature_name: str = Field(min_length=1)
    action: Literal[
        "viewed",
        "created",
        "edited",
        "published",
        "exported",
    ]


class CampaignPublishedProperties(BaseModel):
    """Properties for a campaign publication event."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    campaign_id: str = Field(min_length=1)
    channel: Literal["email", "sms", "push"]


class ReportViewedProperties(BaseModel):
    """Properties for a report viewing event."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    report_type: Literal[
        "campaign_performance",
        "revenue_attribution",
        "engagement",
    ]


class Activity(BaseModel):
    """Validated activity event for the GTM analytics platform."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    activity_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)

    event_name: Literal[
        "feature_used",
        "campaign_published",
        "report_viewed",
        "meeting",
        "email",
    ]

    activity_timestamp: datetime
    source: str = Field(min_length=1)

    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("activity_timestamp")
    @classmethod
    def normalize_timestamp_to_naive_utc(
        cls,
        value: datetime,
    ) -> datetime:
        """Require timezone-aware input and normalize it to naive UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include timezone information")

        return value.astimezone(UTC).replace(tzinfo=None)

    @model_validator(mode="after")
    def validate_event_properties(self) -> "Activity":
        """Validate properties against the schema for each product event."""
        property_models = {
            "feature_used": FeatureUsedProperties,
            "campaign_published": CampaignPublishedProperties,
            "report_viewed": ReportViewedProperties,
        }

        properties_model = property_models.get(self.event_name)

        if properties_model is not None:
            validated_properties = properties_model.model_validate(
                self.properties
            )
            self.properties = validated_properties.model_dump()

        return self