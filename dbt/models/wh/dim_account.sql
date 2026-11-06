with account_versions as (
    select
        account_snapshot.*,
        row_number() over (
            partition by account_id
            order by dbt_valid_from, dbt_scd_id
        ) as version_number
    from {{ ref("accounts_snapshot") }} as account_snapshot
)

select
    dbt_scd_id as account_key,
    account_id,
    account_name,
    industry,
    case
        when version_number = 1 then least(created_at_utc, dbt_valid_from)
        else dbt_valid_from
    end as effective_from,
    dbt_valid_to as effective_to,
    dbt_valid_to is null as is_current,
    batch_id as source_batch_id,
    ingested_at_utc as source_ingested_at_utc
from account_versions
