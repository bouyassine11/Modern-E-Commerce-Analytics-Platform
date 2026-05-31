with country_sales as (
    select
        c.country,
        count(distinct f.order_id) as total_orders,
        count(distinct f.customer_key) as total_customers,
        count(f.order_item_id) as total_items,
        sum(f.total_amount) as total_revenue,
        avg(f.total_amount) as avg_revenue_per_item,
        min(dd.full_date) as first_order_date,
        max(dd.full_date) as last_order_date
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_customer') }} c
        on f.customer_key = c.customer_key
        and c.is_current
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by c.country
)

select
    country,
    total_orders,
    total_customers,
    total_items,
    total_revenue,
    round(total_revenue / nullif(total_orders, 0), 2) as revenue_per_order,
    round(total_revenue / nullif(total_customers, 0), 2) as revenue_per_customer,
    first_order_date,
    last_order_date,
    row_number() over (order by total_revenue desc) as revenue_rank,
    sum(total_revenue) over () as grand_total_revenue,
    round(total_revenue / sum(total_revenue) over () * 100, 2) as revenue_share_pct
from country_sales
order by revenue_rank
