"""Check that Python can connect to the local SQL Server database."""

import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()

server = os.environ["SQL_SERVER"]
database = os.environ["SQL_DATABASE"]
driver = os.environ["ODBC_DRIVER"]

connection_string = (
    f"Driver={{{driver}}};"
    f"Server={server};"
    f"Database={database};"
    "Trusted_Connection=yes;"
)

connection = pyodbc.connect(connection_string)
cursor = connection.cursor()
cursor.execute("SELECT COUNT(*) FROM dbo.Currency")
currency_count = cursor.fetchone()[0]
connection.close()

print(f"Connected to {database} on {server}. Currency rows: {currency_count}")
