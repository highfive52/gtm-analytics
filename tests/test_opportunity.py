"""Tests for the Opportunity data contract.

Coverage:
- Timestamp normalization to naive UTC.
- Decimal representation of opportunity amounts.
- Required-field and unexpected-field validation.
- Valid and invalid sales stages.
- Rejection of negative amounts.
- Rejection of invalid or timezone-naive timestamps.
- Optional calendar-date handling for close_date.
- Rejection of invalid calendar dates.
- Rejection of empty or whitespace-only required strings.
- Acceptance of zero amounts and rejection of negative amounts.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from gtm_analytics.contracts.opportunity import Opportunity


def valid_opportunity_data() -> dict:
    return {
        "opportunity_id": "opp-001",
        "account_id": "acct-001",
        "opportunity_name": "Enterprise Expansion",
        "stage": "evaluation",
        "amount": "25000.00",
        "created_at": "2026-10-23T10:00:00-04:00",
        "updated_at": "2026-10-23T14:30:00Z",
        "close_date": "2026-12-15",
    }


def test_valid_opportunity_normalizes_timestamps_to_naive_utc() -> None:
    opportunity = Opportunity.model_validate(valid_opportunity_data())

    assert opportunity.created_at == datetime(2026, 10, 23, 14, 0, 0)
    assert opportunity.updated_at == datetime(2026, 10, 23, 14, 30, 0)
    assert opportunity.close_date == date(2026, 12, 15)

    assert opportunity.created_at.tzinfo is None
    assert opportunity.updated_at.tzinfo is None


def test_amount_is_parsed_as_decimal() -> None:
    opportunity = Opportunity.model_validate(valid_opportunity_data())

    assert opportunity.amount == Decimal("25000.00")
    assert isinstance(opportunity.amount, Decimal)


def test_missing_required_field_is_rejected() -> None:
    data = valid_opportunity_data()
    del data["account_id"]

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


def test_unexpected_field_is_rejected() -> None:
    data = valid_opportunity_data()
    data["unexpected_field"] = "not allowed"

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


def test_invalid_stage_is_rejected() -> None:
    data = valid_opportunity_data()
    data["stage"] = "pending_review"

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


def test_negative_amount_is_rejected() -> None:
    data = valid_opportunity_data()
    data["amount"] = "-100.00"

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


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
    data = valid_opportunity_data()
    data["created_at"] = timestamp

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


def test_close_date_can_be_omitted() -> None:
    data = valid_opportunity_data()
    del data["close_date"]

    opportunity = Opportunity.model_validate(data)

    assert opportunity.close_date is None


def test_close_date_can_be_none() -> None:
    data = valid_opportunity_data()
    data["close_date"] = None

    opportunity = Opportunity.model_validate(data)

    assert opportunity.close_date is None


def test_close_date_is_parsed_as_calendar_date() -> None:
    opportunity = Opportunity.model_validate(valid_opportunity_data())

    assert opportunity.close_date == date(2026, 12, 15)
    assert isinstance(opportunity.close_date, date)
    assert not isinstance(opportunity.close_date, datetime)


def test_invalid_close_date_is_rejected() -> None:
    data = valid_opportunity_data()
    data["close_date"] = "2026-02-30"

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "opportunity_id",
        "account_id",
        "opportunity_name",
        "stage",
    ],
)
def test_empty_required_string_is_rejected(field: str) -> None:
    data = valid_opportunity_data()
    data[field] = "   "

    with pytest.raises(ValidationError):
        Opportunity.model_validate(data)


def test_zero_amount_is_valid() -> None:
    data = valid_opportunity_data()
    data["amount"] = "0.00"

    opportunity = Opportunity.model_validate(data)

    assert opportunity.amount == Decimal("0.00")