# Modern E-Commerce Analytics Platform — Architecture Blueprint

---

## 1. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Docker Compose Environment                        │
│                                                                             │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────────────┐     │
│  │ Data     │───▶│ PostgreSQL│◀───│ dbt Core │◀───│ Apache Airflow   │     │
│  │ Generator│    │ (Raw + DW)│    │          │    │ (Scheduler +     │     │
│  └──────────┘    └───────────┘    └──────────┘    │  Worker + Websrv)│     │
│                                                    └────────┬─────────┘     │
│  ┌──────────┐    ┌───────────┐                                │             │
│  │ pgAdmin  │────▶ PostgreSQL│                                │             │
│  └──────────┘    └───────────┘                                │             │
│                                                    ┌─────────▼─────────┐   │
│                                                    │  Metabase         │   │
│                                                    │  (BI + Dashboard) │   │
│                                                    └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key flows:**
- **Green arrows** = data ingestion path (CSV → PostgreSQL raw → dbt staging → warehouse)
- **Blue arrows** = orchestration triggers (Airflow initiates generator, dbt runs, refresh cycles)
- **Orange arrows** = BI query path (Metabase queries warehouse views for dashboards)

---

## 2. Detailed Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW                                     │
│                                                                          │
│  [CSV Generator]                                                        │
│   │  products.csv                                                       │
│   │  customers.csv                                                      │
│   │  orders.csv                                                         │
│   │  order_items.csv                                                    │
│   │  payments.csv                                                       │
│   ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                  PostgreSQL — Layer Architecture                │    │
│  │                                                                 │    │
│  │  SCHEMA: raw             SCHEMA: staging    SCHEMA: dw          │    │
│  │  ────────────────       ────────────────    ────────────────    │    │
│  │  raw.products           stg.products        dw.dim_product      │    │
│  │  raw.customers          stg.customers       dw.dim_customer     │    │
│  │  raw.orders             stg.orders          dw.dim_date         │    │
│  │  raw.order_items        stg.order_items     dw.fact_orders      │    │
│  │  raw.payments           stg.payments        dw.fact_payments    │    │
│  │                                              dw.fact_order_items│    │
│  │                                                                 │    │
│  │  SCHEMA: metrics                                                │    │
│  │  ────────────────                                               │    │
│  │  marts.kpi_summary                                              │    │
│  │  marts.daily_revenue                                           │    │
│  │  marts.customer_ltv                                            │    │
│  │  marts.order_funnel                                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                      │
│                                    ▼                                      │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Metabase Dashboards                          │    │
│  │  • Executive Overview (revenue, orders, AOV)                   │    │
│  │  • Customer Analytics (cohorts, LTV, retention)                │    │
│  │  • Operations (order funnel, fulfillment times)                │    │
│  │  • Product Performance (top sellers, inventory, margins)       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. System Components

| Component | Role | Image | Port |
|---|---|---|---|
| **PostgreSQL** | Primary data warehouse — three-layer schema (raw, staging, dw) + metrics schema | `postgres:16` | 5432 |
| **Airflow** | Orchestrates the full pipeline: data generation → ingestion → dbt → refresh | `apache/airflow:2.9.3` | 8080 |
| **dbt Core** | SQL transformations — idempotent, testable, documented | Custom image (dbt + psycopg2) | — |
| **Metabase** | Self-service BI, dashboards, ad-hoc exploration | `metabase/metabase:latest` | 3000 |
| **pgAdmin** | Database admin UI for development and debugging | `dpage/pgadmin4` | 5050 |
| **Data Generator** | Python script that writes realistic CSVs using Faker | Custom Python image | — |
| **ETL Ingestor** | Python script that bulk-copies CSVs into raw schema | Custom Python image | — |

---

## 4. Database Layers

### Layer 1 — `raw` (Source of Truth / Landing Zone)
- **Purpose:** Append-only copy of CSV files. No transformations, no NULL handling, no type casting.
- **Tables:** `raw.products`, `raw.customers`, `raw.orders`, `raw.order_items`, `raw.payments`
- **Columns match CSV exactly** — all `VARCHAR` or `TEXT` to avoid load failures.
- **Load strategy:** `TRUNCATE + INSERT` for idempotency (or incremental for production simulation).
- **Why:** Preserves raw data for replayability; decouples ingestion from transformation.

### Layer 2 — `staging` (Cleaned & Typed)
- **Purpose:** Casts raw strings to proper types (UUID, TIMESTAMP, NUMERIC, INT), renames columns, handles NULLs, deduplicates.
- **Tables:** `stg.products`, `stg.customers`, `stg.orders`, `stg.order_items`, `stg.payments`
- **Key transformations:**
  - String → proper data types
  - Default values for NULLs
  - Duplicate removal by business key
  - Standardized naming (snake_case)

