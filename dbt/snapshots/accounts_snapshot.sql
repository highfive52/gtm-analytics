{% snapshot accounts_snapshot %}

{{
    config(
        target_schema="src",
        unique_key="account_id",
        strategy="timestamp",
        updated_at="updated_at_utc",
        hard_deletes="invalidate",
    )
}}

select
    account_id,
    account_name,
    industry,
    created_at_utc,
    updated_at_utc,
    batch_id,
    ingested_at_utc
from {{ source("raw", "accounts") }}

{% endsnapshot %}
