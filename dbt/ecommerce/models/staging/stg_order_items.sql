with source as (
    select
        order_item_id,
        order_id,
        product_id,
        quantity,
        unit_price,
        total_price
    from {{ source('raw', 'order_items_raw') }}
    where order_item_id is not null
),

cleaned as (
    select
        trim(order_item_id)::integer as order_item_id,
        nullif(trim(order_id), '')::integer as order_id,
        nullif(trim(product_id), '')::integer as product_id,
        coalesce(nullif(trim(quantity), ''), '0')::integer as quantity,
        coalesce(nullif(trim(unit_price), ''), '0')::numeric(10,2) as unit_price,
        coalesce(nullif(trim(total_price), ''), '0')::numeric(12,2) as total_price
    from source
)

select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    total_price
from cleaned
where order_id is not null
  and product_id is not null
  and quantity > 0
