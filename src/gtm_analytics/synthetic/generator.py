from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from gtm_analytics.contracts.account import Account
from gtm_analytics.contracts.activity import Activity
from gtm_analytics.contracts.opportunity import Opportunity
from gtm_analytics.contracts.opportunity_snapshot import OpportunitySnapshot

SCENARIOS = (
    "rising_usage_stalled",
    "rising_usage_progressing",
    "declining_usage_stalled",
    "consistently_low_usage",
    "temporary_usage_spike",
    "opportunity_resolved",
)

ACCOUNTS_PER_SCENARIO = 4
BASE_DATE = datetime(2026, 10, 19, tzinfo=UTC)

SNAPSHOT_COUNT = 12
SNAPSHOT_INTERVAL_DAYS = 7

OpportunityStage = Literal[
    "qualification",
    "discovery",
    "evaluation",
    "proposal",
    "negotiation",
    "closed_won",
    "closed_lost",
]

STALLED_STAGE: OpportunityStage = "discovery"

SCENARIO_STAGE_HISTORY: dict[str, tuple[OpportunityStage, ...]] = {
    "rising_usage_stalled": (STALLED_STAGE,) * SNAPSHOT_COUNT,
    "rising_usage_progressing": (
        ("qualification",) * 4 + ("discovery",) * 4 + ("evaluation",) * 4
    ),
    "declining_usage_stalled": (STALLED_STAGE,) * SNAPSHOT_COUNT,
    "consistently_low_usage": (STALLED_STAGE,) * SNAPSHOT_COUNT,
    "temporary_usage_spike": (STALLED_STAGE,) * SNAPSHOT_COUNT,
    "opportunity_resolved": (("discovery",) * 8 + ("closed_won",) * 4),
}


