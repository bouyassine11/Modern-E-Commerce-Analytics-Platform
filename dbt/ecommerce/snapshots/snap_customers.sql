{% snapshot snap_customers %}

{{
    config(
        target_schema='dw',
        unique_key='customer_id',
        strategy='check',
        check_cols=['city', 'country'],
        invalidate_hard_deletes=True
    )
}}

select
    customer_id,
    first_name,
    last_name,
    email,
    phone,
    address,
    city,
    state,
    zip_code,
    country,
    signup_date,
    status,
    created_at as stg_created_at
from {{ ref('stg_customers') }}

{% endsnapshot %}
