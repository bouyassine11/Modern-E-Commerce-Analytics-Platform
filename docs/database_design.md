# PostgreSQL Database Design — E-Commerce Analytics Platform

---

## Entity-Relationship Diagram (Text)

```
┌──────────────────┐       ┌───────────────────┐       ┌──────────────────┐
│   dim_customer   │       │    fact_sales      │       │   dim_product    │
│──────────────────│       │────────────────────│       │──────────────────│
│ PK customer_key◀─┼───────┼─ FK customer_key   │       │ PK product_key   │
│     customer_id  │       │── FK product_key ──┼──────▶│     product_id   │
│     first_name   │       │── FK date_key      │       │     product_name │
│     last_name    │       │                    │       │     category     │
│     email        │       │     order_id       │       │     price        │
│     phone        │       │     order_item_id  │       │     stock_qty    │
│     address      │       │     quantity       │       │     description  │
│     city         │       │     unit_price     │       └──────────────────┘
│     state        │       │     total_amount   │
│     zip_code     │       │     payment_status │              △
│     country      │       │     order_status   │              │
│     signup_date  │       └─────────┬──────────┘              │
│     status       │                 │                         │
└──────────────────┘                 │                         │
                                     │                         │
                            ┌────────▼──────────┐              │
                            │    dim_date        │              │
                            │───────────────────│              │
                            │ PK date_key        │              │
                            │     full_date      │              │
                            │     day            │              │
                            │     month          │              │
                            │     quarter        │              │
                            │     year           │              │
                            │     day_of_week    │              │
                            │     is_weekend     │              │
                            └────────────────────┘              │
```

**Grain of `fact_sales`:** One row per line item in an order (atomic transaction grain).

**Relationship summary:**
- `fact_sales.customer_key` → `dim_customer.customer_key` (many-to-one)
- `fact_sales.product_key` → `dim_product.product_key` (many-to-one)
- `fact_sales.date_key` → `dim_date.date_key` (many-to-one)

---

## Layer 1: Raw Schema (`raw`)

Mirror of CSV files. All columns stored as `TEXT` or `VARCHAR` to guarantee load success. No constraints beyond the bare minimum.

### `raw.products`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| product_id | INTEGER | PK | Business key from source |
| name | VARCHAR(255) | NOT NULL | |
| category | VARCHAR(100) | | |
| price | VARCHAR(50) | | Stored as string; cast in staging |
| stock_quantity | VARCHAR(20) | | |
| description | TEXT | | |
| created_at | VARCHAR(30) | | ISO timestamp string |
| updated_at | VARCHAR(30) | | |

**Index:** `PK (product_id)`

### `raw.customers`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| customer_id | INTEGER | PK | Business key |
| first_name | VARCHAR(100) | | |
| last_name | VARCHAR(100) | | |
| email | VARCHAR(255) | | |
| phone | VARCHAR(50) | | |
| address | TEXT | | |
| city | VARCHAR(100) | | |
| state | VARCHAR(50) | | |
| zip_code | VARCHAR(20) | | |
| country | VARCHAR(100) | | |
| signup_date | VARCHAR(30) | | |
| status | VARCHAR(20) | | |

**Index:** `PK (customer_id)`

### `raw.orders`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| order_id | INTEGER | PK | |
| customer_id | VARCHAR(20) | | FK target validated in staging |
| order_date | VARCHAR(30) | | |
| status | VARCHAR(50) | | |
| total_amount | VARCHAR(50) | | |
| shipping_address | TEXT | | |
| payment_method | VARCHAR(50) | | |

**Index:** `PK (order_id)`

### `raw.order_items`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| order_item_id | INTEGER | PK | |
| order_id | VARCHAR(20) | | |
| product_id | VARCHAR(20) | | |
| quantity | VARCHAR(20) | | |
| unit_price | VARCHAR(50) | | |
| total_price | VARCHAR(50) | | |

**Index:** `PK (order_item_id)`

