{% snapshot opportunity_snapshots_snapshot %}

{{
    config(
        target_schema="src",
        unique_key="opportunity_id || '|' || snapshot_date::text",
        strategy="check",
        check_cols="all",
        hard_deletes="invalidate",
    )
}}

select
    opportunity_id,
    account_id,
    snapshot_date,
    stage,
    amount,
    batch_id,
    ingested_at_utc
from {{ source("raw", "opportunity_snapshots") }}

{% endsnapshot %}
