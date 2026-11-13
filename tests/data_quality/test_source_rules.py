"""Business rules checked directly in SQL Server.

The stored procedures enforce these rules, but rows written another way would
bypass them. Each query returns the IDs of rows that break a rule.
"""

import pytest

RULE_QUERIES = {
    "fee matches fee schedule": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.FeeSchedule AS f ON f.FeeScheduleId = t.FeeScheduleId
        WHERE t.FeeAmount <> ROUND(f.FlatFee + t.SendAmount * f.PercentFee, 2)
    """,
    "receive amount matches applied rate": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.Corridor AS c ON c.CorridorId = t.CorridorId
        INNER JOIN dbo.Currency AS d ON d.CurrencyCode = c.DestinationCurrencyCode
        WHERE t.ReceiveAmount <> ROUND(t.SendAmount * t.AppliedRate, d.DecimalPlaces)
    """,
    "rate is the customer rate for the transfer date and pair": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.Corridor AS c ON c.CorridorId = t.CorridorId
        INNER JOIN dbo.ExchangeRate AS e ON e.ExchangeRateId = t.ExchangeRateId
        WHERE e.RateDate <> CAST(t.CreatedAt AS DATE)
            OR e.CustomerRate <> t.AppliedRate
            OR e.FromCurrencyCode <> c.SourceCurrencyCode
            OR e.ToCurrencyCode <> c.DestinationCurrencyCode
    """,
    "amount is within the corridor limit": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.Corridor AS c ON c.CorridorId = t.CorridorId
        WHERE t.SendAmount <= 0 OR t.SendAmount > c.MaxSendAmount
    """,
    "customer is verified and in the source country": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.Customer AS c ON c.CustomerId = t.CustomerId
        INNER JOIN dbo.Corridor AS k ON k.CorridorId = t.CorridorId
        WHERE c.KycStatus <> 'Verified' OR c.CountryCode <> k.SourceCountryCode
    """,
    "recipient is in the destination country": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        INNER JOIN dbo.Recipient AS r ON r.RecipientId = t.RecipientId
        INNER JOIN dbo.Corridor AS k ON k.CorridorId = t.CorridorId
        WHERE r.CountryCode <> k.DestinationCountryCode
    """,
    "first history row is NULL to Pending": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        WHERE NOT EXISTS
        (
            SELECT 1 FROM dbo.TransferStatusHistory AS h
            WHERE h.TransferId = t.TransferId AND h.FromStatus IS NULL AND h.ToStatus = 'Pending'
        )
    """,
    "status matches latest history row": """
        SELECT t.TransferId
        FROM dbo.Transfer AS t
        CROSS APPLY
        (
            SELECT TOP (1) h.ToStatus, h.ChangedAt
            FROM dbo.TransferStatusHistory AS h
            WHERE h.TransferId = t.TransferId
            ORDER BY h.TransferStatusHistoryId DESC
        ) AS latest
        WHERE latest.ToStatus <> t.Status OR latest.ChangedAt <> t.UpdatedAt
    """,
    "every status change is allowed": """
        SELECT TransferId
        FROM dbo.TransferStatusHistory
        WHERE NOT (
            (FromStatus IS NULL AND ToStatus = 'Pending')
            OR (FromStatus = 'Pending' AND ToStatus IN ('Processing', 'Cancelled', 'Failed'))
            OR (FromStatus = 'Processing' AND ToStatus IN ('Completed', 'Failed'))
        )
    """,
    "each history row starts from the previous status": """
        SELECT TransferId
        FROM
        (
            SELECT
                TransferId,
                FromStatus,
                LAG(ToStatus) OVER (PARTITION BY TransferId ORDER BY TransferStatusHistoryId) AS PreviousStatus
            FROM dbo.TransferStatusHistory
        ) AS h
        WHERE PreviousStatus IS NOT NULL AND (FromStatus IS NULL OR FromStatus <> PreviousStatus)
    """,
    "CompletedAt is set only for completed transfers": """
        SELECT TransferId
        FROM dbo.Transfer
        WHERE (Status = 'Completed' AND CompletedAt IS NULL)
            OR (Status <> 'Completed' AND CompletedAt IS NOT NULL)
    """,
}


@pytest.mark.parametrize("query", RULE_QUERIES.values(), ids=RULE_QUERIES.keys())
def test_no_rule_violations(source_cursor, query):
    source_cursor.execute(query)
    violating_ids = sorted({row[0] for row in source_cursor.fetchall()})
    assert violating_ids == [], f"{len(violating_ids)} transfers break this rule, for example {violating_ids[:10]}"
