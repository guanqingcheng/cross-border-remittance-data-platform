-- Same rules as usp_GetDailyCorridorSummary: counts cover all transfers,
-- amounts cover completed transfers only. This makes the two easy to reconcile.
select
    t.created_date,
    t.corridor_id,
    d.corridor_name,
    d.source_currency_code,
    d.destination_currency_code,
    count(*) as transfer_count,
    count(*) filter (where t.status = 'Completed') as completed_count,
    count(*) filter (where t.status = 'Failed') as failed_count,
    count(*) filter (where t.status = 'Cancelled') as cancelled_count,
    coalesce(sum(t.send_amount) filter (where t.status = 'Completed'), 0) as completed_send_amount,
    coalesce(sum(t.fee_amount) filter (where t.status = 'Completed'), 0) as completed_fee_amount,
    coalesce(sum(t.receive_amount) filter (where t.status = 'Completed'), 0) as completed_receive_amount,
    round(avg(t.minutes_to_complete), 1) as avg_minutes_to_complete,
    round(count(*) filter (where t.status = 'Failed') / count(*), 4) as failure_rate
from {{ ref('fct_transfers') }} as t
inner join {{ ref('dim_corridor') }} as d on d.corridor_id = t.corridor_id
group by all
