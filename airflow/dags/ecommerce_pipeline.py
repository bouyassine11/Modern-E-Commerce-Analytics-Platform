"""
E-Commerce Analytics Pipeline

Orchestrates:
  1. generate_data      — generate synthetic e-commerce CSV data
  2. extract_data       — validate CSV files exist and report stats
  3. transform_data     — clean, deduplicate, normalize, validate FKs
  4. load_raw_tables    — bulk-load cleaned data into PostgreSQL raw schema
  5. dbt_seed (opt)     — load dbt seed files (optional, controlled by Variable)
  6. dbt_run            — execute dbt models (staging → warehouse → marts)
  7. dbt_test           — run dbt data quality tests
  8. refresh_metabase   — trigger Metabase schema sync via API
  9. generate_kpi_report— query warehouse and log KPI summary
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow/etl")

logger = logging.getLogger("ecommerce_pipeline")


# ---------------------------------------------------------------------------
# Lazy configuration from Airflow Variables (with file-based fallbacks)
# ---------------------------------------------------------------------------

def _var(name: str, default: str) -> str:
    try:
        return Variable.get(name, default_var=default)
    except Exception:
        return default


CONFIG_PATH = _var("config_path", "/opt/airflow/etl/../config.yaml")
DBT_PROJECT_DIR = _var("dbt_project_dir", "/opt/airflow/dbt/ecommerce")
DBT_PROFILES_DIR = _var("dbt_profiles_dir", "/opt/airflow/dbt/ecommerce")
CLEAN_DATA_DIR = _var("clean_data_dir", "/data/processed/cleaned")
METABASE_URL = _var("metabase_url", "http://metabase:3000")
DBT_SEED_ENABLED = _var("dbt_seed_enabled", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------------------

default_args = {
    "owner": "data_engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email": ["admin@ecommerce.com"],
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

dag = DAG(
    dag_id="ecommerce_analytics_pipeline",
    default_args=default_args,
    description="End-to-end e-commerce analytics pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["ecommerce", "analytics", "dbt", "etl"],
    max_active_runs=1,
    doc_md=__doc__,
)

# ---------------------------------------------------------------------------
# Python callables for each task
# ---------------------------------------------------------------------------


def _generate_data(**context: Any) -> dict[str, int]:
    """Generate synthetic e-commerce CSV files."""
    from etl.config import load_config
    from etl.generators.customer_generator import generate_customers
    from etl.generators.order_generator import generate_orders
    from etl.generators.order_item_generator import generate_order_items
    from etl.generators.payment_generator import generate_payments
    from etl.generators.product_generator import generate_products
    from etl.utils import write_csv

    config = load_config(CONFIG_PATH)
    output_dir = config["data"]["output_dir"]

    products = generate_products(config)
    customers = generate_customers(config)
    orders = generate_orders(config, customers)
    order_items, order_totals = generate_order_items(config, orders, products)

    for order in orders:
        order["total_amount"] = order_totals[order["order_id"]]

    payments = generate_payments(config, orders, order_totals)

    datasets = [
        ("products", products),
        ("customers", customers),
        ("orders", orders),
        ("order_items", order_items),
        ("payments", payments),
    ]

    counts: dict[str, int] = {}
    for name, data in datasets:
        write_csv(f"{name}.csv", data, output_dir)
        counts[name] = len(data)

    context["ti"].xcom_push(key="generated_counts", value=counts)
    logger.info("Generated data: %s", counts)
    return counts


def _extract_data(**context: Any) -> dict[str, int]:
    """Validate that all source CSV files exist and report row counts."""
    from etl.config import load_config
    from etl.extract import Extractor

    config = load_config(CONFIG_PATH)
    extractor = Extractor(config)

    row_counts: dict[str, int] = {}
    for table_name in extractor.file_map:
        rows = extractor.extract(table_name)
        row_counts[table_name] = len(rows)

    context["ti"].xcom_push(key="raw_counts", value=row_counts)
    logger.info("Extracted rows: %s", row_counts)
    return row_counts


def _transform_data(**context: Any) -> dict[str, int]:
    """Clean, deduplicate, normalise, and validate data."""
    from etl.config import load_config
    from etl.extract import Extractor
    from etl.transform import Transformer
    from etl.utils import write_csv

    config = load_config(CONFIG_PATH)
    extractor = Extractor(config)
    transformer = Transformer(config)

    raw_data = extractor.extract_all()
    clean_data = transformer.transform_all(raw_data)

    Path(CLEAN_DATA_DIR).mkdir(parents=True, exist_ok=True)

    clean_counts: dict[str, int] = {}
    for name, rows in clean_data.items():
        write_csv(f"{name}.csv", rows, CLEAN_DATA_DIR)
        clean_counts[name] = len(rows)

    context["ti"].xcom_push(key="clean_counts", value=clean_counts)
    logger.info("Transformed rows: %s", clean_counts)
    return clean_counts


def _load_raw_tables(**context: Any) -> dict[str, int]:
    """Bulk-load cleaned CSV data into PostgreSQL raw schema inside a transaction."""
    from etl.config import load_config
    from etl.load import Loader
    from etl.utils import get_connection, read_csv

    config = load_config(CONFIG_PATH)
    loader = Loader(config)

    clean_data: dict[str, list[dict]] = {}
    for name in ["products", "customers", "orders", "order_items", "payments"]:
        path = Path(CLEAN_DATA_DIR) / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Cleaned data not found: {path}")
        clean_data[name] = read_csv(path)

    conn = get_connection(config["database"])
    try:
        with conn:
            counts = loader.load_all(conn, clean_data)
    finally:
        conn.close()

    context["ti"].xcom_push(key="load_counts", value=counts)
    logger.info("Loaded rows: %s", counts)
    return counts


def _dbt_seed(**context: Any) -> None:
    """Run dbt seed (optional — skippable via Airflow Variable)."""
    import subprocess

    cmd = [
        "dbt",
        "seed",
        "--project-dir", DBT_PROJECT_DIR,
        "--profiles-dir", DBT_PROFILES_DIR,
    ]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("dbt seed failed:\n%s", result.stderr)
        raise RuntimeError(f"dbt seed exited {result.returncode}")
    logger.info("dbt seed output:\n%s", result.stdout)


def _refresh_metabase(**context: Any) -> None:
    """Trigger Metabase to re-sync its schema and refresh dashboards."""
    import requests

    session = requests.Session()
    session.verify = False

    resp = session.post(
        f"{METABASE_URL}/api/session",
        json={"username": Variable.get("mb_user", "admin@ecommerce.com"),
              "password": Variable.get("mb_password", "admin")},
    )
    resp.raise_for_status()
    token = resp.json()["id"]
    session.headers.update({"X-Metabase-Session": token})

    dbs = session.get(f"{METABASE_URL}/api/database").json()
    for db in dbs.get("data", []):
        if "ecommerce" in db.get("name", "").lower():
            sync = session.post(f"{METABASE_URL}/api/database/{db['id']}/sync")
            sync.raise_for_status()
            logger.info("Triggered Metabase sync for DB: %s (id=%s)", db["name"], db["id"])

    logger.info("Metabase refresh complete")


def _generate_kpi_report(**context: Any) -> dict[str, Any]:
    """Query the warehouse mart layer and produce a KPI summary."""
    import psycopg2
    from etl.config import load_config

    config = load_config(CONFIG_PATH)
    db = config["database"]
    conn = psycopg2.connect(
        host=db["host"], port=db["port"], dbname=db["dbname"],
        user=db["user"], password=db["password"],
    )

    kpis: dict[str, Any] = {}

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(DISTINCT customer_key) AS total_customers,
                           COUNT(DISTINCT product_key)  AS total_products
                    FROM dw.dim_customer, dw.dim_product
                """)
                row = cur.fetchone()
                kpis["dimensions"] = {"customers": row[0], "products": row[1]}

                cur.execute("""
                    SELECT COUNT(*)              AS total_orders,
                           COALESCE(SUM(total_amount), 0) AS total_revenue,
                           COALESCE(AVG(total_amount), 0)  AS avg_order_value
                    FROM dw.fact_sales
                """)
                row = cur.fetchone()
                kpis["sales"] = {
                    "orders": row[0],
                    "revenue": float(row[1]),
                    "avg_order_value": float(row[2]),
                }

                cur.execute("""
                    SELECT DATE(date_key) AS day, revenue
                    FROM (
                        SELECT date_key,
                               SUM(total_amount) AS revenue
                        FROM dw.fact_sales
                        GROUP BY date_key
                    ) sub
                    ORDER BY day DESC
                    LIMIT 7
                """)
                kpis["last_7_days"] = [
                    {"date": str(r[0]), "revenue": float(r[1])} for r in cur.fetchall()
                ]

    finally:
        conn.close()

    logger.info("=" * 60)
    logger.info("KPI Report")
    logger.info("=" * 60)
    logger.info("Dimensions: %s", kpis.get("dimensions"))
    logger.info("Sales:      %s", kpis.get("sales"))
    logger.info("Last 7d:    %s", kpis.get("last_7_days"))
    logger.info("=" * 60)

    context["ti"].xcom_push(key="kpi_report", value=kpis)
    return kpis


