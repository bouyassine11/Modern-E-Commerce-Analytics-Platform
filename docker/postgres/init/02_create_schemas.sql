-- Creates the raw, staging, dw, and marts schemas inside the ecommerce database.
-- These schemas are used by the ETL pipeline and dbt transformations.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dw;
CREATE SCHEMA IF NOT EXISTS marts;

-- Raw layer — landing zone for CSV data (all TEXT columns for load safety)

CREATE TABLE IF NOT EXISTS raw.products_raw (
    product_id      TEXT,
    name            TEXT,
    category        TEXT,
    price           TEXT,
    stock_quantity  TEXT,
    description     TEXT,
    created_at      TEXT,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS raw.customers_raw (
    customer_id   TEXT,
    first_name    TEXT,
    last_name     TEXT,
    email         TEXT,
    phone         TEXT,
    address       TEXT,
    city          TEXT,
    state         TEXT,
    zip_code      TEXT,
    country       TEXT,
    signup_date   TEXT,
    status        TEXT
);

CREATE TABLE IF NOT EXISTS raw.orders_raw (
    order_id         TEXT,
    customer_id      TEXT,
    order_date       TEXT,
    status           TEXT,
    total_amount     TEXT,
    shipping_address TEXT,
    payment_method   TEXT
);

CREATE TABLE IF NOT EXISTS raw.order_items_raw (
    order_item_id TEXT,
    order_id      TEXT,
    product_id    TEXT,
    quantity      TEXT,
    unit_price    TEXT,
    total_price   TEXT
);

CREATE TABLE IF NOT EXISTS raw.payments_raw (
    payment_id     TEXT,
    order_id       TEXT,
    payment_date   TEXT,
    amount         TEXT,
    payment_method TEXT,
    status         TEXT,
    transaction_id TEXT
);
