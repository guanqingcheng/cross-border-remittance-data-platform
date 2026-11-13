select
    CustomerId as customer_id,
    CountryCode as country_code,
    KycStatus as kyc_status,
    CreatedAt as created_at,
    UpdatedAt as updated_at
from {{ raw_files('Customer') }}
qualify row_number() over (partition by CustomerId order by UpdatedAt desc, _extracted_at desc) = 1
