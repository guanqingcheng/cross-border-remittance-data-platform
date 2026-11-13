-- History rows never change, but a rerun after a failed extract can write one twice.
select
    TransferStatusHistoryId as transfer_status_history_id,
    TransferId as transfer_id,
    FromStatus as from_status,
    ToStatus as to_status,
    ChangedAt as changed_at,
    Reason as reason
from {{ raw_files('TransferStatusHistory') }}
qualify row_number() over (partition by TransferStatusHistoryId order by _extracted_at desc) = 1
