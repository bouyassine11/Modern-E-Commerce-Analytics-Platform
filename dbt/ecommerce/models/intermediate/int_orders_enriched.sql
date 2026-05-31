with orders as (
    select order_id, customer_id, order_date, status, total_amount
    from {{ ref('stg_orders') }}
),

customers as (
    select customer_id, first_name, last_name, country
    from {{ ref('stg_customers') }}
),

order_items as (
    select order_item_id, order_id, product_id, quantity, unit_price, total_price
    from {{ ref('stg_order_items') }}
),

products as (
    select product_id, name, category
    from {{ ref('stg_products') }}
),

payments as (
    select order_id, payment_method, status, amount, payment_date
    from {{ ref('stg_payments') }}
),

payment_summary as (
    select
        order_id,
        case
            when bool_or(status = 'completed') then 'completed'
            when bool_or(status = 'refunded') then 'refunded'
            when bool_or(status = 'pending') then 'pending'
            when bool_or(status = 'failed') then 'failed'
        end as payment_status,
        (array_agg(payment_method order by payment_date desc))[1] as payment_method,
        sum(amount) filter (where status = 'completed') as total_paid,
        sum(amount) filter (where status = 'refunded') as total_refunded,
        count(*) as payment_count
    from payments
    group by order_id
)

select
    oi.order_id,
    o.customer_id,
    c.first_name || ' ' || c.last_name as customer_name,
    c.country,
    oi.product_id,
    p.name as product_name,
    p.category,
    oi.quantity,
    oi.unit_price,
    o.total_amount as order_amount,
    coalesce(ps.payment_method, o.payment_method) as payment_method,
    ps.payment_status,
    o.order_date
from order_items oi
inner join orders o on oi.order_id = o.order_id
inner join customers c on o.customer_id = c.customer_id
inner join products p on oi.product_id = p.product_id
left join payment_summary ps on oi.order_id = ps.order_id
