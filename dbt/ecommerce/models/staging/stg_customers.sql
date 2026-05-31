with source as (
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
        status
    from {{ source('raw', 'customers_raw') }}
    where customer_id is not null
),

cleaned as (
    select
        trim(customer_id)::integer as customer_id,
        trim(first_name) as first_name,
        trim(last_name) as last_name,
        lower(trim(email)) as email,
        trim(phone) as phone,
        trim(address) as address,
        trim(city) as city,
        trim(state) as state,
        trim(zip_code) as zip_code,
        coalesce(trim(country), 'USA') as country,
        nullif(trim(signup_date), '')::date as signup_date,
        coalesce(trim(status), 'active') as status
    from source
),

with_row_number as (
    select
        *,
        row_number() over (
            partition by customer_id
            order by signup_date desc nulls last
        ) as rn
    from cleaned
    where signup_date is not null
)

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
    current_timestamp as created_at
from with_row_number
where rn = 1
