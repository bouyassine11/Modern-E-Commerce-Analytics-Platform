with product_sales as (
    select
        p.product_key,
        p.product_id,
        p.product_name,
        p.category,
        p.price as current_price,
        sum(f.quantity) as total_units_sold,
        sum(f.total_amount) as gross_revenue,
        count(distinct f.order_id) as order_count,
        count(distinct f.customer_key) as customer_count,
        avg(f.unit_price) as avg_unit_price,
        max(dd.full_date) as last_order_date,
        current_date - max(dd.full_date) as days_since_last_sale
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_product') }} p on f.product_key = p.product_key
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by p.product_key, p.product_id, p.product_name, p.category, p.price
),

category_totals as (
    select
        category,
        sum(gross_revenue) as category_total_revenue
    from product_sales
    group by category
)

select
    ps.product_key,
    ps.product_id,
    ps.product_name,
    ps.category,
    ps.current_price,
    ps.avg_unit_price,
    case
        when ps.avg_unit_price = 0 then null
        else round(ps.current_price / ps.avg_unit_price, 2)
    end as price_vs_avg_ratio,
    ps.total_units_sold,
    ps.gross_revenue,
    ps.order_count,
    ps.customer_count,
    ps.last_order_date,
    ps.days_since_last_sale,
    row_number() over (order by ps.gross_revenue desc) as revenue_rank,
    row_number() over (partition by ps.category order by ps.gross_revenue desc) as category_rank,
    case
        when ct.category_total_revenue = 0 then 0
        else round(ps.gross_revenue / ct.category_total_revenue * 100, 2)
    end as category_revenue_pct
from product_sales ps
inner join category_totals ct on ps.category = ct.category
order by revenue_rank
