-- Monitoring & Observability Schema
-- Tracks pipeline execution, task-level metrics, and dbt data quality results.

CREATE SCHEMA IF NOT EXISTS monitoring;

-- ---------------------------------------------------------------------------
-- etl_runs — one row per pipeline execution
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS monitoring.etl_runs (
    run_id              SERIAL PRIMARY KEY,
    pipeline_name       TEXT NOT NULL,
    dag_run_id          TEXT,
    status              TEXT NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'completed', 'failed')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    duration_seconds    NUMERIC(10,2),
    rows_generated      INTEGER,
    rows_extracted      INTEGER,
    rows_loaded         INTEGER,
    error_message       TEXT,
    metadata            JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_status     ON monitoring.etl_runs(status);
CREATE INDEX IF NOT EXISTS idx_etl_runs_started    ON monitoring.etl_runs(started_at DESC);

-- ---------------------------------------------------------------------------
-- etl_task_runs — one row per task execution within a pipeline
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS monitoring.etl_task_runs (
    task_run_id         SERIAL PRIMARY KEY,
    run_id              INTEGER NOT NULL REFERENCES monitoring.etl_runs(run_id) ON DELETE CASCADE,
    task_name           TEXT NOT NULL,
    task_type           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'completed', 'failed')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    duration_seconds    NUMERIC(10,2),
    rows_processed      INTEGER,
    records_before      INTEGER,
    records_after       INTEGER,
    records_removed     INTEGER,
    error_message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_etl_task_runs_run_id ON monitoring.etl_task_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_etl_task_runs_type   ON monitoring.etl_task_runs(task_type);

-- ---------------------------------------------------------------------------
-- data_quality_results — one row per dbt test execution
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS monitoring.data_quality_results (
    result_id               SERIAL PRIMARY KEY,
    run_id                  INTEGER REFERENCES monitoring.etl_runs(run_id) ON DELETE SET NULL,
    test_execution_id       TEXT,
    test_name               TEXT NOT NULL,
    model_name              TEXT,
    column_name             TEXT,
    severity                TEXT NOT NULL CHECK (severity IN ('error', 'warn')),
    status                  TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'skipped')),
    failures                INTEGER NOT NULL DEFAULT 0,
    execution_time_seconds  NUMERIC(10,3),
    test_query              TEXT,
    tested_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dq_results_run_id  ON monitoring.data_quality_results(run_id);
CREATE INDEX IF NOT EXISTS idx_dq_results_status  ON monitoring.data_quality_results(status);
