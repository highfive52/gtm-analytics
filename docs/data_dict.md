# GTM Analytics Platform — Data Dictionary

This document defines the fields, meanings, and data-contract conventions used by the GTM analytics platform. Update it when contracts or business definitions change.

## Conventions

- **Identifiers:** IDs identify records in their source or application context.
- **Timestamps:** Timestamp inputs must include timezone information. Accepted timestamps are converted to UTC and stored as timezone-naive Python `datetime` values. Canonical UTC datetime fields use the `_utc` suffix. The timezone-naive representation means UTC by contract; it does not imply local time.
- **Date-only fields:** Calendar-date fields, such as `Opportunity.close_date` and `OpportunitySnapshot.snapshot_date`, are represented as Python `date` values and are not timezone-converted. They do not use the `_utc` suffix.
- **Validation:** Pydantic enforces field-level rules in the application contracts. Cross-record and dataset-level integrity checks are handled separately.
- **String fields:** Required string fields must be nonempty. Surrounding whitespace is stripped before validation.
- **Additional fields:** The Account, Opportunity, and Activity contracts reject unexpected top-level fields.

## Account

| Field | Purpose | Rules / Representation |
|---|---|---|
| `account_id` | Stable source-system identifier | Required, nonempty string |
| `account_name` | Company name | Required, nonempty string; surrounding whitespace is stripped |
| `industry` | Industry classification | Required, nonempty string; surrounding whitespace is stripped |
| `created_at_utc` | Account creation timestamp | Required; timezone-aware input, normalized to naive UTC |
| `updated_at_utc` | Most recent source update timestamp | Required; timezone-aware input, normalized to naive UTC |

## Opportunity

| Field | Purpose | Rules / Representation |
|---|---|---|
| `opportunity_id` | Identifies the opportunity | Required, nonempty string |
| `account_id` | Links the opportunity to an account | Required, nonempty string; account existence is not verified by the Pydantic model |
| `opportunity_name` | Human-readable name | Required, nonempty string; surrounding whitespace is stripped |
| `stage` | Current sales stage | Required; must match an allowed value listed below |
| `amount` | Monetary amount associated with the opportunity | Required `Decimal`; must be greater than or equal to zero |
| `created_at_utc` | Record creation timestamp | Required; timezone-aware input, normalized to naive UTC |
| `updated_at_utc` | Most recent record update timestamp | Required; timezone-aware input, normalized to naive UTC |
| `close_date` | Expected opportunity close date | Optional; may be omitted or `None`; otherwise, a calendar date represented as `YYYY-MM-DD`, with no timezone conversion |

### Opportunity stages

The `stage` field accepts only these values:

- `qualification`
- `discovery`
- `evaluation`
- `proposal`
- `negotiation`
- `closed_won`
- `closed_lost`

### Opportunity validation notes

- `Literal` restricts `stage` to the defined vocabulary.
- `Field(ge=0)` rejects negative opportunity amounts.
- Pydantic validates that `account_id` is a nonempty string, but does not establish referential integrity. A separate pipeline or data-quality test must verify that the referenced account exists.
- `close_date` is a calendar date, not a timestamp. It represents the expected close date and is not subject to UTC normalization.

## OpportunitySnapshot

Each `OpportunitySnapshot` record represents an opportunity's state on a particular snapshot date.

| Field | Purpose | Rules / Representation |
|---|---|---|
| `opportunity_id` | Identifies the opportunity being snapshotted | Required, nonempty string |
| `account_id` | Links the snapshot to an account | Required, nonempty string |
| `snapshot_date` | Date the opportunity state was recorded | Required calendar date; no timezone conversion |
| `stage` | Opportunity stage on the snapshot date | Required; must match the allowed opportunity-stage vocabulary |
| `amount` | Opportunity amount on the snapshot date | Required `Decimal`; must be greater than or equal to zero |

### OpportunitySnapshot validation notes

- `snapshot_date` is a calendar date, not a timestamp, so it does not use the `_utc` suffix.
- The Pydantic model enforces field-level constraints but does not establish that the referenced opportunity or account exists.
- Dataset-level validation checks snapshot relationships, duplicate opportunity/date combinations, snapshot counts, and weekly spacing.

## Activity

Each Activity record represents one event associated with an account.

| Field | Purpose | Rules / Representation |
|---|---|---|
| `activity_id` | Identifies the activity event | Required, nonempty string |
| `account_id` | Links the activity to an account | Required, nonempty string; account existence is not verified by the Pydantic model |
| `event_name` | Identifies the specific activity event | Required; must match an allowed value listed below |
| `activity_timestamp_utc` | Time the activity occurred | Required; timezone-aware input, normalized to naive UTC |
| `source` | Identifies the originating system | Required, nonempty string |
| `properties` | Holds attributes specific to an activity | Optional; defaults to an empty dictionary |

### Activity event definitions

The `event_name` field accepts only these values:

| Event name | Required properties | Property rules |
|---|---|---|
| `feature_used` | `feature_name`, `action` | `feature_name` must be nonempty. `action` must be one of `viewed`, `created`, `edited`, `published`, `exported`. |
| `campaign_published` | `campaign_id`, `channel` | `campaign_id` must be nonempty. `channel` must be one of `email`, `sms`, `push`. |
| `report_viewed` | `report_type` | Must be one of `campaign_performance`, `revenue_attribution`, `engagement`. |
| `meeting` | None defined yet | Flexible properties; no event-specific validation currently applies. |
| `email` | None defined yet | Flexible properties; no event-specific validation currently applies. |

### Activity validation notes

- `Literal` restricts `event_name` to the defined event vocabulary.
- The `feature_used`, `campaign_published`, and `report_viewed` events use event-specific Pydantic models to validate their properties.
- Those event-specific models reject unexpected properties and enforce the documented required fields and allowed values.
- The `meeting` and `email` events currently accept flexible property dictionaries without event-specific structure or value validation.
- `properties` defaults to an empty dictionary when omitted. Product events require the properties specified in their respective schemas.
- `activity_id` provides an identifier that can support deduplication, but uniqueness is not enforced by the Pydantic model.
- `account_id` is validated as a nonempty string. Referential integrity must be checked separately.
- The event taxonomy and allowed values are project-defined conventions. Changes should be reflected in the Pydantic models, tests, and this dictionary.

## Maintenance

When adding or changing a contract:

1. Document each field's business meaning.
2. Record required/optional status, accepted values, and normalization rules.
3. Update the associated Pydantic model and tests.
4. Update this dictionary whenever the contract's behavior or field semantics change.
5. Keep synthetic-data generation and downstream data-quality checks consistent with the documented contracts.
