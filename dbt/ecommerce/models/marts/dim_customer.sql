with customers as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        phone,
        address,
        city,
        state,
        zip_code,
        country,
        signup_date,
        status,
        created_at as stg_created_at
    from {{ ref('stg_customers') }}
),

customer_orders as (
    select distinct
        customer_id,
        order_id,
        order_amount,
        order_date
    from {{ ref('int_orders_enriched') }}
),

customer_metrics as (
    select
        customer_id,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        count(order_id) as total_orders,
        sum(order_amount) as total_revenue,
        sum(order_amount) / nullif(count(order_id), 0) as avg_order_value,
        (max(order_date) - min(order_date)) as customer_lifetime_days
    from customer_orders
    group by customer_id
)

select
    row_number() over (order by c.customer_id) as customer_key,
    c.customer_id,
    c.first_name || ' ' || c.last_name as full_name,
    c.email,
    c.phone,
    c.address,
    c.city,
    c.state,
    c.zip_code,
    c.country,
    c.signup_date,
    c.status as customer_status,
    current_date - c.signup_date as customer_tenure_days,
    m.first_order_date,
    m.last_order_date,
    coalesce(m.total_orders, 0) as total_orders,
    coalesce(m.total_revenue, 0) as total_revenue,
    coalesce(m.avg_order_value, 0) as avg_order_value,
    m.customer_lifetime_days,
    current_timestamp as dbt_valid_from,
    null::timestamp as dbt_valid_to,
    true as is_current,
    c.stg_created_at as created_at
from customers c
left join customer_metrics m on c.customer_id = m.customer_id
