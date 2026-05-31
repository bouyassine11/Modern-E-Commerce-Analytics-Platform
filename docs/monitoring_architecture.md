# Monitoring & Observability Architecture

## Overview

Three-layer observability strategy covering pipeline execution, task-level
metrics, and data quality outcomes across all four system components:

| Layer | What | Where |
|---|---|---|
| 1 — Audit Tables | Persistent run + task logs | `monitoring` schema in PostgreSQL |
| 2 — Application Logs | Structured text logs to stdout + files | Python `logging` + Airflow task logs |
| 3 — System Metrics | PostgreSQL table sizes, Airflow DAG views | `pg_stat_all_tables`, Airflow UI |

---

## Audit Tables

All three tables live in the `monitoring` schema inside the `ecommerce`
database. Created automatically by the PostgreSQL init script
(`docker/postgres/init/03_monitoring.sql`) and bootstrapped on first use by
`PipelineLogger._ensure_tables()`.

### `monitoring.etl_runs`

One row per pipeline execution (standalone ETL or Airflow DAG run).

| Column | Type | Description |
|---|---|---|
| `run_id` | `SERIAL PK` | Auto-increment identifier |
| `pipeline_name` | `TEXT` | `'etl_ingest'` or `'airflow_ecommerce_pipeline'` |
| `dag_run_id` | `TEXT` | Airflow `dag_run.run_id` (null for standalone) |
| `status` | `TEXT` | `'running'`, `'completed'`, `'failed'` |
| `started_at` | `TIMESTAMPTZ` | UTC timestamp on insert |
| `completed_at` | `TIMESTAMPTZ` | UTC timestamp on completion |
| `duration_seconds` | `NUMERIC(10,2)` | Computed as `completed_at - started_at` |
| `rows_generated` | `INTEGER` | Rows created by data generation |
| `rows_extracted` | `INTEGER` | Rows read from source CSVs |
| `rows_loaded` | `INTEGER` | Rows COPY'd into raw tables |
| `error_message` | `TEXT` | Exception message on failure |
| `metadata` | `JSONB` | KPI snapshots, DAG metadata |

### `monitoring.etl_task_runs`

One row per task within a pipeline run. FK to `etl_runs.run_id` with CASCADE
delete — when a run is purged, all its task records are removed.

| Column | Type | Description |
|---|---|---|
| `task_run_id` | `SERIAL PK` | Auto-increment |
| `run_id` | `INTEGER FK` | Parent pipeline run |
| `task_name` | `TEXT` | e.g. `'extract_products'`, `'load_orders'` |
| `task_type` | `TEXT` | `'generate'`, `'extract'`, `'transform'`, `'load'`, `'dbt_run'`, `'dbt_test'` |
| `status` | `TEXT` | `'running'`, `'completed'`, `'failed'` |
| `started_at` | `TIMESTAMPTZ` | UTC timestamp |
| `completed_at` | `TIMESTAMPTZ` | UTC timestamp |
| `duration_seconds` | `NUMERIC(10,2)` | Computed |
| `rows_processed` | `INTEGER` | Rows output by the task |
| `records_before` | `INTEGER` | Input row count (transform phase) |
| `records_after` | `INTEGER` | Output row count (transform phase) |
| `records_removed` | `INTEGER` | `records_before - records_after` |
| `error_message` | `TEXT` | Exception message on failure |

### `monitoring.data_quality_results`

One row per dbt test execution. FK to `etl_runs.run_id` with SET NULL on
delete — test results survive pipeline run cleanup.

| Column | Type | Description |
|---|---|---|
| `result_id` | `SERIAL PK` | Auto-increment |
| `run_id` | `INTEGER FK` | Parent pipeline run (nullable) |
| `test_execution_id` | `TEXT` | dbt `unique_id` from `run_results.json` |
| `test_name` | `TEXT` | dbt test name |
| `model_name` | `TEXT` | Model under test (first dependency) |
| `column_name` | `TEXT` | Column under test |
| `severity` | `TEXT` | `'error'` or `'warn'` |
| `status` | `TEXT` | `'pass'`, `'fail'`, `'skipped'` |
| `failures` | `INTEGER` | Failure count |
| `execution_time_seconds` | `NUMERIC(10,3)` | Test execution time |
| `test_query` | `TEXT` | Compiled SQL of the test |
| `tested_at` | `TIMESTAMPTZ` | UTC timestamp |

