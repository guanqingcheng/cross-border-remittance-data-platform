"""Shared connections for data quality tests.

The reconciliation tests expect the extract and dbt build to have run after the
last change to the source database.
"""

import os
from pathlib import Path

import duckdb
import pytest

from data_generator.db import get_connection


@pytest.fixture(scope="session")
def source_cursor():
    connection = get_connection()
    yield connection.cursor()
    connection.close()


@pytest.fixture(scope="session")
def warehouse():
    path = Path(os.environ.get("DATA_DIR", "data")) / "warehouse.duckdb"
    if not path.exists():
        pytest.fail(f"{path} not found. Run the extract and dbt build first.")
    connection = duckdb.connect(str(path), read_only=True)
    yield connection
    connection.close()
