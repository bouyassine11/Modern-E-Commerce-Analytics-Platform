with products as (
    select
        product_id,
        name,
        category,
        price,
        stock_quantity,
        description,
        created_at,
        updated_at
    from {{ ref('stg_products') }}
),

product_metrics as (
    select
        product_id,
        sum(quantity) as total_units_sold,
        sum(quantity * unit_price) as gross_revenue,
        avg(unit_price) as avg_unit_price,
        max(order_date) as last_order_date,
        current_date - max(order_date)::date as days_since_last_sale
    from {{ ref('int_orders_enriched') }}
    group by product_id
)

select
    row_number() over (order by p.product_id) as product_key,
    p.product_id,
    p.name as product_name,
    p.category,
    p.price,
    p.stock_quantity,
    p.description,
    coalesce(m.total_units_sold, 0) as total_units_sold,
    coalesce(m.gross_revenue, 0) as gross_revenue,
    coalesce(m.avg_unit_price, 0) as avg_unit_price,
    m.last_order_date,
    m.days_since_last_sale,
    case
        when m.last_order_date is not null
             and m.days_since_last_sale <= 90 then true
        else false
    end as is_active,
    p.created_at,
    p.updated_at
from products p
left join product_metrics m on p.product_id = m.product_id
