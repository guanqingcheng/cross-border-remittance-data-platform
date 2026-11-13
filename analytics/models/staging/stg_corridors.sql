select
    CorridorId as corridor_id,
    SourceCountryCode as source_country_code,
    DestinationCountryCode as destination_country_code,
    SourceCurrencyCode as source_currency_code,
    DestinationCurrencyCode as destination_currency_code,
    MaxSendAmount as max_send_amount,
    IsActive as is_active
from {{ raw_files('Corridor') }}