### Layer 3 — `dw` (Dimensional Warehouse — Star Schema)
- **Dimensions:** `dw.dim_product`, `dw.dim_customer`, `dw.dim_date`
- **Facts:** `dw.fact_orders`, `dw.fact_payments`, `dw.fact_order_items`
- `dim_date` is built from scratch as a date spine (5–10 years), not from source data.
- **SCD Type 1** for customers (simple overwrite); SCD Type 2 is documented as a future enhancement.
- **Surrogate keys** generated via `SERIAL` or `SEQUENCE` for all dimensions.
- **Business keys** (e.g., `customer_id`, `product_id`) preserved in dimension rows for traceability.

### Layer 4 — `marts` (Business Metrics / Aggregates)
- **Purpose:** Pre-computed KPI tables consumable by Metabase without complex joins.
- **Model examples:**
  - `marts.kpi_daily_revenue` — revenue, orders, AOV per day
  - `marts.kpi_customer_ltv` — lifetime value per customer
  - `marts.kpi_order_funnel` — browse → cart → checkout → paid
  - `marts.kpi_product_performance` — units sold, gross margin, rank

---

## 5. ETL Layer Explanation

The ETL is split into **three distinct phases**, each a separate Airflow task:

### Phase 1: Data Generation (`etl/generate.py`)
- Uses `Faker` to produce realistic, relational data.
- **Cardinality constraints:** Customers have 1–10 orders; orders have 1–5 items; payments match order totals.
- Date ranges are configurable via environment variables.
- Outputs five CSV files to `/data/raw/`.

### Phase 2: Data Ingestion (`etl/ingest.py`)
- Reads CSVs from `/data/raw/`.
- Uses `psycopg2` + `COPY FROM` (bulk load) into `raw.*` tables.
- Wraps each load in a transaction; truncates before load for idempotency.
- Records row counts and duration in Airflow logs + optional audit table.

### Phase 3: Data Validation (`etl/validate.py`)
- Row-count parity check: source CSV row count matches `raw.*` row count.
- Referential integrity checks: `order_items.order_id` exists in `orders`, `payments.order_id` exists in `orders`.
- Not-null checks on key fields.
- Fails the pipeline early if data is corrupt, preventing bad data from reaching dbt.

---

## 6. Airflow Orchestration

### DAG Structure

```
ecommerce_pipeline
│
├── start_pipeline                          [DummyOperator — trigger]
│
├── generate_data                           [PythonOperator]
│   ├── gen_products                        [PythonOperator]
│   ├── gen_customers                       [PythonOperator]
│   ├── gen_orders                          [PythonOperator]
│   ├── gen_order_items                     [PythonOperator]
│   └── gen_payments                        [PythonOperator]
│
├── ingest_data                             [PythonOperator — COPY FROM]
│   └── validate_ingestion                  [PythonOperator — checksums]
│
├── dbt_run                                 [BashOperator — dbt run]
│   ├── dbt_run_staging                     [dbt model selector: staging]
│   ├── dbt_run_warehouse                   [dbt model selector: warehouse]
│   └── dbt_run_marts                       [dbt model selector: marts]
│
├── dbt_test                                [BashOperator — dbt test]
│
├── refresh_metabase                        [Simple HTTP Operator — Metabase API sync]
│
└── end_pipeline                            [DummyOperator — success notification]
```

### Key DAG Features
- **Schedule:** `@daily` (configurable to hourly for demo/simulation).
- **Retries:** 2 retries with exponential backoff for transient failures.
- **Alerting:** Slack/email on failure (configurable via Airflow variables).
- **Idempotency:** Every run is a full refresh. Support for incremental runs is documented as future work.
- **Task groups:** Staging, warehouse, and marts each run in a task group for visual clarity in the UI.

### Airflow Configuration
- **Executor:** `LocalExecutor` (adequate for single-node demo; documented migration path to `CeleryExecutor`).
- **Backend:** PostgreSQL as the Airflow metadata DB (same instance, separate database `airflow_meta`).
- **Connections:** One PostgreSQL connection (id: `ecommerce_dw`) used by all dbt and ETL tasks.
- **Variables:** `DATA_DIR`, `DBT_PROFILE_DIR`, `METABASE_API_KEY` stored as Airflow variables.

---

## 7. dbt Transformation Layer

### Project Structure

