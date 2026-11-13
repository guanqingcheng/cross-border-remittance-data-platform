select
    RecipientId as recipient_id,
    CustomerId as customer_id,
    CountryCode as country_code,
    IsActive as is_active,
    CreatedAt as created_at,
    UpdatedAt as updated_at
from {{ raw_files('Recipient') }}
qualify row_number() over (partition by RecipientId order by UpdatedAt desc, _extracted_at desc) = 1