# ---------------------------------------------------------------------------
# DAG start / end markers
# ---------------------------------------------------------------------------

start = EmptyOperator(task_id="start", dag=dag)
end = EmptyOperator(task_id="end", dag=dag)

# ---------------------------------------------------------------------------
# Data pipeline tasks
# ---------------------------------------------------------------------------

generate_data = PythonOperator(
    task_id="generate_data",
    python_callable=_generate_data,
    dag=dag,
)

extract_data = PythonOperator(
    task_id="extract_data",
    python_callable=_extract_data,
    dag=dag,
)

transform_data = PythonOperator(
    task_id="transform_data",
    python_callable=_transform_data,
    dag=dag,
)

load_raw_tables = PythonOperator(
    task_id="load_raw_tables",
    python_callable=_load_raw_tables,
    dag=dag,
)

# ---------------------------------------------------------------------------
# dbt pipeline tasks
# ---------------------------------------------------------------------------

if DBT_SEED_ENABLED:
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=(
            f"dbt seed --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"
        ),
        env={
            "DBT_PROFILES_DIR": DBT_PROFILES_DIR,
            "POSTGRES_USER": "{{ var.value.get('postgres_user', 'postgres') }}",
            "POSTGRES_PASSWORD": "{{ var.value.get('postgres_password', 'postgres') }}",
            "POSTGRES_DB": "{{ var.value.get('postgres_db', 'ecommerce') }}",
        },
        trigger_rule="all_success",
        dag=dag,
    )

