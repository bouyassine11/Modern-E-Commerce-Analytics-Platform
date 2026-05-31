with daily as (
    select
        dd.full_date,
        dd.day_of_week,
        dd.is_weekend,
        count(distinct f.order_id) as total_orders,
        count(f.order_item_id) as total_items,
        sum(f.total_amount) as total_revenue,
        count(distinct f.customer_key) as total_customers
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by dd.full_date, dd.day_of_week, dd.is_weekend
)

select
    full_date as report_date,
    day_of_week,
    is_weekend,
    total_orders,
    total_items,
    total_revenue,
    total_customers,
    case
        when total_orders = 0 then 0
        else total_revenue / total_orders
    end as average_order_value,
    sum(total_revenue) over (order by full_date) as running_total_revenue,
    sum(total_orders) over (order by full_date) as running_total_orders
from daily
order by full_date
