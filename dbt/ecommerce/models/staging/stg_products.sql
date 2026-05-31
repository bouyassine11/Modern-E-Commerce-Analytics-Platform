with source as (
    select
        product_id,
        name,
        category,
        price,
        stock_quantity,
        description,
        created_at,
        updated_at
    from {{ source('raw', 'products_raw') }}
    where product_id is not null
),

cleaned as (
    select
        trim(product_id)::integer as product_id,
        trim(name) as name,
        trim(category) as category,
        coalesce(nullif(trim(price), ''), '0')::numeric(10,2) as price,
        coalesce(nullif(trim(stock_quantity), ''), '0')::integer as stock_quantity,
        trim(description) as description,
        case
            when trim(created_at) = '' then null
            else trim(created_at)::timestamp
        end as created_at,
        case
            when trim(updated_at) = '' then null
            else trim(updated_at)::timestamp
        end as updated_at
    from source
),

with_row_number as (
    select
        *,
        row_number() over (
            partition by product_id
            order by updated_at desc nulls last
        ) as rn
    from cleaned
)

select
    product_id,
    name,
    category,
    price,
    stock_quantity,
    description,
    created_at,
    updated_at
from with_row_number
where rn = 1
