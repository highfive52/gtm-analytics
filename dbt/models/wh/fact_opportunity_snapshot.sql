select
    opportunity_snapshot.dbt_scd_id as opportunity_snapshot_key,
    opportunity_snapshot.opportunity_id,
    opportunity_snapshot.account_id,
    account.account_key,
    opportunity.opportunity_key,
    snapshot_date.date_key,
    opportunity_snapshot.snapshot_date,
    opportunity_snapshot.stage,
    opportunity_snapshot.amount,
    opportunity_snapshot.stage not in ('closed_won', 'closed_lost')
        as is_open_opportunity,
    opportunity_snapshot.batch_id as source_batch_id,
    opportunity_snapshot.ingested_at_utc as source_ingested_at_utc
from {{ ref("opportunity_snapshots_snapshot") }} as opportunity_snapshot
join {{ ref("dim_date") }} as snapshot_date
    on snapshot_date.date_day = opportunity_snapshot.snapshot_date
left join {{ ref("dim_account") }} as account
    on account.account_id = opportunity_snapshot.account_id
    and opportunity_snapshot.snapshot_date::timestamp >= account.effective_from
    and (
        account.effective_to is null
        or opportunity_snapshot.snapshot_date::timestamp < account.effective_to
    )
left join {{ ref("dim_opportunity") }} as opportunity
    on opportunity.opportunity_id = opportunity_snapshot.opportunity_id
where opportunity_snapshot.dbt_valid_to is null
