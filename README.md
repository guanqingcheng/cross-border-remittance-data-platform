# Cross-Border Remittance Data Platform

[![CI](https://github.com/guanqingcheng/cross-border-remittance-data-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/guanqingcheng/cross-border-remittance-data-platform/actions/workflows/ci.yml)

A portfolio project that simulates the data platform of a cross-border money transfer business, from the transactional SQL Server database to a Power BI report. All data is synthetic, and no table, rule, or value comes from a real company.

> **Status:** Phase 1 (data engineering) is complete. Phase 2 (AI engineering) is planned.

![Power BI overview report](docs/images/powerbi-overview.webp)

## Background

A remittance business moves money between countries. A customer in one country sends money to a recipient in another, pays a fee, and the recipient gets the amount converted at that day's rate. Each transfer then moves through a status flow until it is completed, cancelled, or failed.

This project models six such corridors (for example US to Mexico and UK to India) and builds the data platform around them:

- an OLTP database where stored procedures enforce the business rules
- a pipeline that extracts only changed rows into a lakehouse-style analytics layer
- data quality checks that compare the warehouse with the source
- a CI pipeline that rebuilds and tests everything from an empty server on every push

## Architecture

```mermaid
flowchart LR
    subgraph oltp["SQL Server (OLTP)"]
        proj["SQL Database Project<br/>tables, procedures"]
        db[("RemittanceDb")]
        proj -->|dacpac + SqlPackage| db
    end

    gen["Python generator<br/>Faker"] -->|EXEC stored procedures| db
    db -->|incremental extract| raw["Parquet<br/>raw files"]

    subgraph analytics["Analytics (DuckDB)"]
        stg["dbt staging<br/>dedupe to latest version"]
        marts["dbt marts<br/>star schema"]
        stg --> marts
    end

    raw --> stg
    marts -->|export| pbi["Power BI report"]
    tests["pytest<br/>data quality"] -.->|reconcile| marts
    tests -.->|reconcile| db
```

## Highlights

- **Business rules live in the database.** Stored procedures validate eligibility, limits, fees, exchange rates, and status transitions, and write each status change and its history row in one transaction. See [docs/data-model.md](docs/data-model.md) for the 12 rules.
- **Declarative, repeatable deployment.** The schema is an SDK-style SQL Database Project. A second deployment with no changes produces an empty deploy report.
- **Reproducible synthetic data.** The generator is seeded, so the same command produces the same 3,200 transfers on any machine, including the CI runner.
- **Incremental extract.** The extract reads only rows changed since the last watermark, waits out a 5-minute safety lag, handles rows that share the watermark timestamp, and writes files and state atomically. A crash between the two writes only duplicates rows, which dbt removes.
- **Three layers of data quality checks.**
  1. Stored procedures reject bad input.
  2. dbt tests check the warehouse on its own: keys, nulls, accepted values, relationships.
  3. pytest checks the source rules directly in SQL Server and reconciles the warehouse against the source, including a stored procedure summary.
- **Tests that are proven to fail.** Key checks were broken on purpose to confirm they catch the problem. For example, keeping the oldest instead of the newest version of a transfer passes every dbt test, but the reconciliation test fails with 10 transfers in the wrong status.
- **CI from an empty server.** Every push builds the dacpac, starts a SQL Server container, loads two batches of data, and runs the extract, dbt, and pytest after each batch. The second batch exists to exercise the incremental path.
- **Report in version control.** The Power BI report is saved as a Power BI project (`.pbip`), so its layout and DAX measures are text files that can be reviewed in a pull request. The data folder is a parameter, not a hard-coded path.

## CI pipeline

Every push to `main` runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml) on a fresh GitHub-hosted runner, in about two minutes:

1. Build the dacpac and deploy it to a new SQL Server container with a random password.
2. Seed reference data and generate batch 1 (January to September).
3. Extract, run `dbt build`, and run pytest.
4. Generate batch 2 (October 1 to 15), which also finishes open transfers from batch 1.
5. Run the incremental extract, `dbt build`, and pytest again.
6. Export the marts for Power BI.

If any step fails, the run fails and the later steps are skipped.

![CI pipeline run](docs/images/ci-pipeline.png)

## Tech stack

| Area | Tools |
| --- | --- |
| Database | SQL Server 2019, SQL Database Project (Microsoft.Build.Sql), SqlPackage |
| Data generation | Python 3.13, Faker, pyodbc |
| Extract | Python, pyarrow (Parquet) |
| Transform | dbt-core 1.12 with dbt-duckdb, DuckDB |
| Data quality | dbt tests, pytest |
| CI | GitHub Actions, SQL Server Linux container |
| Reporting | Power BI Desktop (Power BI project format, DAX) |

## Repository layout

| Path | Purpose |
| --- | --- |
| `database/RemittanceDb/` | SQL Database Project: tables, sequence, stored procedures |
| `scripts/` | Local deployment script |
| `data_generator/` | Reference data seed and transfer generator |
| `pipeline/` | Incremental extract to Parquet and mart export |
| `analytics/` | dbt project: staging views and mart tables |
| `tests/data_quality/` | Source rule checks and warehouse reconciliation |
| `powerbi/` | Power BI project |
| `.github/workflows/` | CI pipeline |
| `docs/` | Data model, business rules, images |

## Data model

Eight tables: `Currency`, `Corridor`, `ExchangeRate`, `FeeSchedule`, `Customer`, `Recipient`, `Transfer`, and `TransferStatusHistory`. The full entity diagram, business rules, and design decisions are in [docs/data-model.md](docs/data-model.md).

The analytics layer is a star schema: `fct_transfers` at one row per transfer, with `dim_corridor` and `dim_customer`, plus `mart_corridor_daily` for daily corridor totals.

Amounts stay in their source currency (USD, GBP, or EUR), so the report never adds amounts across currencies.

## Run it locally

### Prerequisites

- Windows with PowerShell
- SQL Server 2019 or later (the free Developer edition works)
- .NET 8 SDK and SqlPackage (`dotnet tool install --global microsoft.sqlpackage`)
- Python 3.13
- Microsoft ODBC Driver 17 or 18 for SQL Server
- Power BI Desktop, only for the report

### Steps

1. Create a virtual environment and install the packages.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and adjust it. With `SQL_USERNAME` empty, the scripts use Windows authentication.

3. Build and deploy the database.

   ```powershell
   .\scripts\deploy-local.ps1
   ```

4. Load reference data and the first batch of transfers.

   ```powershell
   python data_generator/seed_reference_data.py
   python data_generator/generate_transfers.py --start 2026-01-01 --end 2026-09-30 --count 3000
   ```

5. Extract, build the warehouse, and test it.

   ```powershell
   python -m pipeline.extract
   dbt build --project-dir analytics --profiles-dir analytics
   pytest
   ```

6. Optional: load a second batch and repeat step 5 to see the incremental extract.

   ```powershell
   python data_generator/generate_transfers.py --start 2026-10-01 --end 2026-10-15 --count 200
   ```

7. Export the marts and open the report.

   ```powershell
   python -m pipeline.export_marts
   ```

   Open `powerbi/remittance-report.pbip`. The report reads from the `DataFolder` parameter (default `C:\remittance-data\exports`). Either change the parameter in **Transform data > Edit parameters** to your `data\exports` folder, or create a directory junction:

   ```powershell
   cmd /c mklink /J C:\remittance-data "<repo path>\data"
   ```

Secrets never go into git: connection settings live in `.env`, which is ignored, and CI generates a random SQL Server password for each run.

## Phase 2: AI engineering (planned)

- **AI SQL review in CI:** changed SQL files are reviewed by Claude, which returns a JSON verdict. The check fails closed, and a deliberately bad stored procedure (for example `ISNULL` around a column in a `WHERE` clause) must be blocked.
- **Data Q&A agent:** answers English questions about the data through a read-only database login, measured against an evaluation set of about 30 questions.

---

Built in collaboration with Claude Code.