---

## Logging Architecture

### Python ETL Pipeline

```
                          ┌──────────────────────┐
                          │   ingest.py           │
                          │   PipelineLogger      │
                          │   (monitor.start_run) │
                          └──────┬───────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
    │ extract.py  │   │transform.py  │   │   load.py    │
    │ monitor     │   │ monitor      │   │   monitor    │
    │ .start_task │   │ .start_task  │   │  .start_task │
    │ .complete   │   │ .complete    │   │  .complete   │
    └─────────────┘   └──────────────┘   └──────────────┘
```

**Log output** goes to two destinations in `setup_logging()`:
- **File**: `logs/etl_<timestamp>.log` — standard Python logging format
- **Console**: stdout — captured by Docker / Airflow

**Structured fields in every log line**:
```
[2026-05-31 08:00:00] INFO     etl.ingest | Phase 1/3: Extract
[2026-05-31 08:00:01] INFO     etl.extract | Extracting products...
[2026-05-31 08:00:02] INFO     etl.utils | Read 500 rows from products.csv
```

### Airflow DAG Logging

```
start_pipeline_run (monitor.start_run)
    │
    ├── generate_data    (logs rows_generated)
    ├── extract_data     (monitor.start_task / .complete_task per table)
    ├── transform_data   (monitor.start_task / .complete_task per table)
    ├── load_raw_tables  (monitor.start_task / .complete_task per table)
    ├── dbt_run          (BashOperator — logged via Airflow)
    ├── dbt_test         (BashOperator — logged via Airflow)
    ├── ingest_dbt_test_results (parse run_results.json → data_quality_results)
    ├── refresh_metabase
    ├── generate_kpi_report (monitor.snapshot_kpis)
    │
complete_pipeline_run (monitor.complete_run)
```

Each PythonOperator uses `PipelineLogger` directly to log task metrics.
`BashOperator` tasks rely on Airflow's native log capture. The
`ingest_dbt_test_results` task parses `target/run_results.json` from the dbt
project and inserts test outcomes into `data_quality_results`.

### dbt Logging

dbt output is captured by Airflow's BashOperator log mechanism. After
`dbt_test` completes, `ingest_dbt_test_results` reads
`target/run_results.json` and writes structured results to
`monitoring.data_quality_results`.

To enable this in the Airflow container:
```yaml
# run_results.json is written by dbt to the project's target/ directory
# which persists on the shared volume mounted at /opt/airflow/dbt/ecommerce
```

---

## Pipeline Metrics

### Tracked metrics by component

| Component | Metrics | Collection Method |
|---|---|---|
| **ETL Pipeline** | Duration per phase, rows per table, dedup ratio, FK violation count | `PipelineLogger` task writes |
| **Airflow** | DAG duration, task duration, retry count, SLA misses | Airflow DB + metadata API |
| **dbt** | Model run duration, test pass/fail, freshness staleness | `run_results.json` → `PipelineLogger.ingest_dbt_results()` |
| **PostgreSQL** | Table sizes, row count estimates, index usage, query performance | `pg_stat_all_tables` views |

### Computation details

- **Dedup ratio** = `records_removed / records_before` per transform task
- **Load throughput** = `rows_loaded / duration_seconds` (rows/sec)
- **Test pass rate** = `pass / (pass + fail)` per dbt run
- **Pipeline SLA** = DAG completes within configured `execution_timeout` (2h)

---

## Error Tracking

### Error classification

| Category | Source | Example |
|---|---|---|
| **Data errors** | transform.py | FK violations, status validation failures |
| **Infrastructure** | Docker, PostgreSQL | Connection refused, disk full |
| **Pipeline logic** | Python code | Missing CSV, type mismatch |
| **dbt failures** | dbt_run/dbt_test | Model compilation error, test failure |

### Error propagation

1. Python exceptions are caught in `ingest.py` / Airflow task callables
2. `error_message` is written to `etl_task_runs` / `etl_runs`
3. Airflow marks the task as `failed` and retries (2 retries, 5 min delay)
4. On final failure, email sent to `admin@ecommerce.com`
5. `monitoring.recent_errors` view shows last 50 failures across all sources

