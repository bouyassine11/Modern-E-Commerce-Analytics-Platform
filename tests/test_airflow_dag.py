"""Validate the Airflow DAG compiles and has the expected structure.

These tests run without a running Airflow instance by importing the DAG file
directly. They verify:
  - The DAG is importable and recognised by Airflow
  - All expected tasks exist
  - Task dependencies form a DAG (no cycles)
  - Module-level Variable.get() calls are handled safely
"""

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _airflow_variables():
    """Mock all Airflow Variable.get calls to prevent DB access."""
    with patch("airflow.models.Variable.get") as mock_get:
        mock_get.return_value = ""
        yield mock_get


@pytest.fixture(autouse=True)
def _patch_etl_imports():
    """Ensure the DAG can find the etl package in tests directory context."""
    import sys
    etl_path = str(Path(__file__).resolve().parent.parent / "etl")
    if etl_path not in sys.path:
        sys.path.insert(0, etl_path)
    yield


class TestDagImports:
    def test_dag_file_importable(self):
        """The DAG module should import without errors."""
        import importlib
        mod = importlib.import_module("airflow.dags.ecommerce_pipeline")
        assert mod is not None

    def test_dag_object_exists(self):
        from airflow.dags.ecommerce_pipeline import dag
        assert dag is not None
        assert dag.dag_id == "ecommerce_analytics_pipeline"

    def test_dag_schedule(self):
        from airflow.dags.ecommerce_pipeline import dag
        assert dag.schedule is not None

    def test_dag_default_args(self):
        from airflow.dags.ecommerce_pipeline import dag
        assert dag.default_args is not None
        assert dag.default_args.get("owner") == "data_engineering"
        assert dag.default_args.get("retries") == 2


class TestDagTasks:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from airflow.dags.ecommerce_pipeline import dag
        self.dag = dag

    def test_all_required_tasks_exist(self):
        task_ids = [t.task_id for t in self.dag.tasks]
        assert "start_pipeline_run" in task_ids
        assert "generate_data" in task_ids
        assert "extract_data" in task_ids
        assert "transform_data" in task_ids
        assert "load_raw_tables" in task_ids
        assert "dbt_run" in task_ids
        assert "dbt_test" in task_ids
        assert "ingest_dbt_test_results" in task_ids
        assert "refresh_metabase" in task_ids
        assert "generate_kpi_report" in task_ids
        assert "complete_pipeline_run" in task_ids

    def test_task_count(self):
        # At minimum: 11 core tasks (+ possibly dbt_seed)
        assert len(self.dag.tasks) >= 11

    def test_downstream_chain(self):
        start = self.dag.get_task("start_pipeline_run")
        generate = self.dag.get_task("generate_data")
        assert generate in start.downstream_list

        load = self.dag.get_task("load_raw_tables")
        dbt_run = self.dag.get_task("dbt_run")
        assert dbt_run in load.downstream_list

    def test_no_orphan_tasks(self):
        """Every task should be reachable from start_pipeline_run or complete_pipeline_run."""
        all_tasks = set(self.dag.task_ids)
        upstream = set()
        downstream = set()
        for t in self.dag.tasks:
            upstream.update(u.task_id for u in t.upstream_list)
            downstream.update(d.task_id for d in t.downstream_list)
        reachable = upstream | downstream | {"start_pipeline_run", "complete_pipeline_run"}
        assert all_tasks == reachable, f"Orphan tasks: {all_tasks - reachable}"

    def test_dag_has_no_cycles(self):
        """Airflow's topological sort ensures a DAG has no cycles. If it passes, we trust it."""
        from airflow.dags.ecommerce_pipeline import dag
        # Topological sort raises on cycles
        ordered = dag.topological_sort()
        assert len(ordered) == len(dag.tasks)
