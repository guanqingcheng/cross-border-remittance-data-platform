select
    corridor_id,
    source_country_code || '-' || destination_country_code as corridor_name,
    source_country_code,
    destination_country_code,
    source_currency_code,
    destination_currency_code,
    max_send_amount,
    is_active
from {{ ref('stg_corridors') }}
