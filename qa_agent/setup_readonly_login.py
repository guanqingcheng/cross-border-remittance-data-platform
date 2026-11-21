"""Create the read-only SQL login that the Q&A agent uses.

Least privilege, layer by layer:
- server: a SQL login with no server roles, its password read from QA_READER_PASSWORD
- database: a user in the qa_readonly role
- tables: SELECT is granted table by table from an allow-list, so a new table stays hidden
  until someone reviews it and adds it here (a schema-wide grant would expose it at once)
- columns: DENY on customer and recipient names and email, so the agent never sees personal data
- writes and procedures: not granted, and denied explicitly so a later GRANT to public cannot add them

The script is idempotent: run it again and it updates the password and permissions.
It connects with the admin settings in .env (SQL_USERNAME empty = Windows authentication).

Run from the repository root:
    python -m qa_agent.setup_readonly_login
"""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, "data_generator")
import db  # noqa: E402  (shared connection helper)

LOGIN = "qa_reader"
ROLE = "qa_readonly"

# Tables the agent may read. Add a table here only after checking its columns for personal data.
ALLOWED_TABLES = [
    "dbo.Currency",
    "dbo.Corridor",
    "dbo.ExchangeRate",
    "dbo.FeeSchedule",
    "dbo.Customer",
    "dbo.Recipient",
    "dbo.Transfer",
    "dbo.TransferStatusHistory",
]

# Columns that hold personal data. The agent answers questions about volumes and rates, not people.
DENIED_COLUMNS = {
    "dbo.Customer": ["FirstName", "LastName", "Email"],
    "dbo.Recipient": ["FirstName", "LastName"],
}


def main():
    load_dotenv()
    password = os.environ.get("QA_READER_PASSWORD")
    if not password:
        raise SystemExit("Set QA_READER_PASSWORD in .env first.")
    database = os.environ["SQL_DATABASE"]

    connection = db.get_connection()
    connection.autocommit = True
    cursor = connection.cursor()

    # Server level. The password goes in as a parameter-free literal only after escaping quotes,
    # because CREATE LOGIN does not accept a variable for PASSWORD.
    quoted_password = password.replace("'", "''")
    cursor.execute(f"""
        IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'{LOGIN}')
            CREATE LOGIN [{LOGIN}] WITH PASSWORD = N'{quoted_password}',
                DEFAULT_DATABASE = [{database}], CHECK_POLICY = ON, CHECK_EXPIRATION = OFF;
        ELSE
            ALTER LOGIN [{LOGIN}] WITH PASSWORD = N'{quoted_password}';
    """)

    # Database level
    cursor.execute(f"USE [{database}];")
    cursor.execute(f"""
        IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{LOGIN}')
            CREATE USER [{LOGIN}] FOR LOGIN [{LOGIN}];
        IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'{ROLE}' AND type = 'R')
            CREATE ROLE [{ROLE}];
        IF IS_ROLEMEMBER(N'{ROLE}', N'{LOGIN}') = 0
            ALTER ROLE [{ROLE}] ADD MEMBER [{LOGIN}];
    """)
    # Remove the schema-wide grant an earlier version of this script made, then grant per table.
    cursor.execute(f"REVOKE SELECT ON SCHEMA::dbo FROM [{ROLE}];")
    for table in ALLOWED_TABLES:
        cursor.execute(f"GRANT SELECT ON {table} TO [{ROLE}];")
    cursor.execute(f"DENY INSERT, UPDATE, DELETE, EXECUTE, ALTER ON SCHEMA::dbo TO [{ROLE}];")
    for table, columns in DENIED_COLUMNS.items():
        column_list = ", ".join(f"[{column}]" for column in columns)
        cursor.execute(f"DENY SELECT ({column_list}) ON {table} TO [{ROLE}];")

    connection.close()
    print(f"Login {LOGIN} is ready in {database}: SELECT on {len(ALLOWED_TABLES)} tables, personal columns denied, writes denied.")


if __name__ == "__main__":
    main()
