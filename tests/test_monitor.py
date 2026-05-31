from unittest.mock import MagicMock, patch

import pytest

from etl.monitor import PipelineLogger


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (1,)
    conn.cursor.return_value = cursor
    conn.closed = False
    return conn


@pytest.fixture
def logger(mock_conn):
    with patch("etl.monitor.psycopg2.connect", return_value=mock_conn):
        with PipelineLogger({"host": "localhost", "port": 5432, "dbname": "test", "user": "u", "password": "p"}) as log:
            yield log


class TestPipelineLogger:
    def test_start_run(self, logger, mock_conn):
        run_id = logger.start_run("test_pipeline")
        assert run_id == 1
        assert logger.run_id == 1
        mock_conn.cursor().execute.assert_called()

    def test_complete_run(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        logger.complete_run(rows_loaded=100)
        assert mock_conn.cursor().execute.call_count >= 2

    def test_fail_run(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        logger.fail_run("Something broke")
        calls = [c[0][0] for c in mock_conn.cursor().execute.call_args_list]
        assert any("status = 'failed'" in c or "failed" in c for c in str(calls))

    def test_start_task_needs_run(self, logger):
        with pytest.raises(RuntimeError, match="No active run"):
            logger.start_task("test_task", "extract")

    def test_task_lifecycle(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        mock_conn.cursor().fetchone.return_value = (42,)
        task_id = logger.start_task("extract_products", "extract")
        assert task_id == 42

        logger.complete_task(task_id, rows_processed=500)
        assert mock_conn.cursor().execute.call_count >= 3

    def test_fail_task(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        mock_conn.cursor().fetchone.return_value = (99,)
        task_id = logger.start_task("load_fail", "load")
        logger.fail_task(task_id, "Connection lost")

    def test_snapshot_kpis(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        logger.snapshot_kpis({"revenue": 1000, "orders": 50})
        calls = [c[0][0] for c in mock_conn.cursor().execute.call_args_list]
        assert any("kpi_snapshot" in c for c in str(calls))

    def test_task_context_manager_success(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        mock_conn.cursor().fetchone.return_value = (7,)
        with logger.task_context("my_task", "transform") as tid:
            assert tid == 7
        # Should have completed successfully
        calls = [c[0][0] for c in mock_conn.cursor().execute.call_args_list]
        assert any("completed" in c for c in str(calls))

    def test_task_context_manager_failure(self, logger, mock_conn):
        logger.start_run("test_pipeline")
        mock_conn.cursor().fetchone.return_value = (7,)
        with pytest.raises(ValueError, match="task failed"):
            with logger.task_context("failing_task", "transform"):
                raise ValueError("task failed")
        calls = [c[0][0] for c in mock_conn.cursor().execute.call_args_list]
        assert any("failed" in c for c in str(calls))

    def test_close_connection(self, logger, mock_conn):
        logger.close()
        mock_conn.close.assert_called_once()
