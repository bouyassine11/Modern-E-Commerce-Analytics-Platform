-- Each line item's total_price must approximately equal quantity * unit_price.
-- Small rounding differences are tolerated (0.01); larger gaps indicate data corruption.

select
    oi.order_item_id,
    oi.order_id,
    oi.product_id,
    oi.quantity,
    oi.unit_price,
    oi.total_price,
    (oi.quantity * oi.unit_price) as expected_total
from {{ ref('stg_order_items') }} oi
where abs(oi.total_price - (oi.quantity * oi.unit_price)) > 0.01
