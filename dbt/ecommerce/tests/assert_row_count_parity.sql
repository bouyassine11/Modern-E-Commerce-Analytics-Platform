-- Raw-to-staging row count parity check.
-- Each staging model must have at most 5% fewer rows than its source raw table.
-- Larger drops indicate over-filtering or data loss in the staging transformation.

{% set tables = {
    'stg_customers':    'customers_raw',
    'stg_products':     'products_raw',
    'stg_orders':       'orders_raw',
    'stg_order_items':  'order_items_raw',
    'stg_payments':     'payments_raw',
} %}

{% for stg, raw in tables %}
select
    '{{ stg }}' as model_name,
    '{{ raw }}' as source_name,
    src.row_count as source_rows,
    stg.row_count as model_rows,
    src.row_count - stg.row_count as rows_dropped,
    case
        when src.row_count = 0 then 0
        else round(100.0 * (src.row_count - stg.row_count) / src.row_count, 2)
    end as pct_dropped
from
    (select count(*) as row_count from {{ source('raw', raw) }}) src,
    (select count(*) as row_count from {{ ref(stg) }}) stg
where stg.row_count < src.row_count * 0.95

{% if not loop.last %}union all{% endif %}
{% endfor %}
