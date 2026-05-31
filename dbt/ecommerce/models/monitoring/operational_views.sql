-- Operational Monitoring Dashboard Views
-- These views power the Ops Dashboard in Metabase and provide quick SQL access
-- for ad-hoc observability queries.

-- ---------------------------------------------------------------------------
-- pipeline_latest_runs — last 30 pipeline executions with status & duration
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.pipeline_latest_runs AS
SELECT
    run_id,
    pipeline_name,
    dag_run_id,
    status,
    started_at,
    completed_at,
    duration_seconds,
    rows_generated,
    rows_extracted,
    rows_loaded,
    error_message,
    metadata ->> 'kpi_snapshot' AS kpi_snapshot_json
FROM monitoring.etl_runs
ORDER BY started_at DESC
LIMIT 30;

-- ---------------------------------------------------------------------------
-- pipeline_daily_metrics — daily aggregates of pipeline health
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.pipeline_daily_metrics AS
SELECT
    DATE(started_at) AS run_date,
    pipeline_name,
    COUNT(*)                                          AS total_runs,
    COUNT(*) FILTER (WHERE status = 'completed')      AS successful_runs,
    COUNT(*) FILTER (WHERE status = 'failed')         AS failed_runs,
    ROUND(AVG(duration_seconds) FILTER (WHERE status = 'completed'), 2)
                                                      AS avg_duration_sec,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_seconds)
          FILTER (WHERE status = 'completed'), 2)     AS p50_duration_sec,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_seconds)
          FILTER (WHERE status = 'completed'), 2)     AS p95_duration_sec,
    SUM(rows_extracted)                               AS total_rows_extracted,
    SUM(rows_loaded)                                  AS total_rows_loaded
FROM monitoring.etl_runs
GROUP BY DATE(started_at), pipeline_name
ORDER BY run_date DESC;

-- ---------------------------------------------------------------------------
-- task_performance_stats — duration percentiles by task type
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.task_performance_stats AS
SELECT
    task_type,
    COUNT(*)                                          AS total_executions,
    COUNT(*) FILTER (WHERE status = 'failed')         AS failures,
    ROUND(AVG(duration_seconds) FILTER (WHERE status = 'completed'), 2)
                                                      AS avg_duration_sec,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_seconds)
          FILTER (WHERE status = 'completed'), 2)     AS p50_duration_sec,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_seconds)
          FILTER (WHERE status = 'completed'), 2)     AS p95_duration_sec,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_seconds)
          FILTER (WHERE status = 'completed'), 2)     AS p99_duration_sec,
    SUM(rows_processed)                               AS total_rows_processed,
    SUM(records_removed)                              AS total_records_removed
FROM monitoring.etl_task_runs
WHERE started_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY task_type
ORDER BY avg_duration_sec DESC;

-- ---------------------------------------------------------------------------
-- data_quality_summary — recent test failures for alerting
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.data_quality_summary AS
SELECT
    dqr.result_id,
    dqr.run_id,
    dqr.test_name,
    dqr.model_name,
    dqr.column_name,
    dqr.severity,
    dqr.status,
    dqr.failures,
    dqr.execution_time_seconds,
    dqr.tested_at,
    er.status AS pipeline_status
FROM monitoring.data_quality_results dqr
LEFT JOIN monitoring.etl_runs er ON dqr.run_id = er.run_id
WHERE dqr.tested_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY dqr.tested_at DESC;

-- ---------------------------------------------------------------------------
-- recent_errors — last 50 pipeline or task failures
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.recent_errors AS
SELECT
    started_at,
    'pipeline' AS source,
    pipeline_name AS name,
    status,
    error_message
FROM monitoring.etl_runs
WHERE status = 'failed'
UNION ALL
SELECT
    tr.started_at,
    'task' AS source,
    tr.task_name AS name,
    tr.status,
    tr.error_message
FROM monitoring.etl_task_runs tr
WHERE tr.status = 'failed'
ORDER BY started_at DESC
LIMIT 50;

-- ---------------------------------------------------------------------------
-- pipeline_table_sizes — PostgreSQL table size monitoring
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW monitoring.pipeline_table_sizes AS
SELECT
    schemaname || '.' || tablename AS full_table_name,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
    pg_total_relation_size(schemaname || '.' || tablename) AS total_size_bytes,
    n_live_tup AS row_count_estimate,
    last_analyze,
    last_autoanalyze
FROM pg_catalog.pg_stat_all_tables
WHERE schemaname IN ('raw', 'staging', 'dw', 'monitoring')
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
