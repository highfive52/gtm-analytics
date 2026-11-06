select
    activity.activity_id,
    account.account_key,
    activity.account_id,
    activity_date.date_key,
    activity.activity_timestamp_utc,
    activity.event_name,
    activity.source as activity_source,
    activity.properties,
    1::integer as activity_count,
    activity.batch_id as source_batch_id,
    activity.ingested_at_utc as source_ingested_at_utc
from {{ ref("activities_snapshot") }} as activity
join {{ ref("dim_date") }} as activity_date
    on activity_date.date_day = activity.activity_timestamp_utc::date
left join {{ ref("dim_account") }} as account
    on account.account_id = activity.account_id
    and activity.activity_timestamp_utc >= account.effective_from
    and (
        account.effective_to is null
        or activity.activity_timestamp_utc < account.effective_to
    )
where activity.dbt_valid_to is null