### `raw.payments`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| payment_id | INTEGER | PK | |
| order_id | VARCHAR(20) | | |
| payment_date | VARCHAR(30) | | |
| amount | VARCHAR(50) | | |
| payment_method | VARCHAR(50) | | |
| status | VARCHAR(20) | | |
| transaction_id | VARCHAR(100) | | |

**Index:** `PK (payment_id)`

---

## Layer 2: Staging Schema (`stg`)

Typed, cleaned, and constrained. All NULLs resolved, duplicates removed, referential integrity enforced.

### `stg.products`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| product_id | INTEGER | PK | Identity column |
| name | VARCHAR(255) | NOT NULL | |
| category | VARCHAR(100) | | |
| price | NUMERIC(10,2) | NOT NULL, CHECK (price >= 0) | |
| stock_quantity | INTEGER | NOT NULL DEFAULT 0, CHECK (stock_qty >= 0) | |
| description | TEXT | | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMP | | |

**Indexes:**
- `PK (product_id)`

### `stg.customers`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| customer_id | INTEGER | PK | Identity column |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| email | VARCHAR(255) | NOT NULL | |
| phone | VARCHAR(20) | | Normalized format |
| address | TEXT | | |
| city | VARCHAR(100) | | |
| state | VARCHAR(50) | | |
| zip_code | VARCHAR(20) | | |
| country | VARCHAR(100) | NOT NULL DEFAULT 'USA' | |
| signup_date | DATE | NOT NULL | |
| status | VARCHAR(20) | NOT NULL DEFAULT 'active', CHECK (status IN ('active','inactive','suspended')) | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | |

**Indexes:**
- `PK (customer_id)`
- `UNIQUE (email)`
- `INDEX (status)`

### `stg.orders`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| order_id | INTEGER | PK | Identity column |
| customer_id | INTEGER | NOT NULL, FK → stg.customers(customer_id) | |
| order_date | TIMESTAMP | NOT NULL | |
| status | VARCHAR(50) | NOT NULL, CHECK (status IN ('pending','processing','shipped','delivered','cancelled','refunded')) | |
| total_amount | NUMERIC(12,2) | NOT NULL, CHECK (total_amount >= 0) | |
| shipping_address | TEXT | | |
| payment_method | VARCHAR(50) | | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | |

**Indexes:**
- `PK (order_id)`
- `INDEX (customer_id)` — FK lookup
- `INDEX (order_date)` — time-range queries
- `INDEX (status)` — filter by order state

### `stg.order_items`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| order_item_id | INTEGER | PK | Identity column |
| order_id | INTEGER | NOT NULL, FK → stg.orders(order_id) | |
| product_id | INTEGER | NOT NULL, FK → stg.products(product_id) | |
| quantity | INTEGER | NOT NULL, CHECK (quantity > 0) | |
| unit_price | NUMERIC(10,2) | NOT NULL, CHECK (unit_price >= 0) | |
| total_price | NUMERIC(12,2) | NOT NULL, CHECK (total_price >= 0) | Can be generated or provided |

**Indexes:**
- `PK (order_item_id)`
- `INDEX (order_id)` — FK lookup
- `INDEX (product_id)` — FK lookup
- `UNIQUE (order_id, order_item_id)` — unique line item within order

### `stg.payments`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| payment_id | INTEGER | PK | Identity column |
| order_id | INTEGER | NOT NULL, FK → stg.orders(order_id) | |
| payment_date | TIMESTAMP | NOT NULL | |
| amount | NUMERIC(12,2) | NOT NULL, CHECK (amount > 0) | |
| payment_method | VARCHAR(50) | | |
| status | VARCHAR(20) | NOT NULL, CHECK (status IN ('pending','completed','failed','refunded')) | |
| transaction_id | VARCHAR(100) | UNIQUE | External gateway ID |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | |

**Indexes:**
- `PK (payment_id)`
- `INDEX (order_id)` — FK lookup
- `UNIQUE (transaction_id)`

---

## Layer 3: Warehouse Schema (`dw`)

Star schema with surrogate-keyed dimensions and an atomic fact table.

### `dw.dim_customer`

