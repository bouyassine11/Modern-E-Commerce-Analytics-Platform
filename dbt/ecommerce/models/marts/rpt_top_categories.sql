with category_sales as (
    select
        p.category,
        count(distinct f.order_id) as total_orders,
        count(distinct f.customer_key) as total_customers,
        sum(f.quantity) as total_units_sold,
        sum(f.total_amount) as gross_revenue,
        avg(f.unit_price) as avg_unit_price,
        count(distinct p.product_key) as active_products,
        min(dd.full_date) as first_sale_date,
        max(dd.full_date) as last_sale_date
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_product') }} p on f.product_key = p.product_key
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by p.category
)

select
    category,
    total_orders,
    total_customers,
    total_units_sold,
    gross_revenue,
    round(gross_revenue / nullif(total_orders, 0), 2) as revenue_per_order,
    avg_unit_price,
    active_products,
    first_sale_date,
    last_sale_date,
    row_number() over (order by gross_revenue desc) as revenue_rank,
    sum(gross_revenue) over () as total_revenue_all,
    round(gross_revenue / sum(gross_revenue) over () * 100, 2) as revenue_share_pct
from category_sales
order by revenue_rank
