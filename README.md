# Cross-Border Remittance Data Platform

A portfolio project that simulates the data platform of a cross-border money transfer business. All data is synthetic.

> **Status:** in progress. Setup instructions, architecture, and demos will be added as each part is completed.

## Planned scope

**Phase 1: Data engineering**

- SQL Server database managed as a SQL Database Project and deployed from a dacpac with SqlPackage
- Synthetic data generation with Python and Faker
- Incremental extraction from SQL Server to Parquet
- Analytics models with dbt on DuckDB
- Data quality checks with dbt tests and pytest
- CI with GitHub Actions
- Power BI report built on the analytics models

**Phase 2: AI engineering**

- AI review of changed SQL as a pull request check
- English data Q&A agent using a read-only database login, with a measured evaluation set

## Planned repository layout

| Path | Purpose |
| --- | --- |
| `.github/workflows/` | CI and AI review workflows |
| `database/RemittanceDb/` | SQL project: tables, stored procedures, security |
| `scripts/` | Local deployment scripts |
| `data_generator/` | Synthetic data generation |
| `pipeline/` | Incremental extraction to Parquet |
| `analytics/` | dbt project |
| `tests/data_quality/` | Data quality tests |
| `ai_review/` | AI SQL review |
| `qa_agent/` | Data Q&A agent |
| `docs/` | Design notes and images |

Built in collaboration with Claude Code.
