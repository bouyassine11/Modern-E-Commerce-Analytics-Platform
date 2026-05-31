# Metabase Dashboard Design

## Overview

Four dashboards providing progressive drill-down from executive overview to
product-level detail. All questions query pre-aggregated `rpt_*` tables in the
`dw` schema — no fact table scans at query time.

## Connection

- **Database**: PostgreSQL, target database `dw`, schema `public`
- **Tables used**: `rpt_daily_revenue`, `rpt_monthly_revenue`,
  `rpt_customer_lifetime_value`, `rpt_top_products`, `rpt_top_categories`,
  `rpt_country_revenue`, `rpt_repeat_customers`, `rpt_payment_analysis`

---

# Dashboard 1 — Executive Dashboard

**Business value**: Single-pane-of-glass health check for daily stand-ups and
executive reviews. Answers _"are we on track?"_ in under 5 seconds.

## Layout (4 columns, 3 rows)

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Total    │ │ Total    │ │ Total    │ │ Avg      │
│ Revenue  │ │ Orders   │ │ Customers│ │ Order    │
│          │ │          │ │          │ │ Value    │
├──────────┴─┴──────────┴─┴──────────┴─┴──────────┤
│            Revenue Trend (area)                   │
│            X: report_date  Y: total_revenue       │
│            Filter: last 12 months                 │
├───────────────────────────────────────────────────┤
│            Orders Trend (area)                     │
│            X: report_date  Y: total_orders         │
│            Series: total_orders, running_total     │
└───────────────────────────────────────────────────┘
```

## KPIs (card visualizations)

| KPI | Question | Source | Metabase Card Type |
|---|---|---|---|
| Total Revenue | `Sum(rpt_daily_revenue.total_revenue)` | `rpt_daily_revenue` | Scalar |
| Total Orders | `Sum(rpt_daily_revenue.total_orders)` | `rpt_daily_revenue` | Scalar |
| Total Customers | `Sum(rpt_daily_revenue.total_customers)` | `rpt_daily_revenue` | Scalar |
| Avg Order Value | `Sum(total_revenue) / Sum(total_orders)` | `rpt_daily_revenue` | Scalar |

## Charts

| Chart | Visualization | X-axis | Y-axis | Notes |
|---|---|---|---|---|
| Revenue Trend | Area (stacked) | `report_date` | `total_revenue` | Smooth curve, 90-day default filter |
| Orders Trend | Area (stacked) | `report_date` | `total_orders`, `running_total_orders` | Dual series, secondary Y-axis for running total |

## Filters

- **Date range** (single filter, global): `report_date` between `2024-01-01`
  and `2025-12-31`. Default = last 90 days.

## Drill-down

- Click any point on Revenue Trend → opens Sales Dashboard filtered to the
  selected week/month.

---

# Dashboard 2 — Sales Dashboard

**Business value**: Identifies revenue drivers and underperformers at
category, country, and product level. Guides merchandising and marketing
decisions.

## Layout (2 columns, 3 rows)

```
┌────────────────────────────────┬────────────────────────────────┐
│   Revenue by Category (bar)    │   Revenue by Country (bar)     │
│   X: category  Y: gross_rev    │   X: country   Y: total_rev   │
│   Series: revenue_share_pct    │   Series: revenue_share_pct   │
├────────────────────────────────┴────────────────────────────────┤
│   Revenue by Product (table — ranked)                          │
│   Columns: rank | product_name | category | gross_revenue     │
│            | total_units_sold | days_since_last_sale          │
│   Sorted by: revenue_rank asc                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Charts

| Chart | Visualization | X-axis | Y-axis | Source |
|---|---|---|---|---|
| Revenue by Category | Horizontal bar | `category` | `gross_revenue` | `rpt_top_categories` |
| Revenue by Country | Horizontal bar | `country` | `total_revenue` | `rpt_country_revenue` |
| Revenue by Product | Table + Trend | `product_name` | `gross_revenue` | `rpt_top_products` |

## Filters

- **Date range** — no date column at the aggregated level; filter applied at
  fact level if auto-drill-down
- **Category** (dropdown) — filters the Product table to selected category
- **Country** (dropdown) — narrows country bar + filters product table

## Drill-down

- Click category bar → opens Category Performance card on Product Dashboard
- Click country bar → opens Metabase filtered table of orders from that country
  (auto explore)
- Click product row → opens Product Revenue detail on Product Dashboard

---

# Dashboard 3 — Customer Dashboard

**Business value**: Tracks customer acquisition, retention, and lifetime value.
Enables RFM-based segmentation and targeted marketing campaigns.

## Layout (2 columns, 3 rows)

```
┌────────────────────────────────┬────────────────────────────────┐
│  Customer Growth (line)        │  Repeat Customers (bar/line)  │
│  X: report_month  Y: monthly  │  X: cohort_month Y: repeat    │
│  Series: new + repeat          │  Series: repeat_rate_pct     │
├────────────────────────────────┴────────────────────────────────┤
│  Customer Lifetime Value (combo bar + table)                    │
│  Left: bar chart — customer_segment × avg(total_revenue)       │
│  Right: table — Top 10 customers by total_revenue              │
└─────────────────────────────────────────────────────────────────┘
```

## Charts

