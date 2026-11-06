# Dataset Shape

## Purpose

Define the initial synthetic dataset for the GTM Analytics Platform.

The dataset will support analysis of the following business question:

> Which accounts show increasing product usage while their sales opportunities remain stalled, and which accounts should the GTM team prioritize for follow-up?

The first dataset will be intentionally small, deterministic, and easy to validate. It should exercise the complete data pipeline without requiring large volumes of data or unnecessary infrastructure.

## 1. Initial Dataset Size

| Dataset | Initial size | Purpose |
|---|---:|---|
| Accounts | 24 records | Represent the customer accounts being analyzed |
| Opportunities | 24 records | Represent the current sales opportunity state |
| Activities | 2,640 records | Represent product usage and GTM engagement |
| Opportunity snapshots | 288 records | Preserve weekly opportunity history |
| Observation period | 12 weeks | Support trend analysis and opportunity aging |

Each of the six business scenarios will have four accounts. Initially, each account will have one associated opportunity to simplify relationship management and analytical validation.

These are initial project assumptions, not production-scale requirements.

## 2. Source Datasets

### 2.1 Accounts

**Grain:** One record per account.

The account dataset represents the customer or prospective customer being analyzed.

It will use the existing `Account` Pydantic contract.

Each account must have a unique identifier. Account attributes should include the fields defined by the contract, such as account name and relevant timestamps.

Requirements:

- Account identifiers must be unique.
- Required fields must satisfy the `Account` contract.
- Timestamp inputs must include timezone information and follow the contract's UTC normalization rules. Canonical UTC datetime fields use the `_utc` suffix and are represented internally as timezone-naive UTC values.
- Every opportunity and activity record must reference an existing account.

### 2.2 Opportunities

**Grain:** One record per opportunity, representing its current state.

The opportunity dataset will use the existing `Opportunity` Pydantic contract.

Each opportunity must reference an existing account and include its current stage, amount, and relevant dates.

Requirements:

- Opportunity identifiers must be unique.
- Every `account_id` must reference an existing account.
- Stage values must conform to the contract.
- Opportunity amounts must be nonnegative.
- Closed opportunities must be distinguishable from open opportunities through their stage.
- Current opportunity state must be consistent with the corresponding snapshot history.
- `created_at_utc` and `updated_at_utc` must follow the contract's UTC normalization rules.
- `close_date` is a calendar date and is not subject to timezone conversion.

The initial dataset will contain one opportunity per account. Multiple opportunities per account can be introduced in a later iteration to test more complex account-level prioritization.

### 2.3 Activities

**Grain:** One record per activity event.

The activity dataset will use the existing `Activity` Pydantic contract.

It will include product usage and GTM engagement events, such as:

- `feature_used`
- `campaign_published`
- `report_viewed`
- `meeting`
- `email`

Event-specific properties must conform to the appropriate contract rules.

Requirements:

- Activity identifiers must be unique.
- Every `account_id` must reference an existing account.
- Event names and event-specific properties must pass Pydantic validation.
- `activity_timestamp_utc` must follow the contract's UTC normalization rules.
- Activity timestamps must fall within the intended observation period.
- Activity volume and event types must reflect the assigned business scenario.
- Scenario labels must not be included as fields used by analytical models to determine the expected result.

The last requirement is important: the analytics models must infer account behavior from the underlying records rather than simply reading a scenario label generated alongside the data.

### 2.4 Opportunity Snapshots

**Grain:** One opportunity's state on one weekly snapshot date.

The snapshot dataset preserves historical opportunity state so the analytics models can determine whether an opportunity has remained in the same stage over time.

Proposed fields:

| Field | Purpose |
|---|---|
| `opportunity_id` | Identifies the opportunity |
| `account_id` | Identifies the associated account |
| `snapshot_date` | Date of the snapshot |
| `stage` | Opportunity stage on that date |
| `amount` | Opportunity amount on that date |

For 24 opportunities across 12 weekly snapshots, the initial dataset will contain 288 records.

Requirements:

- Each snapshot must reference an existing opportunity and account.
- There must be no duplicate `(opportunity_id, snapshot_date)` combinations.
- Snapshot stages must follow a coherent history.
- The latest snapshot must agree with the current opportunity record.
- Closed opportunities must have a coherent terminal state in their history.
- `snapshot_date` is a calendar date, not a timestamp, and does not use the `_utc` suffix.

The snapshot dataset is an additional source schema. It does not replace or modify the existing `Opportunity` contract.

For the initial implementation, snapshot records will be generated directly rather than introducing a separate stage-change event stream.

## 3. Business Scenarios

Each scenario will contain four accounts. The generator will assign scenario membership internally, but that label will not be supplied to the analytical models.

