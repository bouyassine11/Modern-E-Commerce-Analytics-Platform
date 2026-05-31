-- Every fact_sales row must reference a valid customer_key in dim_customer.
-- Orphaned facts cause incorrect revenue totals and broken dashboards.

select
    f.sales_key,
    f.order_id,
    f.customer_key
from {{ ref('fact_sales') }} f
left join {{ ref('dim_customer') }} c on f.customer_key = c.customer_key
where c.customer_key is null
