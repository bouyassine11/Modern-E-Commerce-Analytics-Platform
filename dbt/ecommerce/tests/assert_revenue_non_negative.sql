-- Every line item must have non-negative revenue.
-- Negative revenue would indicate data corruption or incorrect refund handling.

select
    sales_key,
    order_id,
    order_item_id,
    total_amount
from {{ ref('fact_sales') }}
where total_amount < 0
