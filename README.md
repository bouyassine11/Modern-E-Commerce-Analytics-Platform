# Modern E-Commerce Analytics Platform

End-to-end analytics platform for an online store with synthetic data
generation, ELT pipelines, dimensional modelling, self-service BI, and
Airflow orchestration — all running locally in Docker.

---

## Architecture

```
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌───────────┐
│  Data Gen   │───▶│  ETL     │───▶│  dbt    │───▶│  Metabase │
│  (Python)   │    │ Pipeline │    │  Models │    │  BI       │
└─────────────┘    └──────────┘    └─────────┘    └───────────┘
       │                 │               │               │
       ▼                 ▼               ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                     PostgreSQL (3 layers)                     │
│  raw (TEXT)  →  staging (typed)  →  dw (star schema)        │
│                                       └─ marts (reports)     │
│  monitoring (audit tables)                                    │
└──────────────────────────────────────────────────────────────┘
                        ▲
                ┌───────┴───────┐
                │  Airflow      │
                │  Orchestrator │
                └───────────────┘
```

### Data Flow

1. **Generate** — Synthetic CSV data (500 products, 10k customers, 100k orders)
2. **Extract** — Read CSVs from `data/raw/`
3. **Transform** — Trim, lowercase, dedup, validate FKs
4. **Load** — `COPY FROM STDIN` into `raw.*` tables (all TEXT columns)
5. **dbt run** — Staging (type cast) → Intermediate (enrichment) → Warehouse (star schema) → Marts (aggregated reports)
6. **dbt test** — 109 data quality assertions
7. **Metabase** — Self-service dashboards querying `rpt_*` tables

---

## Folder Structure

```
.
├── airflow/                         # Airflow DAGs and plugins
│   ├── dags/
│   │   └── ecommerce_pipeline.py    # Main pipeline DAG (10 tasks)
│   └── plugins/
│       └── ecommerce_monitor.py     # Monitoring dashboard plugin
├── data/
│   ├── raw/                         # Generated CSV files
│   └── processed/                   # Cleaned CSVs (Airflow only)
├── dbt/
│   └── ecommerce/                   # dbt project root
│       ├── dbt_project.yml
│       ├── profiles.yml             # PostgreSQL connection config
│       ├── models/
│       │   ├── staging/             # 5 stg_* models (views)
│       │   ├── intermediate/        # 1 int_* model (ephemeral)
│       │   └── marts/               # 4 dim + 1 fact + 8 rpt tables
│       ├── snapshots/               # SCD Type 2 (snap_customers)
│       ├── tests/                   # 8 singular data quality tests
│       └── macros/                  # 4 generic test macros
├── docker/
│   ├── airflow/Dockerfile           # Airflow + dbt + providers
│   └── postgres/
│       ├── Dockerfile               # PostgreSQL + init scripts
│       └── init/
│           ├── 02_create_schemas.sql     # schemas + raw tables
│           └── 03_monitoring.sql         # audit tables
├── docker-compose.yml               # 6 services, 4 volumes, 1 network
├── docs/                            # Architecture, design, KPI docs
│   ├── architecture.md
│   ├── database_design.md
│   ├── metabase_dashboards.md
│   └── monitoring_architecture.md
├── etl/                             # Python ETL pipeline
│   ├── generate.py                  # Synthetic data entry point
│   ├── ingest.py                    # Extract → Transform → Load
│   ├── extract.py                   # CSV reader
│   ├── transform.py                 # Clean, validate, dedup
│   ├── load.py                      # TRUNCATE + COPY FROM STDIN
│   ├── monitor.py                   # PipelineLogger audit class
│   ├── config.py                    # YAML config loader
│   ├── utils.py                     # CSV I/O, logging, timing
│   └── generators/                  # Per-entity data generators
├── tests/                           # pytest suite
│   ├── test_generators.py           # 12 data generation tests
│   ├── test_transform.py            # 12 transformation tests
│   ├── test_extract.py              # 4 extraction tests
│   ├── test_utils.py                # 3 utility tests
│   ├── test_monitor.py              # 9 monitor tests
│   └── test_airflow_dag.py          # 7 DAG validation tests
├── .github/workflows/ci.yml         # GitHub Actions pipeline
├── config.yaml                      # Central configuration
├── pyproject.toml                   # Python project settings
└── requirements.txt                 # Python dependencies
```

