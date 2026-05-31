with source as (
    select
        order_id,
        customer_id,
        order_date,
        status,
        total_amount,
        shipping_address,
        payment_method
    from {{ source('raw', 'orders_raw') }}
    where order_id is not null
),

cleaned as (
    select
        trim(order_id)::integer as order_id,
        nullif(trim(customer_id), '')::integer as customer_id,
        nullif(trim(order_date), '')::timestamp as order_date,
        lower(trim(status)) as status,
        coalesce(nullif(trim(total_amount), ''), '0')::numeric(12,2) as total_amount,
        trim(shipping_address) as shipping_address,
        lower(trim(payment_method)) as payment_method
    from source
),

with_row_number as (
    select
        *,
        row_number() over (
            partition by order_id
            order by order_date desc nulls last
        ) as rn
    from cleaned
    where customer_id is not null
      and order_date is not null
)

select
    order_id,
    customer_id,
    order_date,
    status,
    total_amount,
    shipping_address,
    payment_method,
    current_timestamp as created_at
from with_row_number
where rn = 1
