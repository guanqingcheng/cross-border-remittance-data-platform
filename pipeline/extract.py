"""Extract SQL Server tables to Parquet files.

Tables that change use a watermark, so each run only reads new and changed rows.
Small reference tables are replaced with a full snapshot on each run.

Run from the repository root:
    python -m pipeline.extract
"""

import datetime as dt
import json
import os
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from data_generator.db import get_connection

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
RAW_DIR = DATA_DIR / "raw"
STATE_FILE = DATA_DIR / "state" / "watermarks.json"

# Table: (primary key, watermark column)
INCREMENTAL_TABLES = {
    "Customer": ("CustomerId", "UpdatedAt"),
    "Recipient": ("RecipientId", "UpdatedAt"),
    "Transfer": ("TransferId", "UpdatedAt"),
    "TransferStatusHistory": ("TransferStatusHistoryId", "ChangedAt"),
}
SNAPSHOT_TABLES = ["Currency", "Corridor", "FeeSchedule", "ExchangeRate"]

# Rows newer than this wait for the next run, so a slow transaction that commits
# after a later one cannot be skipped by the watermark
SAFETY_LAG_MINUTES = 5


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    """Replace the state file in one step, so a crash cannot leave it half written."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = STATE_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(temp_file, STATE_FILE)


def arrow_type(column):
    """Map a pyodbc column description to a Parquet column type."""
    _, python_type, _, _, precision, scale, _ = column
    if python_type is Decimal:
        return pa.decimal128(precision, scale)
    if python_type is dt.datetime:
        return pa.timestamp("ms")
    if python_type is dt.date:
        return pa.date32()
    if python_type is bool:
        return pa.bool_()
    if python_type is int:
        return pa.int64()
    return pa.string()


def build_table(cursor, rows, extracted_at):
    """Turn query results into a table with fixed types for every file."""
    columns = {
        column[0]: pa.array([row[index] for row in rows], type=arrow_type(column))
        for index, column in enumerate(cursor.description)
    }
    columns["_extracted_at"] = pa.array([extracted_at] * len(rows), type=pa.timestamp("ms"))
    return pa.table(columns)


def write_file(table, path):
    """Write to a temporary file first, so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    pq.write_table(table, temp_path)
    os.replace(temp_path, path)


def extract_incremental(cursor, table_name, primary_key, watermark_column, state, extracted_at):
    table_state = state.get(table_name, {})
    watermark = table_state.get("watermark", "0001-01-01T00:00:00")
    seen_keys = set(table_state.get("keys_at_watermark", []))

    # >= keeps rows that share the watermark timestamp, and seen_keys removes
    # the ones already extracted
    cursor.execute(
        f"""
        SELECT * FROM dbo.{table_name}
        WHERE {watermark_column} >= ?
            AND {watermark_column} < DATEADD(MINUTE, -?, SYSUTCDATETIME())
        ORDER BY {watermark_column}, {primary_key}
        """,
        dt.datetime.fromisoformat(watermark),
        SAFETY_LAG_MINUTES,
    )
    key_index = [column[0] for column in cursor.description].index(primary_key)
    watermark_index = [column[0] for column in cursor.description].index(watermark_column)
    rows = [
        row
        for row in cursor.fetchall()
        if not (row[watermark_index].isoformat() == watermark and row[key_index] in seen_keys)
    ]

    if not rows:
        print(f"{table_name}: no new rows")
        return

    file_name = f"{table_name}_{extracted_at:%Y%m%dT%H%M%S}.parquet"
    write_file(build_table(cursor, rows, extracted_at), RAW_DIR / table_name / file_name)

    new_watermark = rows[-1][watermark_index]
    keys_at_watermark = [row[key_index] for row in rows if row[watermark_index] == new_watermark]
    if new_watermark.isoformat() == watermark:
        keys_at_watermark += list(seen_keys)

    # Saved only after the file exists. A crash here reads the rows again, which
    # is safe because downstream models keep one version of each row
    state[table_name] = {"watermark": new_watermark.isoformat(), "keys_at_watermark": keys_at_watermark}
    save_state(state)
    print(f"{table_name}: {len(rows)} rows, watermark {new_watermark.isoformat()}")


def extract_snapshot(cursor, table_name, extracted_at):
    cursor.execute(f"SELECT * FROM dbo.{table_name}")
    rows = cursor.fetchall()
    write_file(build_table(cursor, rows, extracted_at), RAW_DIR / table_name / f"{table_name}.parquet")
    print(f"{table_name}: {len(rows)} rows, full snapshot")


def main():
    extracted_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
    state = load_state()

    connection = get_connection()
    cursor = connection.cursor()
    try:
        for table_name in SNAPSHOT_TABLES:
            extract_snapshot(cursor, table_name, extracted_at)
        for table_name, (primary_key, watermark_column) in INCREMENTAL_TABLES.items():
            extract_incremental(cursor, table_name, primary_key, watermark_column, state, extracted_at)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
