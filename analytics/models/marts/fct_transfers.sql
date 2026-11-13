with failure_reasons as (
    select
        transfer_id,
        reason as failure_reason
    from {{ ref('stg_transfer_status_history') }}
    where to_status = 'Failed'
)

select
    t.transfer_id,
    t.reference_number,
    t.customer_id,
    t.recipient_id,
    t.corridor_id,
    t.payout_method,
    t.status,
    t.created_at,
    cast(t.created_at as date) as created_date,
    t.completed_at,
    date_diff('minute', t.created_at, t.completed_at) as minutes_to_complete,
    c.source_currency_code,
    t.send_amount,
    t.fee_amount,
    t.send_amount + t.fee_amount as total_charged,
    t.applied_rate,
    c.destination_currency_code,
    t.receive_amount,
    f.failure_reason
from {{ ref('stg_transfers') }} as t
inner join {{ ref('stg_corridors') }} as c on c.corridor_id = t.corridor_id
left join failure_reasons as f on f.transfer_id = t.transfer_id
