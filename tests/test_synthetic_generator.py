from datetime import timedelta

import pytest

from gtm_analytics.synthetic.generator import (
    BASE_DATE,
    SNAPSHOT_COUNT,
    SNAPSHOT_INTERVAL_DAYS,
    activity_volume_for_week,
    generate_accounts,
    generate_activities,
    generate_opportunities,
    generate_opportunity_snapshots,
)


def test_generate_accounts_count_and_unique_ids() -> None:
    accounts = generate_accounts()

    assert len(accounts) == 24
    assert len({account.account_id for account in accounts}) == 24


def test_generate_accounts_are_deterministic() -> None:
    assert generate_accounts() == generate_accounts()


def test_generate_opportunities_match_accounts() -> None:
    accounts = generate_accounts()
    opportunities = generate_opportunities(accounts)

    assert len(opportunities) == len(accounts)
    assert {opportunity.account_id for opportunity in opportunities} == {
        account.account_id for account in accounts
    }


def test_generate_opportunities_are_deterministic() -> None:
    accounts = generate_accounts()

    assert generate_opportunities(accounts) == generate_opportunities(accounts)


def test_generate_opportunity_snapshots_count() -> None:
    accounts = generate_accounts()
    opportunities = generate_opportunities(accounts)

    snapshots = generate_opportunity_snapshots(opportunities)

    assert len(snapshots) == 288


def test_generate_opportunity_snapshots_have_unique_opportunity_dates() -> None:
    accounts = generate_accounts()
    opportunities = generate_opportunities(accounts)

    snapshots = generate_opportunity_snapshots(opportunities)

    keys = [(snapshot.opportunity_id, snapshot.snapshot_date) for snapshot in snapshots]

    assert len(keys) == len(set(keys))


def test_generate_opportunity_snapshots_match_current_stages() -> None:
    accounts = generate_accounts()
    opportunities = generate_opportunities(accounts)

    snapshots = generate_opportunity_snapshots(opportunities)
    latest_date = max(snapshot.snapshot_date for snapshot in snapshots)

    latest_by_opportunity = {
        snapshot.opportunity_id: snapshot
        for snapshot in snapshots
        if snapshot.snapshot_date == latest_date
    }

    for opportunity in opportunities:
        assert (
            latest_by_opportunity[opportunity.opportunity_id].stage == opportunity.stage
        )


def test_activity_volume_increases_for_rising_usage() -> None:
    volumes = [
        activity_volume_for_week("rising_usage_stalled", week) for week in range(12)
    ]

    assert volumes == sorted(volumes)
    assert volumes[-1] > volumes[0]


def test_activity_volume_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        activity_volume_for_week("unknown_scenario", 0)

    with pytest.raises(ValueError):
        activity_volume_for_week("rising_usage_stalled", 12)


def test_generate_activities_is_deterministic() -> None:
    accounts = generate_accounts()

    assert generate_activities(accounts) == generate_activities(accounts)


def test_generate_activities_have_unique_ids() -> None:
    activities = generate_activities(generate_accounts())

    activity_ids = [activity.activity_id for activity in activities]

    assert len(activity_ids) == len(set(activity_ids))


def test_generate_activities_reference_valid_accounts() -> None:
    accounts = generate_accounts()
    activities = generate_activities(accounts)
    account_ids = {account.account_id for account in accounts}

    assert all(activity.account_id in account_ids for activity in activities)


def test_generate_activities_use_validated_product_events() -> None:
    activities = generate_activities(generate_accounts())

    assert activities
    assert {activity.event_name for activity in activities} <= {
        "feature_used",
        "campaign_published",
        "report_viewed",
    }


def test_generate_activities_timestamps_within_observation_window() -> None:
    activities = generate_activities(generate_accounts())

    window_start_utc = (
        BASE_DATE - timedelta(days=SNAPSHOT_COUNT * SNAPSHOT_INTERVAL_DAYS)
    ).replace(tzinfo=None)
    window_end_utc = BASE_DATE.replace(tzinfo=None)

    assert activities
    assert all(
        window_start_utc <= activity.activity_timestamp_utc <= window_end_utc
        for activity in activities
    )


def test_temporary_spike_is_not_sustained_growth() -> None:
    volumes = [
        activity_volume_for_week("temporary_usage_spike", week)
        for week in range(SNAPSHOT_COUNT)
    ]

    assert volumes[7] > volumes[6]
    assert volumes[8] < volumes[7]
    assert volumes[8] == volumes[6]
