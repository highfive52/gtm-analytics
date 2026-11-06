select *
from {{ ref("account_follow_up_priority") }}
where is_primary_follow_up is distinct from (
    is_usage_increasing and is_stalled_opportunity
)
