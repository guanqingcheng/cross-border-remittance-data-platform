-- Names and emails stay in the source system; analytics only needs these attributes
select
    customer_id,
    country_code,
    kyc_status,
    created_at
from {{ ref('stg_customers') }}
