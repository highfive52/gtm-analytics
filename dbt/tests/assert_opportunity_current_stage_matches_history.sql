with latest_snapshot as (
    select
        opportunity_id,
        stage,
        row_number() over (
            partition by opportunity_id
            order by snapshot_date desc
        ) as row_number
    from {{ ref("fact_opportunity_snapshot") }}
)

select
    opportunity.opportunity_id,
    opportunity.current_stage,
    latest_snapshot.stage as latest_snapshot_stage
from {{ ref("dim_opportunity") }} as opportunity
join latest_snapshot
    on latest_snapshot.opportunity_id = opportunity.opportunity_id
    and latest_snapshot.row_number = 1
where opportunity.current_stage is distinct from latest_snapshot.stage
