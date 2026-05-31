import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

_MONITORING_SCHEMA_DDL = Path(__file__).resolve().parent.parent / "docker" / "postgres" / "init" / "03_monitoring.sql"


class PipelineLogger:
    """Audit-log pipeline executions, task-level metrics, and dbt quality results.

    Opens one dedicated connection per pipeline run and manages the full lifecycle:
    start → task(s) → complete.  All INSERT/UPDATE statements use the monitoring
    schema in the target database.
    """

    def __init__(self, db_config: dict, schema: str = "monitoring"):
        self.db_config = db_config
        self.schema = schema
        self.conn: Optional[psycopg2.extensions.connection] = None
        self._run_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> "PipelineLogger":
        self.conn = psycopg2.connect(
            host=self.db_config["host"],
            port=self.db_config["port"],
            dbname=self.db_config["dbname"],
            user=self.db_config["user"],
            password=self.db_config["password"],
        )
        self.conn.autocommit = True
        self._ensure_schema()
        self._ensure_tables()
        return self

    def close(self) -> None:
        if self.conn and not self.conn.closed:
            self.conn.close()
            logger.debug("Monitoring connection closed")

    def __enter__(self) -> "PipelineLogger":
        return self.connect()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")

    def _ensure_tables(self) -> None:
        if _MONITORING_SCHEMA_DDL.exists():
            ddl = _MONITORING_SCHEMA_DDL.read_text()
            with self.conn.cursor() as cur:
                cur.execute(ddl)
            logger.info("Monitoring schema & tables ensured")
        else:
            logger.warning("Monitoring DDL not found at %s — tables may not exist", _MONITORING_SCHEMA_DDL)

    # ------------------------------------------------------------------
    # Pipeline run lifecycle
    # ------------------------------------------------------------------

    @property
    def run_id(self) -> Optional[int]:
        return self._run_id

    def start_run(
        self,
        pipeline_name: str,
        dag_run_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.etl_runs
                    (pipeline_name, dag_run_id, status, started_at, metadata)
                VALUES (%s, %s, 'running', %s, %s)
                RETURNING run_id
                """,
                (pipeline_name, dag_run_id, datetime.now(timezone.utc), json.dumps(metadata or {})),
            )
            self._run_id = cur.fetchone()[0]
        logger.info("Pipeline run %s started (run_id=%s)", pipeline_name, self._run_id)
        return self._run_id

    def complete_run(
        self,
        status: str = "completed",
        error_message: Optional[str] = None,
        rows_generated: Optional[int] = None,
        rows_extracted: Optional[int] = None,
        rows_loaded: Optional[int] = None,
    ) -> None:
        if self._run_id is None:
            raise RuntimeError("No active run to complete")
        completed_at = datetime.now(timezone.utc)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self.schema}.etl_runs
                SET status = %s,
                    completed_at = %s,
                    duration_seconds = EXTRACT(EPOCH FROM %s - started_at),
                    rows_generated = COALESCE(%s, rows_generated),
                    rows_extracted = COALESCE(%s, rows_extracted),
                    rows_loaded = COALESCE(%s, rows_loaded),
                    error_message = %s
                WHERE run_id = %s
                """,
                (status, completed_at, completed_at,
                 rows_generated, rows_extracted, rows_loaded,
                 error_message, self._run_id),
            )
        logger.info("Pipeline run %s completed (%s)", self._run_id, status)

    def fail_run(self, error_message: str, **kwargs: Any) -> None:
        self.complete_run(status="failed", error_message=error_message, **kwargs)

    # ------------------------------------------------------------------
    # Task lifecycle
    # ------------------------------------------------------------------

    def start_task(
        self,
        task_name: str,
        task_type: str,
        records_before: Optional[int] = None,
    ) -> int:
        if self._run_id is None:
            raise RuntimeError("No active run — call start_run() first")
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.etl_task_runs
                    (run_id, task_name, task_type, status, started_at, records_before)
                VALUES (%s, %s, %s, 'running', %s, %s)
                RETURNING task_run_id
                """,
                (self._run_id, task_name, task_type, datetime.now(timezone.utc), records_before),
            )
            task_run_id = cur.fetchone()[0]
        return task_run_id

    def complete_task(
        self,
        task_run_id: int,
        status: str = "completed",
        rows_processed: Optional[int] = None,
        records_after: Optional[int] = None,
        records_removed: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        completed_at = datetime.now(timezone.utc)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self.schema}.etl_task_runs
                SET status = %s,
                    completed_at = %s,
                    duration_seconds = EXTRACT(EPOCH FROM %s - started_at),
                    rows_processed = %s,
                    records_after = %s,
                    records_removed = %s,
                    error_message = %s
                WHERE task_run_id = %s
                """,
                (status, completed_at, completed_at,
                 rows_processed, records_after, records_removed,
                 error_message, task_run_id),
            )

    def fail_task(self, task_run_id: int, error_message: str, **kwargs: Any) -> None:
        self.complete_task(task_run_id, status="failed", error_message=error_message, **kwargs)

    # ------------------------------------------------------------------
    # dbt data quality results
    # ------------------------------------------------------------------

    def ingest_dbt_results(self, run_results_path: str) -> int:
        """Parse dbt run_results.json and insert rows into data_quality_results.

        Returns the number of results ingested.
        """
        path = Path(run_results_path)
        if not path.exists():
            logger.warning("dbt run_results.json not found at %s", run_results_path)
            return 0

        with open(path) as f:
            run_results = json.load(f)

        count = 0
        for result in run_results.get("results", []):
            if result.get("node", {}).get("resource_type") != "test":
                continue

            node = result["node"]
            count += self._insert_dq_result(result, node)

        logger.info("Ingested %d dbt test results", count)
        return count

    def _insert_dq_result(self, result: dict, node: dict) -> int:
        test_name = node.get("name", "unknown")
        model_name = None
        column_name = None

        depends_on = node.get("depends_on", {})
        nodes = depends_on.get("nodes", [])
        if nodes:
            model_name = nodes[0]

        tags = node.get("tags", [])
        severity = "error" if node.get("config", {}).get("severity", "error") == "error" else "warn"

        test_query = node.get("compiled_sql") or node.get("raw_sql")

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.data_quality_results
                    (run_id, test_execution_id, test_name, model_name, column_name,
                     severity, status, failures, execution_time_seconds, test_query)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self._run_id,
                    result.get("unique_id"),
                    test_name,
                    model_name,
                    column_name,
                    severity,
                    "pass" if result.get("status") == "pass" else "fail",
                    result.get("failures", 0),
                    result.get("execution_time", 0),
                    test_query,
                ),
            )
        return 1

    # ------------------------------------------------------------------
    # KPI metrics snapshot
    # ------------------------------------------------------------------

    def snapshot_kpis(self, kpi_data: dict) -> None:
        """Store a KPI snapshot as JSONB metadata on the current run."""
        if self._run_id is None:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {self.schema}.etl_runs
                SET metadata = metadata || %s::jsonb
                WHERE run_id = %s
                """,
                (json.dumps({"kpi_snapshot": kpi_data}), self._run_id),
            )

    # ------------------------------------------------------------------
    # Convenience helpers for ETL task wrappers
    # ------------------------------------------------------------------

    @contextmanager
    def task_context(self, task_name: str, task_type: str, **initial: Any):
        """Context manager that auto-creates and completes a task run."""
        task_run_id = self.start_task(task_name, task_type, **initial)
        try:
            yield task_run_id
            self.complete_task(task_run_id, status="completed")
        except Exception as exc:
            self.fail_task(task_run_id, error_message=str(exc))
            raise
