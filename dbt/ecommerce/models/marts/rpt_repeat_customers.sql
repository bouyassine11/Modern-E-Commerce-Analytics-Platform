with customer_order_counts as (
    select
        customer_key,
        count(distinct order_id) as order_count,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date
    from (
        select distinct f.customer_key, f.order_id, dd.full_date as order_date
        from {{ ref('fact_sales') }} f
        inner join {{ ref('dim_date') }} dd on f.date_key = dd.date_key
        where f.payment_status in ('paid', 'pending')
    ) distinct_orders
    group by customer_key
),

monthly_cohort as (
    select
        date_trunc('month', first_order_date)::date as cohort_month,
        count(customer_key) as new_customers,
        sum(case when order_count >= 2 then 1 else 0 end) as repeat_customers,
        sum(case when order_count >= 2 then 1 else 0 end)::float
            / nullif(count(customer_key), 0) as repeat_rate
    from customer_order_counts
    group by date_trunc('month', first_order_date)
),

monthly_new_vs_repeat as (
    select
        date_trunc('month', last_order_date)::date as report_month,
        count(case when order_count = 1 then 1 end) as new_customers,
        count(case when order_count >= 2 then 1 end) as repeat_customers
    from customer_order_counts
    group by date_trunc('month', last_order_date)
)

select
    mc.cohort_month,
    mc.new_customers as cohort_size,
    mc.repeat_customers as cohort_repeat_customers,
    round(mc.repeat_rate * 100, 2) as repeat_purchase_rate_pct,
    nr.report_month,
    coalesce(nr.new_customers, 0) as monthly_new_customers,
    coalesce(nr.repeat_customers, 0) as monthly_repeat_customers,
    case
        when coalesce(nr.new_customers + nr.repeat_customers, 0) = 0 then 0
        else round(
            nr.repeat_customers::float / (nr.new_customers + nr.repeat_customers) * 100, 2
        )
    end as monthly_repeat_rate_pct
from monthly_cohort mc
full outer join monthly_new_vs_repeat nr
    on mc.cohort_month = nr.report_month
order by coalesce(mc.cohort_month, nr.report_month)
