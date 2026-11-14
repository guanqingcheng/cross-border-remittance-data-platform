"""Export the dbt mart tables to Parquet files for Power BI.

Power BI Desktop reads Parquet with a built-in connector, so the report does
not need a DuckDB driver. File names stay the same on every run, which lets
the report refresh without changing its data source.

Run from the repository root after dbt build:
    python -m pipeline.export_marts
"""

import os
from pathlib import Path

import duckdb

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
WAREHOUSE = DATA_DIR / "warehouse.duckdb"
EXPORT_DIR = DATA_DIR / "exports"

MART_TABLES = ["dim_customer", "dim_corridor", "fct_transfers", "mart_corridor_daily"]


def main():
    if not WAREHOUSE.exists():
        raise SystemExit(f"{WAREHOUSE} not found. Run the extract and dbt build first.")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        for table in MART_TABLES:
            final_path = EXPORT_DIR / f"{table}.parquet"
            temp_path = final_path.with_name(final_path.name + ".tmp")
            # Write to a temporary file first, so Power BI never reads a half-written file
            connection.execute(f"COPY {table} TO '{temp_path.as_posix()}' (FORMAT parquet)")
            os.replace(temp_path, final_path)
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {row_count} rows -> {final_path}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
