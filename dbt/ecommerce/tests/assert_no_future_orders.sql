-- No orders should have an order_date in the future.
-- Future-dated orders indicate timestamp corruption or test data issues.

with orders as (
    select distinct order_id, order_date
    from {{ ref('int_orders_enriched') }}
)

select
    order_id,
    order_date
from orders
where order_date > current_timestamp
