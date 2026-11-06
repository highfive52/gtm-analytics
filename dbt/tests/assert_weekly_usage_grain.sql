select
    account_id,
    week_start_date
from {{ ref("account_weekly_usage") }}
group by account_id, week_start_date
having count(*) > 1
