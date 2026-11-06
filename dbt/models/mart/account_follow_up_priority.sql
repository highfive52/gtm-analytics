with activity_observation as (
    select max(activity_timestamp_utc::date) as last_activity_date
    from {{ ref("fact_activity") }}
),

complete_week as (
    select
        case
            when last_activity_date
                = date_trunc('week', last_activity_date)::date + 6
                then date_trunc('week', last_activity_date)::date
            else date_trunc('week', last_activity_date)::date - 7
        end as latest_complete_week_start
    from activity_observation
),

activity_trends as (
    select
        weekly_usage.account_id,
        avg(weekly_usage.activity_count::numeric) filter (
            where weekly_usage.week_start_date between
                complete_week.latest_complete_week_start - 21
                and complete_week.latest_complete_week_start
        ) as recent_four_week_average,
        avg(weekly_usage.activity_count::numeric) filter (
            where weekly_usage.week_start_date between
                complete_week.latest_complete_week_start - 49
                and complete_week.latest_complete_week_start - 28
        ) as prior_four_week_average,
        count(*) filter (
            where weekly_usage.week_start_date between
                complete_week.latest_complete_week_start - 21
                and complete_week.latest_complete_week_start
        ) as recent_week_count,
        count(*) filter (
            where weekly_usage.week_start_date between
                complete_week.latest_complete_week_start - 49
                and complete_week.latest_complete_week_start - 28
        ) as prior_week_count
    from {{ ref("account_weekly_usage") }} as weekly_usage
    cross join complete_week
    group by weekly_usage.account_id
),

stage_sequence as (
    select
        opportunity_id,
        account_id,
        snapshot_date,
        stage,
        lag(stage) over (
            partition by opportunity_id
            order by snapshot_date
        ) as previous_stage
    from {{ ref("fact_opportunity_snapshot") }}
),

stage_with_start_date as (
    select
        opportunity_id,
        account_id,
        snapshot_date,
        stage,
        max(
            case
                when previous_stage is distinct from stage then snapshot_date
            end
        ) over (
            partition by opportunity_id
            order by snapshot_date
            rows between unbounded preceding and current row
        ) as current_stage_start_date
    from stage_sequence
),

latest_opportunity_stage as (
    select
        opportunity_id,
        account_id,
        snapshot_date as latest_snapshot_date,
        stage as current_stage,
        current_stage_start_date,
        snapshot_date - current_stage_start_date as days_in_current_stage
    from (
        select
            stage_with_start_date.*,
            row_number() over (
                partition by opportunity_id
                order by snapshot_date desc
            ) as row_number
        from stage_with_start_date
    ) as ranked_stages
    where row_number = 1
),

account_opportunity_signals as (
    select
        account.account_key,
        account.account_id,
        account.account_name,
        account.industry,
        opportunity.opportunity_key,
        opportunity.opportunity_id,
        opportunity.opportunity_name,
        coalesce(
            latest_stage.current_stage,
            opportunity.current_stage
        ) as current_stage,
        latest_stage.latest_snapshot_date,
        latest_stage.current_stage_start_date,
        latest_stage.days_in_current_stage,
        activity_trends.recent_four_week_average,
        activity_trends.prior_four_week_average,
        activity_trends.recent_week_count,
        activity_trends.prior_week_count,
        coalesce(
            activity_trends.recent_week_count = 4
                and activity_trends.prior_week_count = 4,
            false
        ) as has_complete_usage_windows
    from {{ ref("dim_account") }} as account
    left join {{ ref("dim_opportunity") }} as opportunity
        on opportunity.account_id = account.account_id
    left join latest_opportunity_stage as latest_stage
        on latest_stage.opportunity_id = opportunity.opportunity_id
    left join activity_trends
        on activity_trends.account_id = account.account_id
    where account.is_current
)

select
    account_key,
    account_id,
    account_name,
    industry,
    opportunity_key,
    opportunity_id,
    opportunity_name,
    current_stage,
    latest_snapshot_date,
    current_stage_start_date,
    days_in_current_stage,
    recent_four_week_average,
    prior_four_week_average,
    recent_four_week_average - prior_four_week_average
        as weekly_activity_average_change,
    round(
        100.0 * (
            recent_four_week_average - prior_four_week_average
        ) / nullif(prior_four_week_average, 0),
        2
    ) as weekly_activity_average_change_percent,
    has_complete_usage_windows,
    has_complete_usage_windows
        and recent_four_week_average > prior_four_week_average
        as is_usage_increasing,
    current_stage is not null
        and current_stage not in ('closed_won', 'closed_lost')
        as is_open_opportunity,
    current_stage is not null
        and current_stage not in ('closed_won', 'closed_lost')
        and days_in_current_stage >= 30
        as is_stalled_opportunity,
    has_complete_usage_windows
        and recent_four_week_average > prior_four_week_average
        and current_stage is not null
        and current_stage not in ('closed_won', 'closed_lost')
        and days_in_current_stage >= 30
        as is_primary_follow_up,
    case
        when current_stage is null then 'no_opportunity_history'
        when current_stage in ('closed_won', 'closed_lost')
            then 'opportunity_closed'
        when not has_complete_usage_windows
            then 'insufficient_usage_history'
        when recent_four_week_average > prior_four_week_average
            and days_in_current_stage >= 30
            then 'increasing_usage_and_stalled_opportunity'
        when recent_four_week_average > prior_four_week_average
            then 'increasing_usage_without_stalled_opportunity'
        when days_in_current_stage >= 30
            then 'stalled_without_increasing_usage'
        else 'no_primary_signal'
    end as follow_up_reason
from account_opportunity_signals