| Scenario | Product usage pattern | Opportunity pattern | Expected analytical behavior |
|---|---|---|---|
| A. Rising usage, stalled opportunity | Increasing activity | Open opportunity remains in the same stage | Flag as a potential follow-up priority |
| B. Rising usage, progressing opportunity | Increasing activity | Opportunity advances through stages | Recognize engagement without incorrectly classifying the deal as stalled |
| C. Declining usage, stalled opportunity | Decreasing activity | Open opportunity remains in the same stage | Identify a different risk pattern |
| D. Consistently low usage | Persistently low activity | Opportunity may remain open | Distinguish low engagement from increasing engagement |
| E. Temporary usage spike | Brief increase followed by a return toward baseline | Opportunity does not necessarily progress | Avoid treating a temporary spike as sustained growth |
| F. Opportunity resolved | Any coherent activity pattern | Opportunity closes as won or lost | Exclude resolved opportunities from open-deal stall calculations |

The generator should create distinguishable patterns without making every account artificially identical. Small variations in activity volume and event timing will help test whether the analytical logic generalizes beyond one exact record pattern.

## 4. Initial Analytical Definitions

These definitions are starting assumptions for the project. They should be documented and tested rather than treated as universal GTM benchmarks.

### Increasing product usage

Compare the most recent four complete weeks against the preceding four complete weeks.

The initial implementation should calculate weekly activity counts and evaluate whether usage has increased over the comparison period. It should also distinguish sustained growth from a single-week spike.

The 12-week observation period provides enough history to calculate the two comparison windows and inspect earlier behavior.

### Stalled opportunity

An opportunity is considered stalled when it is open and has remained in the same stage for at least 30 days.

Weekly snapshots provide the historical state needed to approximate stage age. Because snapshots are weekly, the exact transition date may not be known; the initial implementation should document how it handles this uncertainty.

### Primary follow-up signal

The primary signal is an account with:

1. Increasing product usage.
2. An associated open opportunity.
3. An opportunity that meets the stalled-stage definition.

This combination suggests that product engagement may be growing without corresponding sales progression. It is a prioritization signal for further investigation, not proof that an account will convert.

## 5. Source Format and Directory Layout

Synthetic source records will be written as JSON Lines (`.jsonl`) files. Each line represents one JSON record.

JSONL supports incremental record processing and preserves nested activity properties without requiring a separate file format for each event type.

Proposed layout:

```text
synthetic/
├── accounts/
│   └── batch_id=baseline/
│       └── accounts.jsonl
├── opportunities/
│   └── batch_id=baseline/
│       └── opportunities.jsonl
├── activities/
│   └── batch_id=baseline/
│       └── activities.jsonl
├── opportunity_snapshots/
│   └── batch_id=baseline/
│       └── snapshots.jsonl
└── manifests/
    └── baseline.json
```

The current publishing workflow writes the generated JSONL datasets to MinIO for raw storage. If local file generation is introduced as a separate step, it should use the same contracts and validation rules.

The manifest should include:

- Batch identifier.
- Generation timestamp, expressed in the documented UTC representation.
- Record count for each dataset.
- File checksum for each generated dataset.
- Generator or dataset version.

The manifest makes it easier to verify that a batch is complete and that regenerated data has not changed unexpectedly.

## 6. Determinism and Validation

The generator must be deterministic: identical configuration and seed values should produce equivalent records and stable file contents.

Validation will occur at two levels.

### Record-level validation

Use the existing Pydantic contracts to validate accounts, opportunities, and activities before writing the final dataset.

Snapshot records should receive equivalent schema validation using the existing `OpportunitySnapshot` model.

Timestamp validation must distinguish between external input and the canonical stored representation. External inputs require timezone information and are normalized to naive UTC. Storage validation must respect that representation rather than blindly reapplying the external-input requirement to serialized naive UTC values.

### Cross-record validation

Validate relationships and consistency across datasets:

- All identifiers are unique within their intended entity.
- All foreign-key references resolve.
- Snapshot grain is unique.
- Snapshot histories are coherent.
- The latest opportunity snapshot matches the current opportunity record.
- Activities fall within the observation period.
- Every business scenario exhibits the intended underlying behavior.
- Dataset counts match the manifest.
- Checksums and file sizes match the published objects.

These checks should fail validation when the output is invalid rather than silently accepting inconsistent records.

## 7. Implementation Sequence

1. Generate accounts using the existing `Account` contract.
2. Generate current opportunities using the existing `Opportunity` contract.
3. Generate weekly opportunity snapshots.
4. Generate activity events using the existing `Activity` contract.
5. Run record-level and cross-record validation.
6. Write JSONL datasets and a batch manifest.
7. Add automated tests for determinism, relationships, scenario behavior, and invalid output.

The generated scenario assignments may be retained separately as test metadata so automated tests can verify expected analytical results without exposing those labels to the dbt models.

## 8. Future Extensions

Once the initial pipeline and analytical models work end to end, consider:

- Multiple opportunities per account.
- Additional activity types and more realistic event distributions.
- Late-arriving activities and duplicate events.
- Repeated ingestion of the same batch to test idempotency.
- Schema evolution and backward compatibility.
- Larger datasets for testing partitioning and query performance.
- Additional account-level prioritization features, such as opportunity amount and recent meeting activity.

These extensions should be introduced when they test a concrete architectural or analytical requirement, rather than included in the initial generator by default.
