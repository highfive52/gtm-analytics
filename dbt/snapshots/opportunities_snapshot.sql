{% snapshot opportunities_snapshot %}

{{
    config(
        target_schema="src",
        unique_key="opportunity_id",
        strategy="timestamp",
        updated_at="updated_at_utc",
        hard_deletes="invalidate",
    )
}}

select
    opportunity_id,
    account_id,
    opportunity_name,
    stage,
    amount,
    created_at_utc,
    updated_at_utc,
    close_date,
    batch_id,
    ingested_at_utc
from {{ source("raw", "opportunities") }}

{% endsnapshot %}
