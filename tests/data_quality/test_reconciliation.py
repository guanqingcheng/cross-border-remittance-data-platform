"""Compare the DuckDB warehouse with SQL Server.

A pipeline bug can produce tidy, unique rows that are still wrong, such as an
old version of a transfer. Only a comparison with the source catches that.
"""


def test_every_transfer_has_the_source_status(source_cursor, warehouse):
    source_cursor.execute("SELECT TransferId, Status FROM dbo.Transfer")
    source = dict(source_cursor.fetchall())
    mart = dict(warehouse.execute("select transfer_id, status from fct_transfers").fetchall())

    missing = sorted(set(source) - set(mart))
    extra = sorted(set(mart) - set(source))
    wrong_status = sorted(k for k in set(source) & set(mart) if source[k] != mart[k])

    assert missing == [], f"{len(missing)} transfers missing from the warehouse, for example {missing[:10]}"
    assert extra == [], f"{len(extra)} transfers in the warehouse but not the source, for example {extra[:10]}"
    assert wrong_status == [], f"{len(wrong_status)} transfers have a different status, for example {wrong_status[:10]}"


def test_daily_corridor_totals_match_stored_procedure(source_cursor, warehouse):
    source_cursor.execute("SELECT MIN(CreatedAt), MAX(CreatedAt) FROM dbo.Transfer")
    first, last = source_cursor.fetchone()
    source_cursor.execute(
        "EXEC dbo.usp_GetDailyCorridorSummary @FromDate = ?, @ToDate = ?", first.date(), last.date()
    )
    source = {
        (row.SummaryDate, row.CorridorId): (
            row.TransferCount,
            row.CompletedCount,
            row.FailedCount,
            row.TotalSendAmount,
            row.TotalFeeAmount,
            row.TotalReceiveAmount,
        )
        for row in source_cursor.fetchall()
    }

    rows = warehouse.execute(
        """
        select created_date, corridor_id, transfer_count, completed_count, failed_count,
               completed_send_amount, completed_fee_amount, completed_receive_amount
        from mart_corridor_daily
        """
    ).fetchall()
    mart = {(row[0], row[1]): tuple(row[2:]) for row in rows}

    different = sorted(key for key in set(source) | set(mart) if source.get(key) != mart.get(key))
    assert different == [], f"{len(different)} date and corridor rows differ, for example {different[:5]}"


def test_status_history_row_count_matches(source_cursor, warehouse):
    source_cursor.execute("SELECT COUNT(*) FROM dbo.TransferStatusHistory")
    source_count = source_cursor.fetchone()[0]
    mart_count = warehouse.execute("select count(*) from stg_transfer_status_history").fetchone()[0]
    assert mart_count == source_count
