with expected_accounts as (
    select unnest(array['acct-001', 'acct-002', 'acct-003', 'acct-004'])
        as account_id
),

actual_accounts as (
    select account_id
    from {{ ref("account_follow_up_priority") }}
    where is_primary_follow_up
)

select expected_accounts.account_id
from expected_accounts
left join actual_accounts using (account_id)
where actual_accounts.account_id is null

union all

select actual_accounts.account_id
from actual_accounts
left join expected_accounts using (account_id)
where expected_accounts.account_id is null