---

## Installation

### Prerequisites

- **Docker** 24+ with Docker Compose plugin
- **Python** 3.12+ (for local ETL runs outside Docker)
- **Git**

### Clone & Configure

```bash
git clone <repo-url> ecommerce-analytics
cd ecommerce-analytics

# Environment configuration
cp .env.example .env

# Generate a Fernet key (required by Airflow)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Copy the output into .env: AIRFLOW_FERNET_KEY=<key>
```

---

## Running Docker

### Start all services

```bash
docker compose up -d
```

This starts 6 containers:
| Service | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | Data warehouse + metadata DBs |
| `airflow-webserver` | 8080 | Airflow UI |
| `airflow-scheduler` | — | Task scheduling |
| `airflow-init` | — | DB init (runs once, exits) |
| `metabase` | 3000 | Self-service BI |
| `pgadmin` | 5050 | Database management |

### Check health

```bash
docker compose ps
docker compose logs airflow-webserver | tail -10
```

### Stop

```bash
docker compose down
```

### Full reset (destroys data)

```bash
docker compose down -v
```

---

## Running Airflow

Access the Airflow web UI at [http://localhost:8080](http://localhost:8080).

**Default credentials**: `admin` / `admin`

### Trigger the pipeline manually

1. Navigate to **DAGs** tab
2. Find `ecommerce_analytics_pipeline`
3. Click the ▶️ play button → **Trigger DAG**

### Pipeline tasks

```
start_pipeline_run
  └─ generate_data
       └─ extract_data
            └─ transform_data
                 └─ load_raw_tables
                      └─ dbt_run
                           └─ dbt_test
                                └─ ingest_dbt_test_results
                                     └─ refresh_metabase
                                          └─ generate_kpi_report
                                               └─ complete_pipeline_run
```

### Variables

Configured in Airflow UI → Admin → Variables:

| Variable | Default | Purpose |
|---|---|---|
| `dbt_seed_enabled` | `false` | Enable dbt seed loading |
| `metabase_url` | `http://metabase:3000` | Metabase API endpoint |
| `postgres_user` | `postgres` | Warehouse DB user |
| `postgres_password` | `postgres` | Warehouse DB password |
| `postgres_db` | `ecommerce` | Warehouse DB name |

---

## Running dbt

### Inside Docker

The dbt project lives at `/opt/airflow/dbt/ecommerce/` inside the Airflow container.

```bash
# Interactive shell
docker compose exec airflow-scheduler bash

# dbt commands
dbt debug
dbt run
dbt test
dbt docs generate
dbt docs serve
```

### Outside Docker (local dbt)

```bash
cd dbt/ecommerce

# Requires a running PostgreSQL instance
dbt debug
dbt run
dbt test
```

### dbt Models

| Layer | Materialization | Models | Schema |
|---|---|---|---|
| **Staging** | View | `stg_products`, `stg_customers`, `stg_orders`, `stg_order_items`, `stg_payments` | `stg` |
| **Intermediate** | Ephemeral | `int_orders_enriched` | `stg` |
| **Warehouse** | Table / Incremental | `dim_customer` (SCD2), `dim_product`, `dim_date`, `fact_sales` | `dw` |
| **Marts (Reports)** | Table | `rpt_daily_revenue`, `rpt_monthly_revenue`, `rpt_customer_lifetime_value`, `rpt_top_products`, `rpt_top_categories`, `rpt_country_revenue`, `rpt_repeat_customers`, `rpt_payment_analysis` | `public` |

### Data Quality

109 tests across all models:
- **Singular tests** (8): Business rule SQL assertions
- **Generic tests** (4 macros): `not_empty_string`, `valid_email`, `positive_value`, `date_in_past`
- **Column tests** (97): `not_null`, `unique`, `accepted_values`, `relationships`

```bash
dbt test                              # Run all tests
dbt test --select tag:core            # Core subset
dbt test --select source:ecommerce+   # Source freshness
```

---

## ETL Pipeline (Standalone)

Run the ETL pipeline directly (without Airflow):

```bash
# Generate synthetic data
python -m etl.generate

# Dry-run (no database writes)
python -m etl.ingest --dry-run

# Full pipeline
python -m etl.ingest

# With custom config
python -m etl.ingest --config custom_config.yaml --log-level DEBUG
```

### Generator details

| Entity | Count | Distribution |
|---|---|---|
| Products | 500 | 8 categories with per-category price ranges |
| Customers | 10,000 | Faker-generated, Pareto signup (2020–2026) |
| Orders | 100,000 | Recency-biased dates, Zipf-sampled products |
| Order Items | 300,000 | 1–5 items per order |
| Payments | 100,000 | 4 statuses, refunds as negative amounts |

### ETL phases

| Phase | Action | Row tracking |
|---|---|---|
| Extract | Read CSV → `list[dict]` | Raw counts |
| Transform | Trim whitespace, lowercase emails, dedup by business key, validate FKs | Before/after/removed |
| Load | TRUNCATE → `COPY FROM STDIN` (single transaction) | Rows loaded |

---

## Dashboard Overview

### Executive Dashboard (`localhost:3000/dashboard/1`)

| KPI Card | Source | Chart |
|---|---|---|
| Total Revenue | `rpt_daily_revenue` | — |
| Total Orders | `rpt_daily_revenue` | — |
| Total Customers | `rpt_daily_revenue` | — |
| Avg Order Value | `rpt_daily_revenue` | — |
| — | — | Revenue Trend (area) |
| — | — | Orders Trend (area) |

### Sales Dashboard (`localhost:3000/dashboard/2`)

| Chart | Source |
|---|---|
| Revenue by Category (bar) | `rpt_top_categories` |
| Revenue by Country (bar) | `rpt_country_revenue` |
| Revenue by Product (table) | `rpt_top_products` |

### Customer Dashboard (`localhost:3000/dashboard/3`)

| Chart | Source |
|---|---|
| Customer Growth (line) | `rpt_repeat_customers` |
| Repeat Customers (bar) | `rpt_repeat_customers` |
| Customer LTV by Segment (bar) | `rpt_customer_lifetime_value` |

### Product Dashboard (`localhost:3000/dashboard/4`)

| Chart | Source |
|---|---|
| Top Products (bar, top 20) | `rpt_top_products` |
| Category Performance (combo) | `rpt_top_categories` |
| Top Categories (pie) | `rpt_top_categories` |
| Product Detail (table) | `rpt_top_products` |

**Cross-filtering**: Executive → Sales → Product. Click any data point to
drill down.

---

## KPI Definitions

| KPI | Formula | Source | Refresh |
|---|---|---|---|
| **Revenue** | `SUM(total_amount)` where `payment_status IN ('paid', 'pending')` | `rpt_daily_revenue` | Daily |
| **Orders** | `COUNT(DISTINCT order_id)` | `rpt_daily_revenue` | Daily |
| **Avg Order Value (AOV)** | `total_revenue / total_orders` | `rpt_daily_revenue` | Daily |
| **Customer LTV** | `SUM(total_amount)` per customer | `rpt_customer_lifetime_value` | Daily |
| **Repeat Purchase Rate** | `customers_with_2+_orders / customers_with_1+_order` | `rpt_repeat_customers` | Daily |
| **Revenue by Category** | `SUM(total_amount) GROUP BY category` | `rpt_top_categories` | Daily |
| **Revenue by Country** | `SUM(total_amount) GROUP BY country` | `rpt_country_revenue` | Daily |
| **Top Products** | `SUM(total_amount) GROUP BY product ORDER BY revenue DESC` | `rpt_top_products` | Daily |
| **Revenue Growth (MoM)** | `(current_month_revenue - prev_month_revenue) / prev_month_revenue * 100` | `rpt_monthly_revenue` | Daily |
| **Revenue Share (%)** | `category_revenue / total_revenue * 100` | `rpt_top_categories` | Daily |
| **RFM Segment** | Quintile-based R + F + M scoring → Champions / Loyal / At Risk / Lost | `rpt_customer_lifetime_value` | Daily |

---

## Monitoring & Observability

Three audit tables in the `dw.monitoring` schema track pipeline health:

| Table | Grain | Key columns |
|---|---|---|
| `etl_runs` | Per pipeline execution | status, duration, rows, error_message |
| `etl_task_runs` | Per task | task_type, status, rows_processed, records_removed |
| `data_quality_results` | Per dbt test | test_name, status, failures, severity |

### Operational views

- `monitoring.pipeline_daily_metrics` — Daily success/fail rates
- `monitoring.task_performance_stats` — P50/P95/P99 durations
- `monitoring.data_quality_summary` — Last 7 days of test results
- `monitoring.recent_errors` — Last 50 failures
- `monitoring.pipeline_table_sizes` — PostgreSQL table byte sizes

### Pipeline flow

```
start_pipeline_run
  ├── (each PythonOperator logs start/completion to etl_task_runs)
  ├── (dbt_test writes to target/run_results.json)
  ├── ingest_dbt_test_results → data_quality_results
  └── complete_pipeline_run (finalizes etl_runs)
```

---

## Testing

```bash
# Unit tests (no PostgreSQL required)
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=etl

# ETL integration test (requires Docker)
./tests/integration/test_pipeline.sh

# Airflow DAG validation
pytest tests/test_airflow_dag.py -v

# dbt tests (requires database)
dbt test --project-dir dbt/ecommerce
```

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push/PR:

```
Lint (ruff + yamllint)
  └─ Test (pytest — unit tests)
       └─ dbt Validate (dbt debug + compile)
            └─ Docker Build (Airflow + Postgres images)
```

---

## Environment Variables

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `POSTGRES_USER` | `postgres` | | PostgreSQL user |
| `POSTGRES_PASSWORD` | `postgres` | | PostgreSQL password |
| `POSTGRES_DB` | `ecommerce` | | Default database |
| `PG_PORT` | `5432` | | PostgreSQL host port |
| `AIRFLOW_FERNET_KEY` | — | **Yes** | Airflow encryption key |
| `AIRFLOW_PORT` | `8080` | | Airflow webserver port |
| `MB_ENCRYPTION_KEY` | — | | Metabase encryption key |
| `METABASE_PORT` | `3000` | | Metabase port |
| `PGADMIN_EMAIL` | `admin@ecommerce.com` | | pgAdmin login email |
| `PGADMIN_PASSWORD` | `admin` | | pgAdmin login password |

Generate the Fernet key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Future Enhancements

| Area | Enhancement |
|---|---|
| **CDC** | Replace full TRUNCATE-load with `_etl_loaded_at`-based incremental extraction |
| **Late-arriving data** | Add `fact_sales` late-arriving fact handling with recency window |
| **Exports** | Scheduled PDF/CSV exports from Metabase subscriptions |
| **Alerting** | Prometheus + Grafana for real-time pipeline metrics |
| **Schema evolution** | dbt `on_schema_change='append_new_columns'` for warehouse tables |
| **Data catalog** | dbt docs serve with lineage graph and column-level lineage |
| **Multi-tenant** | Add `tenant_id` to dimension tables for SaaS multi-tenancy |
| **Reverse ETL** | Push segments/customer scores to operational systems |
| **Cost modelling** | Estimated query cost tracking per dashboard |
| **dbt source freshness** | Add `_etl_loaded_at` to raw table DDL for full freshness monitoring |

---

## License

Internal use. Not for production deployment without security review.