```
dbt/ecommerce/
│
├── dbt_project.yml
├── profiles.yml                    (mounted via Docker volume)
│
├── models/
│   ├── staging/
│   │   ├── _stg__sources.yml       (source definitions → raw.*)
│   │   ├── stg_products.sql
│   │   ├── stg_customers.sql
│   │   ├── stg_orders.sql
│   │   ├── stg_order_items.sql
│   │   └── stg_payments.sql
│   │
│   ├── warehouse/
│   │   ├── _dw__models.yml         (model configs + docs)
│   │   ├── dim_product.sql
│   │   ├── dim_customer.sql
│   │   ├── dim_date.sql
│   │   ├── fact_orders.sql
│   │   ├── fact_payments.sql
│   │   └── fact_order_items.sql
│   │
│   └── marts/
│       ├── _marts__models.yml
│       ├── kpi_daily_revenue.sql
│       ├── kpi_customer_ltv.sql
│       ├── kpi_order_funnel.sql
│       └── kpi_product_performance.sql
│
├── tests/
│   ├── assert_positive_revenue.sql
│   ├── assert_order_total_matches_items.sql
│   └── assert_unique_customer_ids.sql
│
├── macros/
│   ├── generate_surrogate_key.sql
│   └── dbt_date_spine.sql
│
└── docs/
    ├── overview.md
    └── data_dictionary.md
```

### Key dbt Design Decisions

| Decision | Rationale |
|---|---|
| **Materializations:** `staging` = `view`, `warehouse` = `table`, `marts` = `table` or `incremental` | Views avoid redundancy in staging; tables in warehouse for query performance; incremental on marts for daily refresh efficiency. |
| **Sources** reference `raw.*` tables — dbt tracks freshness via `freshness:` blocks | Freshness warnings fire if raw data is stale beyond threshold. |
| **Tests:** Singular + generic (unique, not_null, relationships) | Ensures data quality at every layer; tests run after every dbt run. |
| **Documentation:** `dbt docs generate` generates full lineage + data dictionary | Metabase users can reference dbt docs for field definitions. |
| **Macros** for surrogate keys and date spine | Reusable logic; avoids code duplication. |

### Transformation Logic (Conceptual)

- **stg_products.sql:** CAST string IDs to integers/UUIDs; normalize `price` to `NUMERIC(10,2)`;
- **stg_customers.sql:** Split `full_name` into `first_name`/`last_name`; parse `signup_date`;
- **dim_date.sql:** Generate date spine from Jan 1, 2020 to Dec 31, 2030 with day, week, month, quarter, year, fiscal period columns;
- **fact_orders.sql:** Join `stg_orders` + `stg_payments` + `dim_customer` + `dim_date`; compute `total_amount`, `payment_status`, `fulfillment_hours`;
- **kpi_daily_revenue.sql:** Aggregate `fact_orders` by `order_date` → revenue, order count, AOV, item count;
- **kpi_customer_ltv.sql:** Aggregate orders per customer → total spend, avg order value, customer lifetime in days.

---

## 8. BI Layer (Metabase)

### Metabase Setup
- **Embedded mode** — fully configured via environment variables (`MB_DB_TYPE=postgres`, `MB_DB_CONNECTION_URI`).
- **Auto-provisioning:** Startup script creates admin user and database connection via Metabase API.
- **Collections:** Pre-built collections mapped to business domains.

### Dashboard Designs

| Dashboard | Questions / Charts | Business Value |
|---|---|---|
| **Executive Overview** | Revenue trend (line), Orders/day (bar), AOV (number), Active customers (number) | Quick pulse on business health |
| **Customer Analytics** | New vs returning (pie), LTV histogram, Monthly cohort retention (heatmap), Top 10 customers (table) | Understand customer behavior and retention |
| **Order Funnel** | Funnel chart (visits → carts → checkouts → purchases), Abandonment rate over time | Identify conversion bottlenecks |
| **Product Performance** | Top 10 products (bar), Revenue by category (pie), Inventory turnover (table), Price elasticity scatter | Merchandising & inventory decisions |

### Refresh Strategy
- Metabase syncs table metadata on a schedule (configured via API).
- Dashboards are auto-refreshed via Metabase's native 5-minute cache.
- Full sync is triggered after every Airflow DAG completion via Metabase's `/api/database/{id}/sync` endpoint.

---

## 9. Docker Deployment Architecture

### Container Definitions