SCD Type 1 (overwrite on change). Type 2 tracked via `dbt_valid_from`/`dbt_valid_to` for future migration.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| customer_key | INTEGER | PK | Surrogate key |
| customer_id | INTEGER | NOT NULL | Business key |
| first_name | VARCHAR(100) | NOT NULL | |
| last_name | VARCHAR(100) | NOT NULL | |
| full_name | VARCHAR(201) | GENERATED AS (first_name \|\| ' ' \|\| last_name) STORED | Derived for convenience |
| email | VARCHAR(255) | NOT NULL | |
| phone | VARCHAR(20) | | |
| address | TEXT | | |
| city | VARCHAR(100) | | |
| state | VARCHAR(50) | | |
| zip_code | VARCHAR(20) | | |
| country | VARCHAR(100) | NOT NULL DEFAULT 'USA' | |
| signup_date | DATE | | |
| customer_status | VARCHAR(20) | NOT NULL DEFAULT 'active' | |
| customer_tenure_days | INTEGER | GENERATED AS (CURRENT_DATE - signup_date) STORED | |
| dbt_valid_from | TIMESTAMP | NOT NULL DEFAULT NOW() | SCD tracking |
| dbt_valid_to | TIMESTAMP | | NULL = current record |
| is_current | BOOLEAN | NOT NULL DEFAULT TRUE | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | |

**Indexes:**
- `PK (customer_key)`
- `UNIQUE (customer_id, dbt_valid_from)` — SCD uniqueness
- `INDEX (email)`
- `INDEX (customer_status)`
- `INDEX (is_current)` — filter active records
- `INDEX (city, state)` — geographic queries

### `dw.dim_product`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| product_key | INTEGER | PK | Surrogate key |
| product_id | INTEGER | NOT NULL | Business key |
| product_name | VARCHAR(255) | NOT NULL | |
| category | VARCHAR(100) | | |
| price | NUMERIC(10,2) | NOT NULL | Latest price |
| stock_quantity | INTEGER | NOT NULL DEFAULT 0 | |
| description | TEXT | | |
| created_at | TIMESTAMP | | From source |
| updated_at | TIMESTAMP | | |

**Indexes:**
- `PK (product_key)`
- `UNIQUE (product_id)`
- `INDEX (category)`
- `INDEX (product_name)` — search/lookup queries

### `dw.dim_date`

Static date dimension. Populated once for 10+ years. No ETL needed after initial load.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| date_key | INTEGER | PK | Format: YYYYMMDD (e.g., 20260115) |
| full_date | DATE | NOT NULL, UNIQUE | |
| day | INTEGER | NOT NULL | 1–31 |
| month | INTEGER | NOT NULL | 1–12 |
| month_name | VARCHAR(20) | NOT NULL | January–December |
| month_short_name | VARCHAR(4) | NOT NULL | Jan–Dec |
| quarter | INTEGER | NOT NULL | 1–4 |
| year | INTEGER | NOT NULL | |
| day_of_week | INTEGER | NOT NULL | 0=Sunday, 6=Saturday |
| day_name | VARCHAR(20) | NOT NULL | Sunday–Saturday |
| day_of_year | INTEGER | NOT NULL | 1–366 |
| week_of_year | INTEGER | NOT NULL | 1–53 |
| is_weekend | BOOLEAN | NOT NULL | |
| is_holiday | BOOLEAN | NOT NULL DEFAULT FALSE | |
| fiscal_quarter | INTEGER | | Configurable fiscal calendar |
| fiscal_year | INTEGER | | |
| month_end_date | DATE | | Last day of month |
| season | VARCHAR(10) | | Spring/Summer/Fall/Winter |

**Indexes:**
- `PK (date_key)`
- `UNIQUE (full_date)`
- `INDEX (year, month)`
- `INDEX (year, quarter)`
- `INDEX (is_weekend)`

### `dw.fact_sales`

