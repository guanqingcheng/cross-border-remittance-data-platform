"""Generate synthetic customers, recipients, and transfers.

Transfers go through the stored procedures, so generated data follows the same
business rules as normal transfers. Each run is one batch for a later date range,
and also finishes transfers left open by the previous batch.

Example:
    python data_generator/generate_transfers.py --start 2026-01-01 --end 2026-09-30 --count 3000
"""

import argparse
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from faker import Faker

from db import get_connection

SEED = 42
CUSTOMER_COUNT = 600
MIN_AMOUNT = 20.0
MAX_AMOUNT = 5000.0
OPEN_WINDOW = timedelta(days=2)

CUSTOMER_COUNTRY_WEIGHTS = {"US": 80, "GB": 12, "DE": 8}
KYC_STATUS_WEIGHTS = {"Verified": 90, "Pending": 7, "Rejected": 3}
PAYOUT_METHOD_WEIGHTS = {"BankDeposit": 55, "CashPickup": 25, "MobileWallet": 20}
FINAL_STATUS_WEIGHTS = {"Completed": 88, "Failed": 7, "Cancelled": 5}
FAILURE_REASONS = ["Recipient bank rejected", "Compliance review failed", "Payout partner timeout"]


def weighted_choice(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def load_corridors(cursor):
    """Return active corridors grouped by source country."""
    cursor.execute(
        "SELECT CorridorId, SourceCountryCode, DestinationCountryCode FROM dbo.Corridor "
        "WHERE IsActive = 1 ORDER BY CorridorId"
    )
    corridors = {}
    for corridor_id, source_country, destination_country in cursor.fetchall():
        corridors.setdefault(source_country, []).append((corridor_id, destination_country))
    return corridors


def create_customers_and_recipients(cursor, rng, fake, corridors, first_batch_start):
    """Create customers and recipients once, dated before the first batch."""
    for _ in range(CUSTOMER_COUNT):
        country = weighted_choice(rng, CUSTOMER_COUNTRY_WEIGHTS)
        created_at = datetime.combine(first_batch_start, time()) - timedelta(minutes=rng.randint(1440, 525600))
        cursor.execute(
            """
            SET NOCOUNT ON;
            INSERT INTO dbo.Customer (FirstName, LastName, Email, CountryCode, KycStatus, CreatedAt, UpdatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            SELECT CAST(SCOPE_IDENTITY() AS INT);
            """,
            fake.first_name(),
            fake.last_name(),
            fake.unique.safe_email(),
            country,
            weighted_choice(rng, KYC_STATUS_WEIGHTS),
            created_at,
            created_at,
        )
        customer_id = cursor.fetchone()[0]

        for _ in range(rng.randint(1, 3)):
            _, destination_country = rng.choice(corridors[country])
            cursor.execute(
                """
                INSERT INTO dbo.Recipient (CustomerId, FirstName, LastName, CountryCode, CreatedAt, UpdatedAt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                customer_id,
                fake.first_name(),
                fake.last_name(),
                destination_country,
                created_at,
                created_at,
            )


def load_senders(cursor, corridors):
    """Return every valid customer, recipient, and corridor combination."""
    cursor.execute(
        """
        SELECT c.CustomerId, c.CountryCode, r.RecipientId, r.CountryCode
        FROM dbo.Customer AS c
        INNER JOIN dbo.Recipient AS r ON r.CustomerId = c.CustomerId
        WHERE c.KycStatus = 'Verified' AND r.IsActive = 1
        ORDER BY c.CustomerId, r.RecipientId
        """
    )
    senders = []
    for customer_id, source_country, recipient_id, destination_country in cursor.fetchall():
        for corridor_id, corridor_destination in corridors[source_country]:
            if corridor_destination == destination_country:
                senders.append((customer_id, recipient_id, corridor_id))
    return senders


def update_status(cursor, transfer_id, new_status, changed_at, reason=None):
    cursor.execute(
        "EXEC dbo.usp_UpdateTransferStatus @TransferId = ?, @NewStatus = ?, @Reason = ?, @ChangedAtUtc = ?",
        transfer_id,
        new_status,
        reason,
        changed_at,
    )


def finish_open_transfers(cursor, rng, batch_start):
    """Close transfers left open by the previous batch, so existing rows change."""
    cursor.execute("SELECT TransferId, Status FROM dbo.Transfer WHERE Status IN ('Pending', 'Processing') ORDER BY TransferId")
    open_transfers = cursor.fetchall()

    for transfer_id, status in open_transfers:
        changed_at = datetime.combine(batch_start, time()) + timedelta(minutes=rng.randint(1, 720))
        if status == "Pending":
            update_status(cursor, transfer_id, "Processing", changed_at)
            changed_at += timedelta(minutes=rng.randint(1, 30))
        update_status(cursor, transfer_id, "Completed", changed_at)

    return len(open_transfers)


def create_transfer(cursor, rng, sender, created_at):
    customer_id, recipient_id, corridor_id = sender
    amount = min(max(rng.lognormvariate(5.5, 0.9), MIN_AMOUNT), MAX_AMOUNT)

    cursor.execute(
        """
        SET NOCOUNT ON;
        DECLARE @TransferId BIGINT;
        EXEC dbo.usp_CreateTransfer
            @CustomerId = ?, @RecipientId = ?, @CorridorId = ?, @PayoutMethod = ?, @SendAmount = ?,
            @AsOfUtc = ?, @TransferId = @TransferId OUTPUT;
        SELECT @TransferId;
        """,
        customer_id,
        recipient_id,
        corridor_id,
        weighted_choice(rng, PAYOUT_METHOD_WEIGHTS),
        Decimal(str(round(amount, 2))),
        created_at,
    )
    return cursor.fetchone()[0]


def advance_transfer(cursor, rng, transfer_id, created_at, batch_end):
    """Move a new transfer through its status flow, or leave it open near the batch end."""
    if created_at > batch_end - OPEN_WINDOW and rng.random() < 0.5:
        return

    final_status = weighted_choice(rng, FINAL_STATUS_WEIGHTS)
    changed_at = created_at + timedelta(minutes=rng.randint(1, 30))

    if final_status == "Cancelled":
        update_status(cursor, transfer_id, "Cancelled", changed_at, "Customer request")
        return

    update_status(cursor, transfer_id, "Processing", changed_at)
    changed_at += timedelta(minutes=rng.randint(5, 240))

    if final_status == "Failed":
        update_status(cursor, transfer_id, "Failed", changed_at, rng.choice(FAILURE_REASONS))
    else:
        update_status(cursor, transfer_id, "Completed", changed_at)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate a batch of synthetic transfers.")
    parser.add_argument("--start", type=date.fromisoformat, required=True, help="First date, YYYY-MM-DD")
    parser.add_argument("--end", type=date.fromisoformat, required=True, help="Last date, YYYY-MM-DD")
    parser.add_argument("--count", type=int, required=True, help="Number of new transfers")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.end < args.start or args.count < 1:
        raise SystemExit("--end cannot be before --start, and --count must be at least 1.")

    # The batch dates are part of the seed, so each batch differs but can be reproduced
    rng = random.Random(f"{SEED}-{args.start}-{args.end}-{args.count}")
    fake = Faker("en_US")
    fake.seed_instance(SEED)

    connection = get_connection()
    connection.autocommit = False
    cursor = connection.cursor()

    try:
        cursor.execute("SELECT MAX(CreatedAt) FROM dbo.Transfer")
        latest_transfer = cursor.fetchone()[0]
        if latest_transfer is not None and args.start <= latest_transfer.date():
            raise SystemExit(f"--start must be after the latest transfer date, {latest_transfer.date()}.")

        corridors = load_corridors(cursor)
        cursor.execute("SELECT COUNT(*) FROM dbo.Customer")
        if cursor.fetchone()[0] == 0:
            create_customers_and_recipients(cursor, rng, fake, corridors, args.start)

        senders = load_senders(cursor, corridors)
        finished = finish_open_transfers(cursor, rng, args.start)

        batch_start = datetime.combine(args.start, time())
        batch_end = datetime.combine(args.end, time(23, 59, 59))
        total_seconds = int((batch_end - batch_start).total_seconds())
        created_times = sorted(
            batch_start + timedelta(seconds=rng.randint(0, total_seconds)) for _ in range(args.count)
        )

        for created_at in created_times:
            transfer_id = create_transfer(cursor, rng, rng.choice(senders), created_at)
            advance_transfer(cursor, rng, transfer_id, created_at, batch_end)

        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"Created {args.count} transfers from {args.start} to {args.end}. Finished {finished} open transfers.")


if __name__ == "__main__":
    main()