| Chart | Visualization | Axis 1 | Axis 2 | Source |
|---|---|---|---|---|
| Customer Growth | Line (multi-series) | `monthly_new_customers` | `monthly_repeat_customers` | `rpt_repeat_customers` |
| Repeat Customers | Bar + trend line | `cohort_month` | `repeat_purchase_rate_pct` | `rpt_repeat_customers` |
| Customer LTV | Stacked bar | `customer_segment` | `count(*)`, `avg(total_revenue)` | `rpt_customer_lifetime_value` |

The Customer LTV chart uses a Metabase **Custom Expression** question:
```sql
select
  customer_segment,
  count(*)                as customer_count,
  avg(total_revenue)      as avg_ltv
from rpt_customer_lifetime_value
group by customer_segment
order by avg_ltv desc
```

## Filters

- **Customer segment** (multi-select dropdown) — filter LTV table to segment
- **Date range** — filters cohort_month on Repeat Customers chart

## Drill-down

- Click cohort bar → opens filtered LTV table of customers from that cohort
- Click segment bar → opens filtered customer table for that RFM segment
- Click top customer row → opens Metabase customer detail (auto explore)

---

# Dashboard 4 — Product Dashboard

**Business value**: Deep product and category analytics for inventory
management, pricing decisions, and category management.

## Layout (3 columns, 2 rows)

```
┌────────────────────────────┬────────────────────────────┬────────────────────────────┐
│ Top Products (bar)         │ Category Perf. (combo bar) │ Top Categories (pie)       │
│ X: product_name (top 20)   │ X: category   Y: revenue  │ X: category / revenue_pct  │
│ Y: gross_revenue           │ Series: revenue_per_order  │                            │
├────────────────────────────┴────────────────────────────┴────────────────────────────┤
│                        Product Detail Table                                         │
│ Columns: product_id | product_name | category | gross_revenue | total_units_sold   │
│          | current_price | avg_unit_price | days_since_last_sale                   │
│ Sorted by: revenue_rank asc                                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Charts

| Chart | Visualization | Axis 1 | Axis 2 | Source |
|---|---|---|---|---|
| Top Products | Horizontal bar (top 20) | `product_name` | `gross_revenue` | `rpt_top_products` |
| Category Performance | Combo bar + line | `category` | `gross_revenue` (bar), `revenue_per_order` (line) | `rpt_top_categories` |
| Top Categories | Pie / Donut | `category` | `revenue_share_pct` | `rpt_top_categories` |

The Top Products bar uses native query with a LIMIT 20:
```sql
select product_name, gross_revenue, revenue_rank
from rpt_top_products
order by revenue_rank
limit 20
```

The Category Performance combo chart uses:
```sql
select
  category,
  gross_revenue,
  revenue_per_order
from rpt_top_categories
order by gross_revenue desc
```

## Filters

- **Category** (dropdown, global) — filters all 3 charts + table to selected
  category
- **Active only** (toggle) — `days_since_last_sale <= 90`

## Drill-down

- Click product bar → opens filtered detail table for that product
- Click category bar → narrows Top Products + Detail Table to that category
- Click pie slice → same filter behavior as category bar

---

# Source Table Mapping

| Metabase Question | Source Table | Refresh Strategy |
|---|---|---|
| All Executive KPIs | `rpt_daily_revenue` | Daily (dbt run) |
| Revenue Trend | `rpt_daily_revenue` | Daily |
| Orders Trend | `rpt_daily_revenue` | Daily |
| Revenue by Category | `rpt_top_categories` | Daily |
| Revenue by Country | `rpt_country_revenue` | Daily |
| Revenue by Product | `rpt_top_products` | Daily |
| Customer Growth | `rpt_repeat_customers` | Daily |
| Repeat Customers | `rpt_repeat_customers` | Daily |
| Customer LTV | `rpt_customer_lifetime_value` | Daily |
| Top Products | `rpt_top_products` | Daily |
| Category Performance | `rpt_top_categories` | Daily |
| Product Detail Table | `rpt_top_products` | Daily |
| Top Categories Pie | `rpt_top_categories` | Daily |

# Cross-Filtering & Navigation

```
Executive Dashboard
    │
    ├─ click date → Sales Dashboard (filtered by week)
    │
    └─ click order count → Customer Dashboard (filtered by month)

Sales Dashboard
    │
    ├─ click category → Product Dashboard (filtered by category)
    │
    └─ click country → Metabase auto-explore (orders by country)

Customer Dashboard
    │
    └─ click segment → Metabase auto-explore (customers by segment)

Product Dashboard
    │
    └─ click category → narrows to category
```

# Metabase Setup Notes

## Creating the Questions

For each dashboard, create Saved Questions first (one per chart/KPI), then add
them to the dashboard. Use **Native Query** for precise SQL control and
**GUI Mode** for simple aggregates.

## Caching

Set Metabase cache TTL on `rpt_*` tables to **24 hours** since they are
refreshed once per day by the Airflow DAG:

```
Admin → Table Settings → rpt_* → Cache TTL: 86400
```

## Dashboard Subscriptions

Configure email/Slack subscriptions for the Executive Dashboard to send a
daily snapshot after the dbt run completes (~8:00 AM).

# Implementation Order

1. Create saved questions for the 4 Executive KPI scalar cards
2. Create Revenue Trend and Orders Trend questions
3. Build Executive Dashboard layout + date filter
4. Create Sales Dashboard questions (bar charts + table)
5. Link Executive → Sales drill-down
6. Create Customer Dashboard questions
7. Create Product Dashboard questions
8. Set up cross-filtering and navigation
9. Configure caching and subscriptions
