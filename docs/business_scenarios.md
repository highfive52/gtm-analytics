# GTM Analytics: Business Scenarios

## Business Question

Which accounts show increasing product usage while their sales opportunities remain stalled, and which accounts should the GTM team prioritize for follow-up?

The synthetic dataset should include both positive signals and counterexamples. Otherwise, downstream dbt models could appear to work simply because every account was designed to fit the same pattern.

The scenarios in this document define the behaviors the synthetic data generator must represent and the analytical models must distinguish.

## 1. Business Scenarios

### A. Rising Usage, Stalled Opportunity

**Classification:** Primary signal

Product activity increases over several weeks, but the associated opportunity remains in the same sales stage without meaningful progress.

This is the primary account behavior the GTM team should investigate. Increasing engagement may indicate growing customer interest or expansion potential, while stalled sales progression may indicate a need for follow-up.

### B. Rising Usage, Progressing Opportunity

Product engagement increases while the opportunity advances through the sales pipeline.

This is a positive control. It demonstrates that rising product usage does not necessarily indicate a stalled deal and provides a comparison against Scenario A.

### C. Declining Usage, Stalled Opportunity

Product activity falls while the opportunity makes no meaningful progress.

This may indicate declining engagement or deal risk. It is an important signal, but it differs from the primary scenario because usage is decreasing rather than increasing.

### D. Consistently Low Usage

Product activity remains low over the observation period, regardless of opportunity stage.

This scenario distinguishes accounts with consistently limited adoption from accounts experiencing recent growth or decline in engagement.

### E. Temporary Usage Spike

Product activity increases sharply for a short period, then returns to its previous level.

This scenario tests whether the analytical models distinguish sustained usage growth from isolated activity spikes. A single busy week should not automatically qualify an account as experiencing a sustained increase in engagement.

### F. Opportunity Resolved

The opportunity closes as won or lost.

These accounts provide comparison cases and help prevent the analytical models from classifying every opportunity without recent stage movement as stalled. Closed opportunities should be distinguished from open opportunities that have stopped progressing.

## 2. Data Requirements

The existing Account, Opportunity, and Activity contracts provide the foundation for the synthetic source data. Additional history and relationships are needed to represent the scenarios reliably.

| Data requirement | Purpose |
|---|---|
| Multiple weeks of activity | Distinguishes sustained usage trends from isolated events |
| Event timestamps | Supports weekly activity aggregation and trend analysis |
| Event properties | Distinguishes product actions, such as creating or publishing a campaign |
| Opportunity stage history | Identifies stage progression and time spent in a stage |
| Account-to-opportunity relationships | Connects product behavior to the sales pipeline |
| Closed-won and closed-lost outcomes | Provides comparison cases for resolved opportunities |

### Opportunity History

The current Opportunity contract includes `created_at`, `updated_at`, and the current `stage`, but it does not preserve historical stage transitions.

Two approaches are possible:

1. **Weekly opportunity snapshots:** preserve the opportunity's stage and relevant attributes at regular intervals.
2. **Opportunity stage-change events:** record each transition, including the previous stage, new stage, and transition timestamp.

For the initial implementation, weekly snapshots are a practical choice if the goal is to preserve the existing three contracts. Stage-change events provide more explicit transition history but introduce an additional source or contract.

Whichever approach is selected, the analytical models must be able to determine how long an open opportunity has remained in its current stage.

## 3. Initial Dataset Size

The initial dataset should be small enough to inspect manually but large enough to demonstrate meaningful variation.

| Entity or attribute | Initial target |
|---|---:|
| Accounts | 24 |
| Opportunities | 24–30 |
| Activity events | 1,000–2,000 |
| Activity history | 8–12 weeks |

These are starting targets rather than strict requirements. The final volume can be adjusted after validating the generated records and confirming that the scenarios are distinguishable.

The generator should assign scenarios deterministically while allowing controlled variation in account names, opportunity amounts, event counts, and event timing.

For example, assigning four accounts to each of the six scenarios provides a predictable baseline for testing. Determinism makes it easier to reproduce results and identify regressions when the generator or analytical logic changes.

## 4. Initial Analytical Definitions

The following definitions establish a starting point for the primary signal. They are project-specific assumptions, not universal GTM benchmarks.

### Increasing Product Usage

Compare the most recent four complete weeks of activity with the preceding four complete weeks.

An account qualifies as showing increasing usage when its activity volume demonstrates an upward trend over the observation period.

The implementation should define the exact calculation—for example, comparing average weekly event counts—and avoid treating a single temporary spike as sustained growth.

### Stalled Opportunity

An opportunity qualifies as stalled when it remains open and has stayed in the same sales stage for at least 30 days.

The calculation requires enough opportunity history to establish when the current stage began. The current `updated_at` field alone should not automatically be treated as a stage-change timestamp unless its semantics explicitly support that interpretation.

### Primary Signal

An account qualifies for the primary signal when both conditions hold:

- Product usage is increasing over the defined observation period.
- An associated open opportunity has remained in the same stage for at least 30 days.

The resulting model should expose the account, opportunity, observed usage trend, days in the current stage, and the reason the account was flagged. This makes the output actionable and explainable to the GTM team.

## 5. Design Principles

The synthetic dataset should follow these principles:

- **Deterministic:** repeated runs with the same configuration produce reproducible records.
- **Contract-valid:** generated Account, Opportunity, and Activity records pass their Pydantic validations.
- **Relationally consistent:** foreign-key-like relationships between accounts and opportunities are valid.
- **Temporally coherent:** event timestamps, opportunity creation dates, stage history, and close dates make sense together.
- **Analytically meaningful:** every scenario can be distinguished using the available data.
- **Representative:** include positive signals, negative signals, counterexamples, and resolved opportunities.
- **Testable:** tests verify both record validity and the presence of the intended scenarios.

## 6. Implementation Sequence

1. Finalize the scenario definitions and analytical thresholds.
2. Decide how opportunity stage history will be represented.
3. Define the source-data format and generation rules.
4. Generate deterministic synthetic records using the existing contracts.
5. Validate record-level rules and cross-record relationships.
6. Confirm that the generated dataset exhibits all six scenarios.
7. Prepare the source data for MinIO storage and Postgres ingestion.
8. Build dbt models that identify and explain the primary signal.

The objective is not simply to generate realistic-looking data. It is to create a reproducible dataset that can demonstrate the complete path from source records to trustworthy, actionable GTM analytics.