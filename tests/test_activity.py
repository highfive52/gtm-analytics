"""Coverage:
- Timestamp normalization to naive UTC.
- Required-field validation.
- Rejection of unexpected top-level fields.
- Rejection of unsupported event names.
- Rejection of invalid or timezone-naive timestamps.
- Rejection of empty or whitespace-only required strings.
- Default and explicitly supplied event properties.
- Event-specific property validation for feature usage,
  campaign publication, and report viewing.
- Rejection of missing required properties, invalid values,
  and unexpected event-specific properties.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from gtm_analytics.contracts.activity import Activity


def valid_activity_data() -> dict:
    return {
        "activity_id": "act-001",
        "account_id": "acct-001",
        "event_name": "feature_used",
        "activity_timestamp": "2026-10-23T10:00:00-04:00",
        "source": "product_analytics",
        "properties": {
            "feature_name": "campaign_builder",
            "action": "published",
        },
    }


def test_valid_activity_normalizes_timestamp_to_naive_utc() -> None:
    activity = Activity.model_validate(valid_activity_data())

    assert activity.activity_timestamp == datetime(2026, 10, 23, 14, 0, 0)
    assert activity.activity_timestamp.tzinfo is None


def test_missing_required_field_is_rejected() -> None:
    data = valid_activity_data()
    del data["account_id"]

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_unexpected_field_is_rejected() -> None:
    data = valid_activity_data()
    data["unexpected_field"] = "not allowed"

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_invalid_activity_type_is_rejected() -> None:
    data = valid_activity_data()
    data["event_name"] = "phone_call"

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-timestamp",
        "2026-10-23T14:00:00",
    ],
)
def test_invalid_or_timezone_naive_timestamp_is_rejected(
    timestamp: str,
) -> None:
    data = valid_activity_data()
    data["activity_timestamp"] = timestamp

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


@pytest.mark.parametrize(
    "field",
    ["activity_id", "account_id", "source"],
)
def test_empty_required_string_is_rejected(field: str) -> None:
    data = valid_activity_data()
    data[field] = "   "

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_properties_default_to_empty_dictionary() -> None:
    data = valid_activity_data()
    data["event_name"] = "meeting"
    del data["properties"]

    activity = Activity.model_validate(data)

    assert activity.properties == {}


def test_explicit_properties_are_preserved() -> None:
    data = valid_activity_data()

    activity = Activity.model_validate(data)

    assert activity.properties == {
        "feature_name": "campaign_builder",
        "action": "published",
    }


def test_feature_used_requires_feature_name() -> None:
    data = valid_activity_data()
    data["properties"] = {"action": "published"}

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_feature_used_rejects_invalid_action() -> None:
    data = valid_activity_data()
    data["properties"]["action"] = "deleted"

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_product_event_rejects_unexpected_property() -> None:
    data = valid_activity_data()
    data["properties"]["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_campaign_published_properties_are_validated() -> None:
    data = valid_activity_data()
    data["event_name"] = "campaign_published"
    data["properties"] = {
        "campaign_id": "campaign-001",
        "channel": "email",
    }

    activity = Activity.model_validate(data)

    assert activity.properties == {
        "campaign_id": "campaign-001",
        "channel": "email",
    }


def test_report_viewed_rejects_invalid_report_type() -> None:
    data = valid_activity_data()
    data["event_name"] = "report_viewed"
    data["properties"] = {"report_type": "unknown_report"}

    with pytest.raises(ValidationError):
        Activity.model_validate(data)


def test_meeting_can_have_empty_properties() -> None:
    data = valid_activity_data()
    data["event_name"] = "meeting"
    data["properties"] = {}

    activity = Activity.model_validate(data)

    assert activity.properties == {}

def test_feature_used_requires_action() -> None:
    data = valid_activity_data()
    data["properties"] = {"feature_name": "campaign_builder"}

    with pytest.raises(ValidationError):
        Activity.model_validate(data)