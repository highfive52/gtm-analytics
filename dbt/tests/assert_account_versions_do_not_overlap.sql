select
    first_version.account_id,
    first_version.account_key as first_account_key,
    second_version.account_key as second_account_key
from {{ ref("dim_account") }} as first_version
join {{ ref("dim_account") }} as second_version
    on first_version.account_id = second_version.account_id
    and first_version.account_key < second_version.account_key
    and first_version.effective_from
        < coalesce(second_version.effective_to, 'infinity'::timestamp)
    and second_version.effective_from
        < coalesce(first_version.effective_to, 'infinity'::timestamp)