### Alerting thresholds

| Metric | Threshold | Action |
|---|---|---|
| Pipeline failure | Any `status='failed'` | Airflow email alert |
| dbt test failure | > 0 `failures` on severity `error` | Airflow email alert + KPI report note |
| Transform dedup > 10% | `records_removed / records_before > 0.10` | WARN log + monitoring note |
| Load duration > P95 | `> P95 of last 30 days` | WARN log |

---

## Operational Dashboard Design

### Dashboard layout (2 columns, 3 rows)

```
┌────────────────────────────────────┬────────────────────────────────────┐
│ Pipeline Health (KPI cards)        │ Recent Errors (table)              │
│ - Last run status / duration       │ Columns: timestamp | source | name │
│ - Success rate (7d)                │          | status | error_message  │
│ - Avg duration (7d)                │ Sorted: started_at DESC, limit 20 │
│ - Active tasks running              │                                     │
├────────────────────────────────────┼────────────────────────────────────┤
│ Pipeline Duration Trend (bar)      │ Task Performance (bar)             │
│ X: run_date   Y: avg_duration_sec  │ X: task_type   Y: avg_duration_sec │
│ Series: successful_runs, fail      │ Series: p50 / p95 / p99            │
│ Source: pipeline_daily_metrics      │ Source: task_performance_stats      │
├────────────────────────────────────┼────────────────────────────────────┤
│ Data Quality (table)               │ Table Sizes (bar)                  │
│ Columns: test_name | model |       │ X: full_table_name  Y: row_count  │
│          status | failures | date  │ Source: pipeline_table_sizes       │
│ Source: data_quality_summary       │ Color: schema (raw/staging/dw)     │
└────────────────────────────────────┴────────────────────────────────────┘
```

### Source views

| View | Purpose |
|---|---|
| `monitoring.pipeline_latest_runs` | Last 30 run statuses for KPI cards |
| `monitoring.pipeline_daily_metrics` | Daily aggregates for trend chart |
| `monitoring.task_performance_stats` | P50/P95/P99 per task type for SLO tracking |
| `monitoring.data_quality_summary` | Last 7 days of test results |
| `monitoring.recent_errors` | Last 50 failures for error feed |
| `monitoring.pipeline_table_sizes` | PostgreSQL table size monitoring |

### Filters

- **Date range** (global): filter all charts by `run_date`
- **Pipeline name** (dropdown): narrow to `etl_ingest` or `airflow_ecommerce_pipeline`
- **Task type** (dropdown): filter task performance by type

---

## Best Practices

### Audit table hygiene

- `etl_task_runs` has `ON DELETE CASCADE` from `etl_runs` — purging old
  pipeline runs automatically cleans up task data
- `data_quality_results` uses `ON DELETE SET NULL` — test results are
  preserved even if the pipeline run is purged
- Index on `started_at DESC` enables fast "last N runs" queries

### When to use PipelineLogger vs. Airflow on_failure_callback

| Scenario | Use |
|---|---|
| Standalone ETL (`python -m etl.ingest`) | `PipelineLogger` directly |
| Airflow PythonOperator | `PipelineLogger` inside the callable |
| Airflow BashOperator (dbt_run) | `ingest_dbt_test_results` after the task |
| All Airflow tasks uniformly | `on_success_callback` / `on_failure_callback` at DAG level (future enhancement) |

### Performance considerations

- `PipelineLogger` opens a dedicated PostgreSQL connection per run — fine for
  daily pipeline cadence
- `autocommit = True` ensures each INSERT/UPDATE is immediately visible
- Monitoring writes are not wrapped in the ETL transaction — they survive
  pipeline rollbacks
- Parsing `run_results.json` is fast (<50ms for 100+ tests)

### Future enhancements

- **Prometheus + Grafana**: Export `duration_seconds` and `rows_processed` as
  metrics for real-time alerting
- **dbt artifacts**: Parse `sources.json` and `catalog.json` for freshness and
  lineage tracking
- **SLA SLO tracking**: Store target duration thresholds per task type and
  alert on breaches
- **Log aggregation**: Ship Python + dbt logs to ELK or Loki for centralized
  search
