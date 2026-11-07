"""Check that Python can connect to the configured SQL Server database."""

from db import get_connection

connection = get_connection()
cursor = connection.cursor()
cursor.execute("SELECT DB_NAME(), COUNT(*) FROM dbo.Currency")
database_name, currency_count = cursor.fetchone()
connection.close()

print(f"Connected to {database_name}. Currency rows: {currency_count}")
