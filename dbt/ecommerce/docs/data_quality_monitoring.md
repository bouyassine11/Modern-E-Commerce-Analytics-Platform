# Data Quality Monitoring Framework

## 1. Test Suite Overview

| Layer | Generic Tests | Singular Tests | Total |
|---|---|---|---|
| Sources | 0 (freshness via filter) | 0 | 0 |
| Staging (5 models) | 26 | 0 | 26 |
| Intermediate (1 model) | 10 | 0 | 10 |
| Warehouse (4 models) | 26 | 7 | 33 |
| **Total** | **62** | **7** | **69** |

## 2. Test Categories

### Unique Tests (`unique`)
| Model | Column | What it catches |
|---|---|---|
| stg_customers | customer_id, email | Duplicate customer records |
| stg_products | product_id | Duplicate products |
| stg_orders | order_id | Duplicate orders |
| stg_order_items | order_item_id | Duplicate line items |
| stg_payments | payment_id, transaction_id | Duplicate payments |
| int_orders_enriched | (order_id, product_id) | Grain violations |
| dim_customer | customer_key, customer_id | SCD key corruption |
| dim_product | product_key, product_id | Dimension key corruption |
| dim_date | date_key, full_date | Date spine gaps |
| fact_sales | sales_key, order_item_id | Fact duplication |

### Not Null Tests (`not_null`)
Applied to all surrogate keys, business keys, FKs, and critical business measures (total_amount, quantity, unit_price, email, status, etc.).

### Relationship Tests (`relationships`)
| Source | Target | FK |
|---|---|---|
| stg_orders | stg_customers | customer_id |
| stg_order_items | stg_orders | order_id |
| stg_order_items | stg_products | product_id |
| stg_payments | stg_orders | order_id |
| fact_sales | dim_customer | customer_key |
| fact_sales | dim_product | product_key |
| fact_sales | dim_date | date_key |

### Accepted Values Tests
| Model | Column | Valid Values |
|---|---|---|
| stg_customers | status | active, inactive, suspended |
| stg_products | category | 8 product categories |
| stg_orders | status | pending, processing, shipped, delivered, cancelled, refunded |
| stg_orders | payment_method | credit_card, paypal, stripe, bank_transfer |
| stg_payments | status | pending, completed, failed, refunded |
| stg_payments | payment_method | credit_card, paypal, stripe, bank_transfer |
| int_orders_enriched | payment_method | credit_card, paypal, stripe, bank_transfer |
| int_orders_enriched | payment_status | completed, refunded, pending, failed |
| fact_sales | payment_status | paid, pending, failed, refunded |
| fact_sales | order_status | pending, processing, shipped, delivered, cancelled, refunded |

## 3. Singular Tests (Business Rules)

| Test | Purpose | Threshold |
|---|---|---|
| `assert_revenue_non_negative` | fact_sales.total_amount >= 0 | 0 tolerance |
| `assert_signup_before_order` | No orders before customer signup | 0 tolerance |
| `assert_no_future_orders` | No future-dated orders | 0 tolerance |
| `assert_order_item_total_matches` | total_price ≈ quantity × unit_price | ±0.01 tolerance |
| `assert_row_count_parity` | Staging ≤ raw row counts | <5% drop threshold |
| `assert_fact_references_valid_customers` | All fact customer_key exists in dim_customer | 0 tolerance |
| `assert_daily_revenue_consistency` | Daily revenue >= 0 for paid/pending orders | 0 tolerance |
| `assert_one_current_version_per_customer` | Each customer has exactly 1 current SCD version | 0 tolerance |

## 4. Run Strategy

| Trigger | Scope | Command |
|---|---|---|
| Daily pipeline | All models + sources | `dbt test` |
| Pre-deploy CI | Changed models only | `dbt test --select model_tag:staging` |
| On-call alert | Failed tests | `dbt test --select result:fail` |

## 5. Alerting Thresholds

| Severity | Condition | Action |
|---|---|---|
| Critical | Any `not_null`/`unique` failure | Block downstream, page on-call |
| Warning | Accepted values violation (>0.1% rows) | Log to audit, page if trend |
| Informational | Row count parity <5% drop | Log to audit, no page |
| Degraded | Relationship test failure (>0.1% orphaned) | Block fact refresh, page owner |

## 6. Dashboard Queries for Monitoring

### Row Count Trend (7-day)
```sql
select
    table_name,
    row_count,
    lag(row_count) over (partition by table_name order by run_date) as prev_count,
    row_count - lag(row_count) over (partition by table_name order by run_date) as delta
from pipeline_audit_log
where run_date >= current_date - 7
order by table_name, run_date desc;
```

### Test Failure Rate
```sql
select
    test_name,
    count(*) as total_runs,
    sum(case when status = 'fail' then 1 else 0 end) as failures,
    round(100.0 * sum(case when status = 'fail' then 1 else 0 end) / count(*), 1) as fail_rate
from dbt_test_results
group by test_name
having fail_rate > 5.0
order by fail_rate desc;
```

### Referential Integrity Health
```sql
select
    'fact_sales → dim_customer' as relationship,
    count(*) as fact_rows,
    count(distinct customer_key) as distinct_fk,
    count(*) filter (where customer_key not in (select customer_key from dim_customer)) as orphans
from fact_sales;
```

## 7. Known Gaps

| Gap | Impact | Mitigation |
|---|---|---|
| Raw tables lack `_etl_loaded_at` | Cannot run column-based source freshness | Use `assert_row_count_parity` as freshness proxy |
| Payment gateway reconciliation | Cannot verify external payment accuracy | Manual spot-check + anomaly detection |
| Real-time latency | Incremental model has ~1 run latency | Daily schedule sufficient for current SLA |
| Cross-source dedup | No global customer identity resolution | Out of scope for v1; document for Phase 2 |
