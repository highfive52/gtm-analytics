{% snapshot activities_snapshot %}

{{
    config(
        target_schema="src",
        unique_key="activity_id",
        strategy="check",
        check_cols="all",
        hard_deletes="invalidate",
    )
}}

select
    activity_id,
    account_id,
    event_name,
    activity_timestamp_utc,
    source,
    properties,
    batch_id,
    ingested_at_utc
from {{ source("raw", "activities") }}

{% endsnapshot %}
