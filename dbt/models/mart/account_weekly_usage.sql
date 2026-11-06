-- Weekly account activity at one row per account and week.
with account_ids as (
    select distinct account_id
    from {{ ref("dim_account") }}
),

activity_weeks as (
    select distinct activity_date.week_start_date
    from {{ ref("fact_activity") }} as activity
    join {{ ref("dim_date") }} as activity_date
        on activity_date.date_key = activity.date_key
),

account_week_spine as (
    select
        account_ids.account_id,
        account_version.account_key,
        activity_weeks.week_start_date
    from account_ids
    cross join activity_weeks
    left join {{ ref("dim_account") }} as account_version
        on account_version.account_id = account_ids.account_id
        and activity_weeks.week_start_date::timestamp
            >= account_version.effective_from
        and (
            account_version.effective_to is null
            or activity_weeks.week_start_date::timestamp
                < account_version.effective_to
        )
),

weekly_activity as (
    select
        activity.account_id,
        activity_date.week_start_date,
        count(*)::integer as activity_count,
        count(*) filter (
            where activity.event_name = 'feature_used'
        )::integer as feature_used_count,
        count(*) filter (
            where activity.event_name = 'campaign_published'
        )::integer as campaign_published_count,
        count(*) filter (
            where activity.event_name = 'report_viewed'
        )::integer as report_viewed_count,
        count(*) filter (
            where activity.event_name = 'meeting'
        )::integer as meeting_count,
        count(*) filter (
            where activity.event_name = 'email'
        )::integer as email_count
    from {{ ref("fact_activity") }} as activity
    join {{ ref("dim_date") }} as activity_date
        on activity_date.date_key = activity.date_key
    group by activity.account_id, activity_date.week_start_date
)

select
    account_week_spine.account_id,
    account_week_spine.account_key,
    week_date.date_key as week_start_date_key,
    account_week_spine.week_start_date,
    coalesce(weekly_activity.activity_count, 0) as activity_count,
    coalesce(weekly_activity.feature_used_count, 0) as feature_used_count,
    coalesce(weekly_activity.campaign_published_count, 0)
        as campaign_published_count,
    coalesce(weekly_activity.report_viewed_count, 0) as report_viewed_count,
    coalesce(weekly_activity.meeting_count, 0) as meeting_count,
    coalesce(weekly_activity.email_count, 0) as email_count
from account_week_spine
join {{ ref("dim_date") }} as week_date
    on week_date.date_day = account_week_spine.week_start_date
left join weekly_activity
    on weekly_activity.account_id = account_week_spine.account_id
    and weekly_activity.week_start_date = account_week_spine.week_start_date