```
docker-compose.yml          # Single-file orchestration
docker/
├── postgres/
│   ├── init/
│   │   ├── 01_create_schemas.sql       (raw, staging, dw, marts)
│   │   └── 02_create_meta_tables.sql   (audit log, run metadata)
│   └── Dockerfile                      (custom init scripts)
│
├── airflow/
│   ├── Dockerfile                      (adds dbt, psycopg2, requirements)
│   ├── dags/
│   │   └── ecommerce_pipeline.py       (main DAG)
│   └── config/
│       └── airflow.cfg
│
├── dbt/
│   ├── Dockerfile                      (dbt-core + dbt-postgres)
│   └── profiles.yml                    (database connection config)
│
├── metabase/
│   └── Dockerfile                      (custom startup with API init)
│
├── generator/
│   ├── Dockerfile                      (Python 3.12 + Faker)
│   └── generate.py
│
└── etl/
    ├── Dockerfile                      (Python 3.12 + psycopg2)
    ├── ingest.py
    └── validate.py
```

### Docker Compose Service Breakdown

| Service | Depends On | Volumes | Resource Limits |
|---|---|---|---|
| `postgres` | — | `pgdata:/var/lib/postgresql/data`, `./docker/postgres/init:/docker-entrypoint-initdb.d` | 1GB mem, 1 CPU |
| `airflow-webserver` | `postgres` | `./airflow/dags:/opt/airflow/dags`, `./data:/data` | 512MB mem, 0.5 CPU |
| `airflow-scheduler` | `postgres` | Same as webserver | 512MB mem, 0.5 CPU |
| `generator` | — | `./data:/data` | Ephemeral |
| `etl` | `postgres` | `./data:/data` | Ephemeral |
| `dbt` | `postgres` | `./dbt:/dbt` | 256MB mem |
| `metabase` | `postgres` | `./metabase/plugins:/plugins` | 1GB mem, 1 CPU |
| `pgadmin` | `postgres` | — | 256MB mem |

### Networking
- **One bridge network:** `ecommerce-net` (all services communicate internally).
- **Port mappings:** Only expose Metabase (3000), Airflow (8080), and pgAdmin (5050) to host.

### Startup Order
1. PostgreSQL boots first (health check: `pg_isready`).
2. Airflow services start (init metadata DB, create admin user).
3. Generator + ETL containers run on demand via Airflow (not as long-running services).
4. dbt runs as an Airflow task (BashOperator calls dbt CLI inside the Airflow container).
5. Metabase starts (can start in parallel with Airflow; connects to PostgreSQL).
6. pgAdmin starts last (no hard dependency).

---

## 10. Project Folder Structure

```
modern-ecommerce-analytics/
│
├── airflow/
│   ├── dags/
│   │   ├── __init__.py
│   │   └── ecommerce_pipeline.py        # Main orchestration DAG
│   ├── Dockerfile                        # Airflow + dbt + Python deps
│   ├── requirements.txt                  # Python packages for Airflow
│   └── plugins/
│       └── __init__.py
│
├── etl/
│   ├── __init__.py
│   ├── generate.py                      # Fake data generator
│   ├── ingest.py                        # CSV → raw schema loader
│   └── validate.py                      # Data quality checks
│
├── dbt/
│   └── ecommerce/                        # dbt project root
│       ├── dbt_project.yml
│       ├── profiles.yml                  # (mounted at runtime)
│       ├── models/
│       │   ├── staging/
│       │   │   ├── _stg__sources.yml
│       │   │   ├── stg_products.sql
│       │   │   ├── stg_customers.sql
│       │   │   ├── stg_orders.sql
│       │   │   ├── stg_order_items.sql
│       │   │   └── stg_payments.sql
│       │   ├── warehouse/
│       │   │   ├── _dw__models.yml
│       │   │   ├── dim_product.sql
│       │   │   ├── dim_customer.sql
│       │   │   ├── dim_date.sql
│       │   │   ├── fact_orders.sql
│       │   │   ├── fact_payments.sql
│       │   │   └── fact_order_items.sql
│       │   └── marts/
│       │       ├── _marts__models.yml
│       │       ├── kpi_daily_revenue.sql
│       │       ├── kpi_customer_ltv.sql
│       │       ├── kpi_order_funnel.sql
│       │       └── kpi_product_performance.sql
│       ├── macros/
│       │   ├── generate_surrogate_key.sql
│       │   └── dbt_date_spine.sql
│       ├── tests/
│       │   ├── assert_positive_revenue.sql
│       │   ├── assert_order_total_matches_items.sql
│       │   └── assert_unique_customer_ids.sql
│       ├── docs/
│       │   ├── overview.md
│       │   └── data_dictionary.md
│       └── logs/
│
├── data/
│   ├── raw/                             # Generated CSV files
│   └── archive/                         # Compressed historical CSVs
│
├── sql/
│   ├── init/
│   │   ├── 01_create_schemas.sql        # Schema creation DDL
│   │   └── 02_create_meta_tables.sql    # Audit/run metadata tables
│   ├── analytics/
│   │   ├── cohort_retention.sql         # Reference queries for Metabase
│   │   └── rfm_analysis.sql
│   └── maintenance/
│       ├── vacuum_analyze.sql
│       └── partition_maintenance.sql
│
├── dashboards/
│   ├── executive_overview.json          # Metabase export (JSON card)
│   ├── customer_analytics.json
│   ├── product_performance.json
│   └── order_funnel.json
│
├── docker/
│   ├── postgres/
│   │   ├── Dockerfile
│   │   └── init/
│   │       └── 01_create_schemas.sql
│   ├── generator/
│   │   └── Dockerfile
│   ├── etl/
│   │   └── Dockerfile
│   ├── dbt/
│   │   ├── Dockerfile
│   │   └── profiles.yml
│   └── metabase/
│       └── Dockerfile
│
├── tests/
│   ├── etl/
│   │   ├── test_generate.py             # Tests for data generator
│   │   ├── test_ingest.py               # Tests for data ingestion
│   │   └── test_validate.py             # Tests for validation logic
│   ├── dbt/                             # dbt test output reports
│   │   └── README.md
│   └── conftest.py                      # Shared test fixtures
│
├── logs/
│   ├── airflow/                         # Airflow logs (Docker bind mount)
│   ├── dbt/                             # dbt run logs
│   └── pipeline/                        # Custom pipeline logs
│
├── docs/
│   ├── architecture.md                  # This document
│   ├── setup.md                         # Local dev setup instructions
│   ├── data_dictionary.md               # Business glossary
│   ├── dbt_documentation.md             # dbt docs instructions
│   └── troubleshooting.md               # Common issues & solutions
│
├── scripts/
│   ├── reset_database.sh                # Full DB reset for dev
│   ├── run_full_pipeline.sh             # Manual pipeline trigger (no Airflow)
│   └── export_dashboards.sh             # Export Metabase dashboards to JSON
│
├── .env.example                         # Environment variable template
├── .gitignore
├── pyproject.toml                       # Python project configuration (Ruff, pytest)
├── requirements.txt                     # Root-level dev requirements
└── docker-compose.yml                   # Single-file deployment orchestration
```

