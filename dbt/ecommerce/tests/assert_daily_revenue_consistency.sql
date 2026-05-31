-- Daily revenue in fact_sales should never be negative for non-refunded orders.
-- A negative daily total with no refunded orders indicates data corruption.

with daily_revenue as (
    select
        dd.full_date,
        sum(f.total_amount) as total_revenue,
        count(distinct f.order_id) as order_count
    from {{ ref('fact_sales') }} f
    inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
    where f.payment_status in ('paid', 'pending')
    group by dd.full_date
)

select
    full_date,
    total_revenue,
    order_count
from daily_revenue
where total_revenue < 0
