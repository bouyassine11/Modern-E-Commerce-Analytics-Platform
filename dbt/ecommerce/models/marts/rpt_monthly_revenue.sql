with monthly as (
    select
        dd.year,
        dd.month,
        dd.month_name,
        dd.quarter,
        count(distinct f.order_id) as total_orders,
        count(f.order_item_id) as total_items,
        sum(f.total_amount) as total_revenue,
        count(distinct f.customer_key) as total_customers
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by dd.year, dd.month, dd.month_name, dd.quarter
)

select
    year,
    month,
    month_name,
    quarter,
    total_orders,
    total_items,
    total_revenue,
    total_customers,
    case
        when total_orders = 0 then 0
        else total_revenue / total_orders
    end as average_order_value,
    lag(total_revenue) over (order by year, month) as prev_month_revenue,
    case
        when lag(total_revenue) over (order by year, month) = 0 then null
        when lag(total_revenue) over (order by year, month) is null then null
        else round(
            (total_revenue - lag(total_revenue) over (order by year, month))
            / lag(total_revenue) over (order by year, month) * 100,
            2
        )
    end as revenue_growth_pct
from monthly
order by year, month
