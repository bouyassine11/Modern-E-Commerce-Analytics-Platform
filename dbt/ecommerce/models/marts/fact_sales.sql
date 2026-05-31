{{
    config(
        materialized='incremental',
        unique_key='order_item_id',
        on_schema_change='append_new_columns',
        tags=['marts', 'fact', 'daily']
    )
}}

with orders as (
    select
        order_id,
        customer_id,
        product_id,
        quantity,
        unit_price,
        quantity * unit_price as revenue,
        payment_status,
        order_date
    from {{ ref('int_orders_enriched') }}

{% if is_incremental() %}
    where order_date > (
        select max(order_date) from {{ this }}
    )
{% endif %}
),

order_items as (
    select order_item_id, order_id
    from {{ ref('stg_order_items') }}
),

dim_cust as (
    select customer_key, customer_id, is_current
    from {{ ref('dim_customer') }}
    where is_current
),

dim_prod as (
    select product_key, product_id
    from {{ ref('dim_product') }}
),

dim_d as (
    select date_key, full_date
    from {{ ref('dim_date') }}
)

select
    ('x' || substr(md5(
        o.order_id::text || '-' || oi.order_item_id::text
    ), 1, 8))::bit(32)::bigint as sales_key,
    o.order_id,
    oi.order_item_id,
    dc.customer_key,
    dp.product_key,
    dd.date_key,
    o.quantity,
    o.unit_price,
    0::numeric(10,2) as discount_amount,
    o.revenue as total_amount,
    coalesce(o.payment_status, 'pending') as payment_status,
    case
        when o.payment_status = 'completed' then 'paid'
        else o.payment_status
    end as order_status,
    current_timestamp as created_at,
    1 as etl_batch_id
from orders o
inner join dim_cust dc on o.customer_id = dc.customer_id
inner join dim_prod dp on o.product_id = dp.product_id
inner join dim_d dd on o.order_date::date = dd.full_date
left join order_items oi on o.order_id = oi.order_id
