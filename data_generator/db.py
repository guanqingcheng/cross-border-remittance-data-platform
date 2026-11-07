"""Shared SQL Server connection helper."""

import os

import pyodbc
from dotenv import load_dotenv


def get_connection():
    """Open a connection using settings from the environment or .env file."""
    load_dotenv()

    connection_string = (
        f"Driver={{{os.environ['ODBC_DRIVER']}}};"
        f"Server={os.environ['SQL_SERVER']};"
        f"Database={os.environ['SQL_DATABASE']};"
        "TrustServerCertificate=yes;"
    )

    username = os.environ.get("SQL_USERNAME")
    if username:
        connection_string += f"UID={username};PWD={os.environ['SQL_PASSWORD']};"
    else:
        connection_string += "Trusted_Connection=yes;"

    return pyodbc.connect(connection_string)
