"""Tests for the Account data contract.

Coverage:
- Timestamp normalization to naive UTC.
- Required-field validation.
- Rejection of unexpected fields.
- Rejection of invalid or timezone-naive timestamps.
- Rejection of empty or whitespace-only required strings.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from gtm_analytics.contracts.account import Account


def valid_account_data() -> dict:
    return {
        "account_id": "acct-001",
        "account_name": "Example Corp",
        "industry": "Technology",
        "created_at_utc": "2026-10-23T10:00:00-04:00",
        "updated_at_utc": "2026-10-23T14:30:00Z",
    }


def test_valid_account_normalizes_timestamps_to_naive_utc() -> None:
    account = Account.model_validate(valid_account_data())

    assert account.created_at_utc == datetime(2026, 10, 23, 14, 0, 0)
    assert account.updated_at_utc == datetime(2026, 10, 23, 14, 30, 0)

    assert account.created_at_utc.tzinfo is None
    assert account.updated_at_utc.tzinfo is None


def test_missing_required_field_is_rejected() -> None:
    data = valid_account_data()
    del data["account_name"]

    with pytest.raises(ValidationError):
        Account.model_validate(data)


def test_unexpected_field_is_rejected() -> None:
    data = valid_account_data()
    data["unexpected_field"] = "not allowed"

    with pytest.raises(ValidationError):
        Account.model_validate(data)


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
    data = valid_account_data()
    data["created_at_utc"] = timestamp

    with pytest.raises(ValidationError):
        Account.model_validate(data)


@pytest.mark.parametrize(
    "field",
    ["account_id", "account_name", "industry"],
)
def test_empty_required_string_is_rejected(field: str) -> None:
    data = valid_account_data()
    data[field] = "   "

    with pytest.raises(ValidationError):
        Account.model_validate(data)
