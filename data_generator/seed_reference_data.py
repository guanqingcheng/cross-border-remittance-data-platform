"""Insert synthetic currencies, corridors, fee schedules, and exchange rates."""

import random
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

from db import get_connection

SEED = 42
RATE_START_DATE = date(2026, 1, 1)
RATE_END_DATE = date(2026, 10, 31)
RATE_PRECISION = Decimal("0.00000001")

CURRENCIES = [
    ("USD", "US Dollar", 2),
    ("EUR", "Euro", 2),
    ("GBP", "British Pound", 2),
    ("MXN", "Mexican Peso", 2),
    ("PHP", "Philippine Peso", 2),
    ("INR", "Indian Rupee", 2),
    ("JPY", "Japanese Yen", 0),
]

# Source country, destination country, source currency, destination currency
CORRIDORS = [
    ("US", "MX", "USD", "MXN"),
    ("US", "PH", "USD", "PHP"),
    ("US", "IN", "USD", "INR"),
    ("US", "JP", "USD", "JPY"),
    ("GB", "IN", "GBP", "INR"),
    ("DE", "PH", "EUR", "PHP"),
]
MAX_SEND_AMOUNT = Decimal("5000.00")

# Invented starting points for the simulation, not market data
STARTING_RATES = {
    ("USD", "MXN"): Decimal("18.50"),
    ("USD", "PHP"): Decimal("56.00"),
    ("USD", "INR"): Decimal("83.00"),
    ("USD", "JPY"): Decimal("150.00"),
    ("GBP", "INR"): Decimal("105.00"),
    ("EUR", "PHP"): Decimal("60.00"),
}

# Payout method: flat fee, percent fee for smaller amounts
PAYOUT_FEES = {
    "BankDeposit": (Decimal("2.00"), Decimal("0.0100")),
    "CashPickup": (Decimal("4.00"), Decimal("0.0150")),
    "MobileWallet": (Decimal("1.50"), Decimal("0.0120")),
}

# Minimum, maximum, percent fee discount for larger amounts
AMOUNT_BANDS = [
    (Decimal("0.01"), Decimal("999.99"), Decimal("0.0000")),
    (Decimal("1000.00"), MAX_SEND_AMOUNT, Decimal("0.0020")),
]

# Effective from, effective to, flat fee reduction after a simulated price change
FEE_PERIODS = [
    (date(2026, 1, 1), date(2026, 5, 31), Decimal("0.00")),
    (date(2026, 6, 1), None, Decimal("0.50")),
]


def build_corridor_rows():
    return [(*corridor, MAX_SEND_AMOUNT) for corridor in CORRIDORS]


def build_fee_rows(corridor_ids):
    rows = []
    for corridor_id in corridor_ids:
        for payout_method, (flat_fee, percent_fee) in PAYOUT_FEES.items():
            for minimum, maximum, discount in AMOUNT_BANDS:
                for effective_from, effective_to, reduction in FEE_PERIODS:
                    rows.append((
                        corridor_id,
                        payout_method,
                        minimum,
                        maximum,
                        flat_fee - reduction,
                        percent_fee - discount,
                        effective_from,
                        effective_to,
                    ))
    return rows


def build_exchange_rate_rows():
    """Move each rate by a small random amount per day, using a fixed seed."""
    rng = random.Random(SEED)
    rows = []
    for (from_currency, to_currency), starting_rate in STARTING_RATES.items():
        mid_rate = starting_rate
        current_date = RATE_START_DATE
        while current_date <= RATE_END_DATE:
            daily_change = Decimal(str(round(rng.uniform(-0.005, 0.005), 6)))
            margin = Decimal(str(round(rng.uniform(0.005, 0.015), 6)))
            mid_rate = (mid_rate * (1 + daily_change)).quantize(RATE_PRECISION)
            customer_rate = (mid_rate * (1 - margin)).quantize(RATE_PRECISION, ROUND_DOWN)
            rows.append((from_currency, to_currency, current_date, mid_rate, customer_rate))
            current_date += timedelta(days=1)
    return rows


def main():
    connection = get_connection()
    connection.autocommit = False
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM dbo.Currency")
        if cursor.fetchone()[0] > 0:
            print("Reference data already exists. Nothing was changed.")
            return

        cursor.fast_executemany = True

        cursor.executemany(
            "INSERT INTO dbo.Currency (CurrencyCode, CurrencyName, DecimalPlaces) VALUES (?, ?, ?)",
            CURRENCIES,
        )

        corridor_rows = build_corridor_rows()
        cursor.executemany(
            """
            INSERT INTO dbo.Corridor
                (SourceCountryCode, DestinationCountryCode, SourceCurrencyCode, DestinationCurrencyCode, MaxSendAmount)
            VALUES (?, ?, ?, ?, ?)
            """,
            corridor_rows,
        )

        cursor.execute("SELECT CorridorId FROM dbo.Corridor ORDER BY CorridorId")
        corridor_ids = [row[0] for row in cursor.fetchall()]

        fee_rows = build_fee_rows(corridor_ids)
        cursor.executemany(
            """
            INSERT INTO dbo.FeeSchedule
                (CorridorId, PayoutMethod, MinSendAmount, MaxSendAmount, FlatFee, PercentFee, EffectiveFrom, EffectiveTo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fee_rows,
        )

        rate_rows = build_exchange_rate_rows()
        cursor.executemany(
            """
            INSERT INTO dbo.ExchangeRate (FromCurrencyCode, ToCurrencyCode, RateDate, MidRate, CustomerRate)
            VALUES (?, ?, ?, ?, ?)
            """,
            rate_rows,
        )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(
        f"Inserted {len(CURRENCIES)} currencies, {len(corridor_rows)} corridors, "
        f"{len(fee_rows)} fee schedules, and {len(rate_rows)} exchange rates."
    )


if __name__ == "__main__":
    main()
