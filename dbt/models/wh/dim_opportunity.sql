select
    opportunity_id as opportunity_key,
    opportunity_id,
    account_id,
    opportunity_name,
    stage as current_stage,
    amount as current_amount,
    created_at_utc,
    updated_at_utc,
    close_date,
    stage in ('closed_won', 'closed_lost') as is_closed,
    batch_id as source_batch_id,
    ingested_at_utc as source_ingested_at_utc
from {{ ref("opportunities_snapshot") }}
where dbt_valid_to is null
