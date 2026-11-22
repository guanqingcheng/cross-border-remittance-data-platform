"""Answer English questions about the remittance data with Claude and two read-only tools.

The model gets two tools:
- get_schema: the tables and columns the qa_reader login is allowed to read
- run_query: run one SELECT statement as qa_reader and return the rows

Safety does not depend on the model behaving. The database login can only read the allowed tables,
and personal columns are denied (see setup_readonly_login.py). The code adds its own limits on top:
one SELECT statement per call, at most 200 rows, a 10 second query timeout, and at most 8 model turns.

Run from the repository root:
    python -m qa_agent.agent "How many transfers were completed in March 2026?"
"""

import argparse
import os
import re
import sys

import anthropic
import pyodbc
from dotenv import load_dotenv

MODEL = "claude-haiku-5-5"
PRICE_PER_MTOK = {"input": 0.10, "output": 0.50}
MAX_TURNS = 8
MAX_ROWS = 200
QUERY_TIMEOUT_SECONDS = 10
MAX_TOKENS = 8000

SYSTEM_PROMPT = """You answer questions about the data of a cross-border money transfer business.
The data is synthetic and lives in a SQL Server database.

How to work:
- Call get_schema first, then answer with run_query. Never guess a number: every number in your answer must come from a query result.
- Write T-SQL for SQL Server. Name the columns you need; do not use SELECT *.
- If a query fails, read the error, fix the query, and try again.
- Customer and recipient names and email are stored in the database, but your login is not allowed to read them, so get_schema does not list them. Do not say they do not exist. If a question needs them, say you are not permitted to read them and answer with IDs instead.
- If the question is ambiguous, state the assumption you made.

Business facts:
- A transfer belongs to a corridor, for example US to Mexico. SendAmount and FeeAmount are in the corridor's source currency; ReceiveAmount is in the destination currency.
- Amounts in different currencies must not be added together. Group by currency instead.
- Transfer.Status is the current status: Pending, Processing, Completed, Cancelled, or Failed. Completed, Cancelled, and Failed are final.
- TransferStatusHistory has one row per status change; Reason explains failures.
- FeeSchedule.PercentFee 0.0150 means 1.5%.
- Dates are stored in UTC.

Answer in plain English, in a few sentences, and include the key numbers.
Give money amounts, rates, and averages with two decimal places, exactly as the query returned them rounded to two places. Do not round them to whole numbers or write "about"."""

