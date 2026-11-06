with source_dates as (
    select activity_timestamp_utc::date as date_day
    from {{ source("raw", "activities") }}

    union all

    select snapshot_date as date_day
    from {{ source("raw", "opportunity_snapshots") }}

    union all

    select created_at_utc::date as date_day
    from {{ source("raw", "accounts") }}

    union all

    select created_at_utc::date as date_day
    from {{ source("raw", "opportunities") }}

    union all

    select close_date as date_day
    from {{ source("raw", "opportunities") }}
    where close_date is not null
),

date_bounds as (
    select
        date_trunc('week', min(date_day))::date as min_date,
        max(date_day) as max_date
    from source_dates
),

calendar as (
    select calendar_series.calendar_timestamp::date as date_day
    from date_bounds
    cross join lateral generate_series(
        date_bounds.min_date::timestamp,
        date_bounds.max_date::timestamp,
        interval '1 day'
    ) as calendar_series(calendar_timestamp)
)

select
    to_char(date_day, 'YYYYMMDD')::integer as date_key,
    date_day,
    extract(year from date_day)::integer as year_number,
    extract(quarter from date_day)::integer as quarter_number,
    extract(month from date_day)::integer as month_number,
    extract(isodow from date_day)::integer as day_of_week_number,
    date_trunc('month', date_day)::date as month_start_date,
    date_trunc('week', date_day)::date as week_start_date,
    extract(isodow from date_day) in (6, 7) as is_weekend
from calendar
