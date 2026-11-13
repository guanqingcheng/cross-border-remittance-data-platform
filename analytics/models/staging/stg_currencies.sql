select
    CurrencyCode as currency_code,
    CurrencyName as currency_name,
    DecimalPlaces as decimal_places
from {{ raw_files('Currency') }}