dbt_run = BashOperator(
    task_id="dbt_run",
    bash_command=(
        f"dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"
    ),
    env={
        "DBT_PROFILES_DIR": DBT_PROFILES_DIR,
        "POSTGRES_USER": "{{ var.value.get('postgres_user', 'postgres') }}",
        "POSTGRES_PASSWORD": "{{ var.value.get('postgres_password', 'postgres') }}",
        "POSTGRES_DB": "{{ var.value.get('postgres_db', 'ecommerce') }}",
    },
    dag=dag,
)

dbt_test = BashOperator(
    task_id="dbt_test",
    bash_command=(
        f"dbt test --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILES_DIR}"
    ),
    env={
        "DBT_PROFILES_DIR": DBT_PROFILES_DIR,
        "POSTGRES_USER": "{{ var.value.get('postgres_user', 'postgres') }}",
        "POSTGRES_PASSWORD": "{{ var.value.get('postgres_password', 'postgres') }}",
        "POSTGRES_DB": "{{ var.value.get('postgres_db', 'ecommerce') }}",
    },
    dag=dag,
)

# ---------------------------------------------------------------------------
# Reporting tasks
# ---------------------------------------------------------------------------

refresh_metabase = PythonOperator(
    task_id="refresh_metabase",
    python_callable=_refresh_metabase,
    dag=dag,
)

generate_kpi_report = PythonOperator(
    task_id="generate_kpi_report",
    python_callable=_generate_kpi_report,
    dag=dag,
)

# ---------------------------------------------------------------------------
# Task dependencies
# ---------------------------------------------------------------------------

start >> generate_data >> extract_data >> transform_data >> load_raw_tables

load_raw_tables >> dbt_run >> dbt_test
if DBT_SEED_ENABLED:
    dbt_seed >> dbt_run

dbt_test >> refresh_metabase >> generate_kpi_report >> end
