-- Every order must be placed after the customer's signup date.
-- A signup_date after the order_date indicates a data integrity issue.

with customer_signup as (
    select customer_id, signup_date
    from {{ ref('dim_customer') }}
    where is_current
)

select
    o.customer_id,
    o.order_id,
    o.order_date,
    c.signup_date
from {{ ref('fact_sales') }} o
inner join customer_signup c on o.customer_id = c.customer_id
where c.signup_date > o.created_at::date