**Grain:** One row per line item in an order (atomic transaction fact).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| sales_key | BIGINT | PK | Surrogate key (high volume table) |
| order_id | INTEGER | NOT NULL | Degenerate dimension |
| order_item_id | INTEGER | NOT NULL | Degenerate dimension |
| customer_key | INTEGER | NOT NULL, FK → dw.dim_customer(customer_key) | |
| product_key | INTEGER | NOT NULL, FK → dw.dim_product(product_key) | |
| date_key | INTEGER | NOT NULL, FK → dw.dim_date(date_key) | Order date |
| quantity | INTEGER | NOT NULL, CHECK (quantity > 0) | |
| unit_price | NUMERIC(10,2) | NOT NULL, CHECK (unit_price >= 0) | Price at time of order |
| discount_amount | NUMERIC(10,2) | NOT NULL DEFAULT 0, CHECK (discount_amount >= 0) | |
| total_amount | NUMERIC(12,2) | NOT NULL, CHECK (total_amount >= 0) | (unit_price × quantity) − discount |
| payment_status | VARCHAR(20) | | completed, pending, failed, refunded |
| order_status | VARCHAR(50) | | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | DW load timestamp |
| etl_batch_id | INTEGER | | For lineage and debugging |

**Indexes:**
- `PK (sales_key)`
- `INDEX (customer_key)` — FK lookup
- `INDEX (product_key)` — FK lookup
- `INDEX (date_key)` — FK lookup
- `INDEX (order_id)` — debugging / back-reference
- `INDEX (order_item_id)` — debugging
- `INDEX (date_key, product_key)` — product performance over time
- `INDEX (date_key, customer_key)` — customer purchase patterns
- `INDEX (payment_status)` — payment reconciliation

**FK Constraints:**
- `fk_sales_customer` → `dw.dim_customer(customer_key)`
- `fk_sales_product` → `dw.dim_product(product_key)`
- `fk_sales_date` → `dw.dim_date(date_key)`

### Physical Storage Notes

| Table | Est. Row Count | Est. Size | Notes |
|---|---|---|---|
| `dim_customer` | 10K–100K | Small | Few hundred KB |
| `dim_product` | 1K–10K | Small | Few hundred KB |
| `dim_date` | 3,650 (10 yrs) | Tiny | ~200 KB |
| `fact_sales` | 1M–100M+ | Medium–Large | Primary growth table |

**Performance recommendations:**
- `fact_sales` should use `CLUSTER` on `(date_key)` for time-range scans
- Partitioning on `date_key` by year should be documented for >50M rows
- `dim_date` fits entirely in RAM — no tuning needed
- Regular `ANALYZE` on all tables after bulk loads
- `autovacuum` tuning considered for `fact_sales` under heavy write load

---

## Schema DDL Order

```
1. CREATE SCHEMA IF NOT EXISTS raw;
2. CREATE SCHEMA IF NOT EXISTS stg;
3. CREATE SCHEMA IF NOT EXISTS dw;

4. raw.products
5. raw.customers
6. raw.orders
7. raw.order_items
8. raw.payments

9. stg.products
10. stg.customers
11. stg.orders          (FK → stg.customers)
12. stg.order_items     (FK → stg.orders, stg.products)
13. stg.payments        (FK → stg.orders)

14. dw.dim_date
15. dw.dim_customer
16. dw.dim_product
17. dw.fact_sales       (FK → all three dimensions)
```

---

## Index Justification Summary

| Index | Table | Rationale |
|---|---|---|
| `customer_id` | `stg.orders` | FK join to customers |
| `order_date` | `stg.orders` | Daily/range queries |
| `status` | `stg.orders` | Status-based filtering |
| `order_id` | `stg.order_items` | FK join to orders |
| `product_id` | `stg.order_items` | FK join to products |
| `order_id` | `stg.payments` | FK join to orders |
| `email` | `dim_customer` | Lookup/login queries |
| `is_current` | `dim_customer` | Filter active records |
| `category` | `dim_product` | Category analysis |
| `date_key` | `fact_sales` | FK join, time range filtering |
| `(date_key, product_key)` | `fact_sales` | Product performance queries |
| `(date_key, customer_key)` | `fact_sales` | Customer purchase patterns |
| `payment_status` | `fact_sales` | Payment reconciliation |