TOOLS = [
    {
        "name": "get_schema",
        "description": "List the tables and columns you can query, with their data types.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "run_query",
        "description": (
            f"Run one read-only T-SQL SELECT statement (a WITH ... SELECT is fine) and return up to {MAX_ROWS} rows. "
            "Aggregate in SQL instead of fetching many rows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "One SELECT statement"}},
            "required": ["sql"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

# Statements and keywords that never belong in a read-only question. The login cannot do these anyway;
# this check gives the model a clear error instead of a permission error.
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|ALTER|CREATE|EXEC|EXECUTE|GRANT|REVOKE|DENY|INTO|BACKUP|RESTORE|SHUTDOWN)\b",
    re.IGNORECASE,
)


class QueryRejected(Exception):
    """The SQL failed the code's own checks before reaching the database."""


class AgentError(Exception):
    """The agent could not produce an answer."""


def connect_readonly():
    """Connect as the read-only qa_reader login."""
    connection_string = (
        f"Driver={{{os.environ['ODBC_DRIVER']}}};"
        f"Server={os.environ['SQL_SERVER']};"
        f"Database={os.environ['SQL_DATABASE']};"
        f"UID={os.environ['QA_READER_USERNAME']};"
        f"PWD={os.environ['QA_READER_PASSWORD']};"
        "TrustServerCertificate=yes;"
    )
    connection = pyodbc.connect(connection_string, autocommit=True)
    connection.timeout = QUERY_TIMEOUT_SECONDS  # query timeout in seconds
    return connection


def get_schema(connection):
    """Return the readable tables and columns as text, one table per line."""
    # INFORMATION_SCHEMA still lists columns that are denied, so filter on the actual permission.
    rows = connection.cursor().execute("""
        SELECT c.TABLE_SCHEMA, c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS AS c
        WHERE HAS_PERMS_BY_NAME(QUOTENAME(c.TABLE_SCHEMA) + '.' + QUOTENAME(c.TABLE_NAME),
                                'OBJECT', 'SELECT', c.COLUMN_NAME, 'COLUMN') = 1
        ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;
    """).fetchall()

    tables = {}
    for schema, table, column, data_type in rows:
        tables.setdefault(f"{schema}.{table}", []).append(f"{column} {data_type}")
    return "\n".join(f"{table}: {', '.join(columns)}" for table, columns in tables.items())


def check_select(sql):
    """Return the statement without comments if it is a single SELECT, otherwise raise QueryRejected."""
    without_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_comments = re.sub(r"--[^\n]*", " ", without_comments)
    statement = without_comments.strip().rstrip(";").strip()

    if not statement:
        raise QueryRejected("The query is empty.")
    if ";" in statement:
        raise QueryRejected("Send one statement at a time, without semicolons in the middle.")
    if not re.match(r"(SELECT|WITH)\b", statement, re.IGNORECASE):
        raise QueryRejected("Only SELECT statements (or WITH ... SELECT) are allowed.")
    match = FORBIDDEN.search(statement)
    if match:
        raise QueryRejected(f"The keyword {match.group(0).upper()} is not allowed in a read-only query.")
    return statement


def run_query(connection, sql):
    """Run one checked SELECT and return the result as text for the model."""
    statement = check_select(sql)
    cursor = connection.cursor()
    cursor.execute(statement)
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchmany(MAX_ROWS + 1)

    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    lines = [" | ".join(columns)]
    lines += [" | ".join("NULL" if value is None else str(value) for value in row) for row in rows]
    note = f"\n(first {MAX_ROWS} rows only; aggregate in SQL to see everything)" if truncated else ""
    return f"{len(rows)} row(s)\n" + "\n".join(lines) + note


def execute_tool(connection, name, tool_input, log):
    """Run one tool call. Returns (text, is_error). Errors go back to the model so it can fix the query."""
    if name == "get_schema":
        return get_schema(connection), False
    if name == "run_query":
        sql = tool_input.get("sql", "")
        try:
            result = run_query(connection, sql)
            log.append({"sql": sql, "ok": True})
            return result, False
        except (QueryRejected, pyodbc.Error) as error:
            log.append({"sql": sql, "ok": False, "error": str(error)})
            return f"Query failed: {error}", True
    return f"Unknown tool: {name}", True


def ask(question, client=None, connection=None, verbose=False):
    """Answer one question. Returns a dict with the answer, the queries run, and token usage."""
    client = client or anthropic.Anthropic(timeout=120, max_retries=2)
    connection = connection or connect_readonly()
    messages = [{"role": "user", "content": question}]
    queries = []
    usage = {"input_tokens": 0, "output_tokens": 0}

    for turn in range(1, MAX_TURNS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            answer = "\n".join(block.text for block in response.content if block.type == "text").strip()
            return {
                "question": question,
                "answer": answer,
                "queries": queries,
                "turns": turn,
                "model": response.model,
                **usage,
                "est_cost_usd": estimate_cost(usage),
            }

        if response.stop_reason != "tool_use":
            raise AgentError(f"The model stopped with stop_reason={response.stop_reason!r}.")

        # Keep the assistant turn as it is, including its tool_use blocks, then answer every tool call.
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            text, is_error = execute_tool(connection, block.name, block.input, queries)
            if verbose:
                shown = block.input.get("sql", "").strip() if block.name == "run_query" else ""
                status = "error" if is_error else "ok"
                print(f"[turn {turn}] {block.name} ({status}) {shown}", file=sys.stderr)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    raise AgentError(f"No answer after {MAX_TURNS} turns.")


def estimate_cost(usage):
    return round(
        (usage["input_tokens"] * PRICE_PER_MTOK["input"] + usage["output_tokens"] * PRICE_PER_MTOK["output"])
        / 1_000_000,
        5,
    )


def main():
    parser = argparse.ArgumentParser(description="Ask a question about the remittance data.")
    parser.add_argument("question")
    args = parser.parse_args()
    load_dotenv()

    try:
        result = ask(args.question, verbose=True)
    except Exception as error:
        print(f"Could not answer: {error}", file=sys.stderr)
        return 2

    print(result["answer"])
    print(
        f"\nmodel={result['model']} turns={result['turns']} queries={len(result['queries'])} "
        f"input_tokens={result['input_tokens']} output_tokens={result['output_tokens']} "
        f"est_cost_usd={result['est_cost_usd']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
