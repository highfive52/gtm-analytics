from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from gtm_analytics.contracts.opportunity_snapshot import OpportunitySnapshot


def test_valid_opportunity_snapshot() -> None:
    snapshot = OpportunitySnapshot(
        opportunity_id="opp-001",
        account_id="acct-001",
        snapshot_date=date(2026, 10, 19),
        stage="evaluation",
        amount=Decimal("25000.00"),
    )

    assert snapshot.opportunity_id == "opp-001"
    assert snapshot.account_id == "acct-001"
    assert snapshot.stage == "evaluation"
    assert snapshot.amount == Decimal("25000.00")


def test_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        OpportunitySnapshot(
            opportunity_id="opp-001",
            account_id="acct-001",
            snapshot_date=date(2026, 10, 19),
            stage="evaluation",
            amount=Decimal(-1),
        )


def test_rejects_invalid_stage() -> None:
    with pytest.raises(ValidationError):
        OpportunitySnapshot(
            opportunity_id="opp-001",
            account_id="acct-001",
            snapshot_date=date(2026, 10, 19),
            stage="unqualified",
            amount=Decimal(1000),
        )


def test_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        OpportunitySnapshot(
            opportunity_id="opp-001",
            account_id="acct-001",
            snapshot_date=date(2026, 10, 19),
            stage="evaluation",
            amount=Decimal(1000),
            is_closed=False,
        )
