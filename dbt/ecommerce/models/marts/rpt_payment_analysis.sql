select
    payment_status,
    count(distinct order_id) as total_orders,
    count(order_item_id) as total_items,
    sum(total_amount) as total_revenue,
    count(distinct customer_key) as total_customers,
    round(
        sum(total_amount) / nullif(count(distinct order_id), 0), 2
    ) as revenue_per_order,
    round(
        sum(total_amount) / nullif(count(distinct customer_key), 0), 2
    ) as revenue_per_customer,
    round(
        sum(total_amount) / sum(sum(total_amount)) over () * 100, 2
    ) as revenue_share_pct,
    round(
        count(distinct order_id)::float
        / sum(count(distinct order_id)) over () * 100, 2
    ) as order_share_pct
from {{ ref('fact_sales') }}
group by payment_status
order by total_revenue desc
