"""The Q&A agent's own SQL check. It needs no database and no API key.

The database login is the real boundary; this check only gives the model a clear error early.
"""

import pytest

from qa_agent.agent import QueryRejected, check_select


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM dbo.Transfer",
    "select Status, COUNT(*) from dbo.Transfer group by Status;",
    "WITH x AS (SELECT 1 AS n) SELECT n FROM x",
    "-- comment\nSELECT UpdatedAt FROM dbo.Transfer",  # UpdatedAt is not the UPDATE keyword
])
def test_allows_a_single_select(sql):
    assert check_select(sql)


@pytest.mark.parametrize("sql", [
    "",
    "DELETE FROM dbo.Transfer",
    "UPDATE dbo.Transfer SET Status = 'Completed'",
    "EXEC dbo.usp_CreateTransfer",
    "DROP TABLE dbo.Transfer",
    "SELECT 1; DROP TABLE dbo.Transfer",
    "SELECT * INTO dbo.Copy FROM dbo.Transfer",
    "WITH x AS (SELECT 1 AS n) DELETE FROM dbo.Transfer",
    "/* hide */ SELECT 1; /* ; */ DELETE FROM dbo.Transfer",
])
def test_rejects_anything_else(sql):
    with pytest.raises(QueryRejected):
        check_select(sql)