### Folder Purpose Summary

| Folder | Purpose |
|---|---|
| `airflow/` | DAG definitions, Airflow Docker image build, plugin extensions |
| `etl/` | Data generation, ingestion, and validation Python modules |
| `dbt/` | Complete dbt project with models, macros, tests, and docs |
| `data/` | Generated CSV files (raw) and historical archives |
| `sql/` | Standalone DDL scripts, analytical reference queries, maintenance routines |
| `dashboards/` | Metabase dashboard JSON exports for version control |
| `docker/` | Per-service Dockerfiles and init scripts for custom builds |
| `tests/` | Python unit/integration tests for ETL; dbt test output artifact folder |
| `logs/` | Runtime logs from Airflow, dbt, and pipeline runs |
| `docs/` | Architecture, setup, data dictionary, and operational documentation |
| `scripts/` | Shell utilities for reset, manual execution, and exports |

---

## Architectural Principles & Trade-offs

| Principle | Application | Trade-off |
|---|---|---|
| **Single source of truth** | Raw layer is append-only, never mutated | Storage cost for raw data — acceptable at this scale |
| **Idempotent pipelines** | Full refresh each run | Slower than incremental; acceptable for demo; incremental path documented |
| **Separation of concerns** | ETL (Python) ≠ Transformation (dbt/SQL) | Two runtimes to maintain; clarity and tooling benefits outweigh |
| **Immediate consistency** | Full DAG: generate → ingest → dbt → sync | Pipeline latency = several minutes; acceptable for daily analytics |
| **Self-service BI** | Metabase with curated marts | Users cannot write arbitrary SQL to raw data; governed via marts layer |

---

## Future Enhancements (Documented for Phase 2)

- **CDC from production DB** instead of CSV generation
- **SCD Type 2** for selected dimension attributes
- **Incremental dbt models** for fact tables
- **dbt-expectations** package for expressive data tests
- **Great Expectations** integration for profile-level validation
- **CeleryExecutor** for Airflow horizontal scaling
- **Reverse ETL** — push KPIs back to operational systems
- **Slack/Teams alerting** for anomaly detection
- **Superset** as an alternative BI tool alongside Metabase

---

*This blueprint defines the complete architecture. The next phase is implementation, starting with `docker-compose.yml`, then PostgreSQL init scripts, then the ETL layer, then dbt models, then Airflow DAGs, and finally Metabase dashboard configuration.*
