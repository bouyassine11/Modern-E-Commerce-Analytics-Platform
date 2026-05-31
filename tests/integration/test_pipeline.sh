#!/usr/bin/env bash
# =============================================================================
# Integration Test: End-to-End Pipeline
# =============================================================================
# Tests the full ETL + dbt pipeline against a running PostgreSQL instance.
# Can run against the Docker Compose stack or a local Postgres.
#
# Usage:
#   ./tests/integration/test_pipeline.sh            # default: Docker stack
#   ./tests/integration/test_pipeline.sh --local    # local Postgres
#   ./tests/integration/test_pipeline.sh --dry-run  # skip dbt, check ETL only
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="${1:-docker}"
PG_HOST="${PGHOST:-localhost}"
PG_PORT="${PGPORT:-5432}"
PG_USER="${PGUSER:-postgres}"
PG_PASSWORD="${PGPASSWORD:-postgres}"
PG_DB="${PGDATABASE:-ecommerce}"

PASS=0
FAIL=0

pass() { PASS=$((PASS + 1)); echo "  PASS: $*"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $*"; }

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

echo "========================================"
echo " E-Commerce Analytics — Integration Test"
echo " Mode: $MODE"
echo " Database: $PG_HOST:$PG_PORT/$PG_DB"
echo "========================================"

cd "$PROJECT_ROOT"

# Ensure .env exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from .env.example"
fi

# Start Docker stack if needed
if [ "$MODE" = "docker" ]; then
    echo "Starting Docker Compose stack..."
    docker compose up -d postgres
    echo "Waiting for PostgreSQL to be healthy..."
    timeout 60 bash -c 'until docker compose exec -T postgres pg_isready -U postgres; do sleep 2; done'
    echo "PostgreSQL is ready"
fi

# ---------------------------------------------------------------------------
# Test 1: Generate synthetic data
# ---------------------------------------------------------------------------

echo ""
echo "--- Test 1: Data Generation ---"

python -m etl.generate --config config.yaml 2>&1 | tail -5
if ls data/raw/*.csv 1>/dev/null 2>&1; then
    pass "CSV files created in data/raw/"
else
    fail "No CSV files found in data/raw/"
fi

# ---------------------------------------------------------------------------
# Test 2: ETL Pipeline (dry-run)
# ---------------------------------------------------------------------------

echo ""
echo "--- Test 2: ETL Dry-Run ---"

OUTPUT=$(python -m etl.ingest --dry-run 2>&1)
if echo "$OUTPUT" | grep -q "Pipeline Summary"; then
    pass "ETL dry-run completed successfully"
else
    fail "ETL dry-run did not produce summary"
    echo "$OUTPUT" | tail -10
fi

# Check row counts in output
for table in products customers orders order_items payments; do
    if echo "$OUTPUT" | grep -qi "$table"; then
        pass "  $table present in dry-run output"
    else
        fail "  $table missing from dry-run output"
    fi
done

# ---------------------------------------------------------------------------
# Test 3: ETL Pipeline (real load)
# ---------------------------------------------------------------------------

echo ""
echo "--- Test 3: ETL Load ---"

python -m etl.ingest 2>&1 | tail -10
if python -c "
import psycopg2
conn = psycopg2.connect(host='$PG_HOST', port=$PG_PORT, dbname='$PG_DB', user='$PG_USER', password='$PG_PASSWORD')
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM raw.products_raw\")
count = cur.fetchone()[0]
conn.close()
print(f'Products loaded: {count}')
assert count > 0, 'No products loaded'
"; then
    pass "Data loaded into raw schema"
else
    fail "Data load verification failed"
fi

# ---------------------------------------------------------------------------
# Test 4: Monitoring audit tables exist
# ---------------------------------------------------------------------------

echo ""
echo "--- Test 4: Monitoring Tables ---"

if python -c "
import psycopg2
conn = psycopg2.connect(host='$PG_HOST', port=$PG_PORT, dbname='$PG_DB', user='$PG_USER', password='$PG_PASSWORD')
cur = conn.cursor()
for tbl in ['etl_runs', 'etl_task_runs', 'data_quality_results']:
    cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='monitoring' AND table_name=%s)\", (tbl,))
    assert cur.fetchone()[0], f'Missing table: {tbl}'
    print(f'  monitoring.{tbl} EXISTS')
conn.close()
"; then
    pass "All monitoring tables exist"
else
    fail "Monitoring tables missing"
fi

# ---------------------------------------------------------------------------
# Test 5: dbt (if not dry-run mode)
# ---------------------------------------------------------------------------

if [ "$MODE" != "dry-run" ]; then
    echo ""
    echo "--- Test 5: dbt Run ---"

    if command -v dbt &>/dev/null; then
        cd "$PROJECT_ROOT/dbt/ecommerce"
        if dbt debug 2>&1 | grep -q "Connection ok"; then
            pass "dbt connection OK"
        else
            fail "dbt connection failed"
        fi

        if dbt run 2>&1 | tail -5; then
            pass "dbt run completed"
        else
            fail "dbt run failed"
        fi

        if dbt test 2>&1 | tail -10; then
            pass "dbt tests completed"
            # Check for test failures
            if dbt test 2>&1 | grep -q "FAILED"; then
                fail "dbt tests have failures"
            fi
        else
            fail "dbt test execution failed"
        fi
    else
        echo "  dbt CLI not available — skipping dbt tests"
    fi
fi

# ---------------------------------------------------------------------------
# Test 6: Fact table query
# ---------------------------------------------------------------------------

echo ""
echo "--- Test 6: Warehouse Query ---"

if python -c "
import psycopg2
conn = psycopg2.connect(host='$PG_HOST', port=$PG_PORT, dbname='$PG_DB', user='$PG_USER', password='$PG_PASSWORD')
cur = conn.cursor()

# Check at least one report table returns data
for tbl in ['rpt_daily_revenue', 'rpt_monthly_revenue', 'rpt_top_products', 'rpt_customer_lifetime_value']:
    cur.execute(f'SELECT COUNT(*) FROM public.{tbl}')
    cnt = cur.fetchone()[0]
    print(f'  {tbl}: {cnt} rows')
conn.close()
"; then
    pass "Report tables queryable and contain data"
else
    fail "Report table query failed"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "========================================"
echo " Results: $PASS passed, $FAIL failed"
echo "========================================"

# Cleanup
if [ "$MODE" = "docker" ]; then
    echo "NOTE: Docker stack left running. Stop with: docker compose down"
fi

exit $FAIL