def scenario_for_account_index(index: int) -> str:
    """Return the scenario assigned to a one-based account index."""
    if index < 1 or index > len(SCENARIOS) * ACCOUNTS_PER_SCENARIO:
        raise ValueError(f"Account index out of range: {index}")

    return SCENARIOS[(index - 1) // ACCOUNTS_PER_SCENARIO]


def stage_history_for_opportunity(index: int) -> tuple[OpportunityStage, ...]:
    """Return the deterministic stage history for a one-based opportunity index."""
    scenario = scenario_for_account_index(index)
    history = SCENARIO_STAGE_HISTORY[scenario]

    if scenario != "opportunity_resolved":
        return history

    terminal_stage: OpportunityStage = "closed_won" if index % 2 == 0 else "closed_lost"
    return history[:-4] + (terminal_stage,) * 4


def activity_volume_for_week(scenario: str, week_index: int) -> int:
    """Return expected activity volume for a zero-based observation week."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")

    if not 0 <= week_index < SNAPSHOT_COUNT:
        raise ValueError(f"Week index out of range: {week_index}")

    if scenario == "rising_usage_stalled":
        return 3 + week_index * 2

    if scenario == "rising_usage_progressing":
        return 3 + week_index * 2

    if scenario == "declining_usage_stalled":
        return max(1, 25 - week_index * 2)

    if scenario == "consistently_low_usage":
        return 2

    if scenario == "temporary_usage_spike":
        return 3 + (20 if week_index == 7 else 0)

    # Opportunity resolved: moderate usage before resolution,
    # followed by lower activity after the opportunity closes.
    return 8 if week_index < 8 else 3


def generate_activities(accounts: list[Account]) -> list[Activity]:
    """Generate deterministic activity events for each account."""
    activities: list[Activity] = []
    event_number = 0

    for account_index, account in enumerate(accounts, start=1):
        scenario = scenario_for_account_index(account_index)

        for week_index in range(SNAPSHOT_COUNT):
            volume = activity_volume_for_week(scenario, week_index)

            for event_index in range(volume):
                event_number += 1
                event_type = event_number % 3

                if event_type == 0:
                    event_name = "feature_used"
                    properties = {
                        "feature_name": (
                            "audience_builder",
                            "campaign_editor",
                            "analytics_dashboard",
                        )[event_index % 3],
                        "action": (
                            "viewed",
                            "created",
                            "edited",
                            "published",
                            "exported",
                        )[event_index % 5],
                    }
                elif event_type == 1:
                    event_name = "campaign_published"
                    properties = {
                        "campaign_id": f"camp-{event_number:05d}",
                        "channel": ("email", "sms", "push")[event_index % 3],
                    }
                else:
                    event_name = "report_viewed"
                    properties = {
                        "report_type": (
                            "campaign_performance",
                            "revenue_attribution",
                            "engagement",
                        )[event_index % 3],
                    }

                week_start = BASE_DATE - timedelta(
                    days=SNAPSHOT_INTERVAL_DAYS * (SNAPSHOT_COUNT - week_index)
                )

                activity_timestamp_utc = week_start + timedelta(
                    days=event_index % 7,
                    hours=9 + event_index % 9,
                    minutes=(event_number * 7) % 60,
                )

                activities.append(
                    Activity(
                        activity_id=f"activity-{event_number:06d}",
                        account_id=account.account_id,
                        event_name=event_name,
                        activity_timestamp_utc=activity_timestamp_utc,
                        source="synthetic",
                        properties=properties,
                    )
                )

    return activities


def generate_accounts() -> list[Account]:
    """Generate deterministic synthetic accounts."""
    accounts: list[Account] = []

    for scenario_index, _scenario in enumerate(SCENARIOS, start=1):
        for account_index in range(1, ACCOUNTS_PER_SCENARIO + 1):
            account_number = (
                scenario_index - 1
            ) * ACCOUNTS_PER_SCENARIO + account_index
            created_at_utc = BASE_DATE - timedelta(days=180 + account_number)

            accounts.append(
                Account(
                    account_id=f"acct-{account_number:03d}",
                    account_name=f"Example Account {account_number:03d}",
                    industry=("Technology", "Finance", "Healthcare", "Retail")[
                        (account_number - 1) % 4
                    ],
                    created_at_utc=created_at_utc,
                    updated_at_utc=BASE_DATE,
                )
            )

    return accounts


def generate_opportunities(accounts: list[Account]) -> list[Opportunity]:
    """Generate one deterministic opportunity for each account."""
    opportunities: list[Opportunity] = []

    for index, account in enumerate(accounts, start=1):
        stage = stage_history_for_opportunity(index)[-1]
        created_at_utc = BASE_DATE - timedelta(days=90 + index)

        close_date = (
            (BASE_DATE - timedelta(days=7 * 3)).date()
            if stage in ("closed_won", "closed_lost")
            else None
        )

        opportunities.append(
            Opportunity(
                opportunity_id=f"opp-{index:03d}",
                account_id=account.account_id,
                opportunity_name=f"Opportunity {index:03d}",
                stage=stage,
                amount=Decimal(10000 + index * 1250),
                created_at_utc=created_at_utc,
                updated_at_utc=BASE_DATE,
                close_date=close_date,
            )
        )

    return opportunities


def generate_opportunity_snapshots(
    opportunities: list[Opportunity],
) -> list[OpportunitySnapshot]:
    """Generate deterministic weekly snapshots for each opportunity."""
    snapshots: list[OpportunitySnapshot] = []

    for index, opportunity in enumerate(opportunities, start=1):
        stage_history = stage_history_for_opportunity(index)

        for snapshot_index, stage in enumerate(stage_history):
            snapshot_date = BASE_DATE.date() - timedelta(
                days=SNAPSHOT_INTERVAL_DAYS * (SNAPSHOT_COUNT - 1 - snapshot_index)
            )

            snapshots.append(
                OpportunitySnapshot(
                    opportunity_id=opportunity.opportunity_id,
                    account_id=opportunity.account_id,
                    snapshot_date=snapshot_date,
                    stage=stage,
                    amount=opportunity.amount,
                )
            )

    return snapshots
