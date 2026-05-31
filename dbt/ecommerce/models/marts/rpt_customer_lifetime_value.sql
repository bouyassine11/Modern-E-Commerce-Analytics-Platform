with customer_orders as (
    select
        customer_key,
        count(distinct order_id) as total_orders,
        count(order_item_id) as total_items,
        sum(total_amount) as total_revenue,
        min(date_key) as first_order_date_key,
        max(date_key) as last_order_date_key
    from {{ ref('fact_sales') }}
    where payment_status in ('paid', 'pending')
    group by customer_key
),

customer_rfm as (
    select
        co.customer_key,
        c.customer_id,
        c.full_name,
        c.country,
        c.signup_date,
        co.total_orders,
        co.total_items,
        co.total_revenue,
        case
            when co.total_orders = 0 then 0
            else co.total_revenue / co.total_orders
        end as avg_order_value,
        current_date - c.signup_date as customer_tenure_days,
        (select full_date from {{ ref('dim_date') }} where date_key = co.last_order_date_key)
            as last_order_date,
        (select full_date from {{ ref('dim_date') }} where date_key = co.first_order_date_key)
            as first_order_date,
        case
            when co.total_orders <= 1 then 0
            else (
                select full_date from {{ ref('dim_date') }} where date_key = co.last_order_date_key
            ) - (
                select full_date from {{ ref('dim_date') }} where date_key = co.first_order_date_key
            )
        end as customer_lifetime_days
    from customer_orders co
    inner join {{ ref('dim_customer') }} c
        on co.customer_key = c.customer_key
        and c.is_current
),

rfm_scores as (
    select
        *,
        ntile(5) over (order by total_revenue desc) as revenue_score,
        ntile(5) over (order by total_orders desc) as frequency_score,
        ntile(5) over (order by last_order_date desc nulls last) as recency_score
    from customer_rfm
)

select
    customer_key,
    customer_id,
    full_name,
    country,
    signup_date,
    first_order_date,
    last_order_date,
    total_orders,
    total_items,
    total_revenue,
    avg_order_value,
    customer_tenure_days,
    customer_lifetime_days,
    coalesce(current_date - last_order_date, customer_tenure_days) as days_since_last_order,
    recency_score,
    frequency_score,
    revenue_score,
    round((recency_score + frequency_score + revenue_score)::numeric / 3, 1) as rfm_score,
    case
        when recency_score >= 4 and frequency_score >= 4 then 'Champions'
        when recency_score >= 4 and frequency_score >= 2 then 'Loyal Customers'
        when recency_score >= 3 and frequency_score >= 3 then 'Potential Loyalists'
        when recency_score >= 4 and frequency_score = 1 then 'New Customers'
        when recency_score = 1 and frequency_score >= 4 then 'At Risk'
        when recency_score = 1 and frequency_score >= 2 then 'Needs Attention'
        when recency_score = 1 and frequency_score = 1 then 'Lost'
        else 'Other'
    end as customer_segment
from rfm_scores
order by total_revenue desc
