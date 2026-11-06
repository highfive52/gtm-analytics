# Synthetic GTM Data

The synthetic package has two distinct responsibilities:

- [`gtm_analytics/synthetic/generator.py`](gtm_analytics/synthetic/generator.py)
  creates the actual deterministic dataset as Pydantic model instances.
- [`gtm_analytics/synthetic/publish_baseline.py`](gtm_analytics/synthetic/publish_baseline.py)
  facilitates loading that generated data into MinIO by serializing and
  publishing it, then validating the uploaded batch.

The generator does not perform file or network I/O.

## What the generator creates

The generator defines six account scenarios, with four accounts in each:

| Scenario | Product activity pattern | Opportunity pattern |
|---|---|---|
| `rising_usage_stalled` | Activity rises each week | Remains in discovery |
| `rising_usage_progressing` | Activity rises each week | Progresses from qualification through discovery to evaluation |
| `declining_usage_stalled` | Activity falls each week | Remains in discovery |
| `consistently_low_usage` | Activity remains low | Remains in discovery |
| `temporary_usage_spike` | One high-activity week, then returns to its previous level | Remains in discovery |
| `opportunity_resolved` | Moderate activity before resolution, then lower activity | Closes won or lost |

It generates:

- 24 accounts, with stable IDs and deterministic example attributes.
- One opportunity for each account, including an amount, current stage, and a
  close date for closed opportunities.
- 12 weekly opportunity snapshots per opportunity (288 total), preserving
  stage history.
- Timestamped product and GTM activity events over the observation period.
  Event types are `feature_used`, `campaign_published`, and `report_viewed`;
  each includes event-specific properties.

The base date is fixed in the generator, and IDs, dates, stage histories,
activity volumes, event types, and properties are derived deterministically.
Calling a generator repeatedly with the same input produces the same records.
For the activity and snapshot generators, account/opportunity order determines
the scenario assignment, so use the accounts and opportunities returned by the
preceding generator calls without reordering them.

For the scenario definitions and their analytics context, see
[`../docs/business_scenarios.md`](../docs/business_scenarios.md).

## Generate records in Python

Run commands from the repository root after installing the project with
`uv sync --dev`:

```python
from gtm_analytics.synthetic.generator import (
    generate_accounts,
    generate_activities,
    generate_opportunities,
    generate_opportunity_snapshots,
)

accounts = generate_accounts()
opportunities = generate_opportunities(accounts)
snapshots = generate_opportunity_snapshots(opportunities)
activities = generate_activities(accounts)

print(len(accounts), len(opportunities), len(snapshots), len(activities))
```

The functions return `list[Account]`, `list[Opportunity]`,
`list[OpportunitySnapshot]`, and `list[Activity]`, respectively. Pass generated
records directly to downstream Python code, or validate/serialize them using
the storage package.

## Field validation and timestamps

The Pydantic contracts validate generated records. For example, the
[`Activity` contract](gtm_analytics/contracts/activity.py) requires a timestamp
with timezone information, converts it to UTC, and then removes the timezone:

```python
@field_validator("activity_timestamp_utc")
@classmethod
def normalize_timestamp_to_naive_utc(cls, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include timezone information")
    return value.astimezone(UTC).replace(tzinfo=None)
```

An input of `2026-10-19T12:00:00+02:00` therefore becomes
`2026-10-19 10:00:00` with `tzinfo=None`: the instant is first converted to
UTC, then represented as a naive datetime. Naive inputs are rejected rather
than treated as local time. The same normalization is used for account and
opportunity timestamps; opportunity snapshots contain dates, not timestamps.

## Publish a batch to MinIO

[`gtm_analytics/synthetic/publish_baseline.py`](gtm_analytics/synthetic/publish_baseline.py)
calls the generators to create the records, writes them as JSON Lines datasets
along with a manifest to the `gtm-raw` bucket, then validates the uploaded
batch. Start the local services with `make start`, then publish from the
repository root:

```sh
make publish-baseline
```

The Make target defaults to batch ID `baseline_v2`. Use a new ID for each
publication because existing batch prefixes are not overwritten:

```sh
make publish-baseline BATCH_ID=baseline_v3
```

The batch is stored under
`synthetic/batch_id=<batch-id>/` in MinIO. The command prints the validation
result and manifest. The Make target supplies local MinIO connection defaults;
when calling the Python module directly, configure `MINIO_ROOT_USER` and
`MINIO_ROOT_PASSWORD` (and, if needed, `MINIO_ENDPOINT` and `MINIO_SECURE`) in
the environment or project-root `.env` file:

```sh
uv run python -m gtm_analytics.synthetic.publish_baseline --batch-id baseline_v3
```

The publishing function is also callable from Python:

```python
from gtm_analytics.synthetic.publish_baseline import publish_baseline

manifest = publish_baseline(batch_id="baseline_v3")
```

It returns the manifest after publishing and validation. A batch ID must be
path-safe and must not already have objects in its MinIO batch prefix.