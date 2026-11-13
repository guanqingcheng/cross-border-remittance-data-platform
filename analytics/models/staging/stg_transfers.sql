-- A transfer can appear in several extract files after status changes.
-- Keep only its latest version.
select
    TransferId as transfer_id,
    ReferenceNumber as reference_number,
    CustomerId as customer_id,
    RecipientId as recipient_id,
    CorridorId as corridor_id,
    FeeScheduleId as fee_schedule_id,
    ExchangeRateId as exchange_rate_id,
    PayoutMethod as payout_method,
    SendAmount as send_amount,
    FeeAmount as fee_amount,
    AppliedRate as applied_rate,
    ReceiveAmount as receive_amount,
    Status as status,
    CreatedAt as created_at,
    UpdatedAt as updated_at,
    CompletedAt as completed_at
from {{ raw_files('Transfer') }}
qualify row_number() over (partition by TransferId order by UpdatedAt desc, _extracted_at desc) = 1
