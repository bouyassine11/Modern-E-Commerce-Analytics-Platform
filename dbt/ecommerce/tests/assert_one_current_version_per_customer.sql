-- Each customer must have exactly one current version in dim_customer
-- Violations indicate SCD tracking corruption or invalid snapshot state

with current_counts as (
    select
        customer_id,
        count(*) as current_version_count
    from {{ ref('dim_customer') }}
    where is_current
    group by customer_id
)

select
    customer_id,
    current_version_count
from current_counts
where current_version_count != 1
