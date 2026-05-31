with source as (
    select
        payment_id,
        order_id,
        payment_date,
        amount,
        payment_method,
        status,
        transaction_id
    from {{ source('raw', 'payments_raw') }}
    where payment_id is not null
),

cleaned as (
    select
        trim(payment_id)::integer as payment_id,
        nullif(trim(order_id), '')::integer as order_id,
        nullif(trim(payment_date), '')::timestamp as payment_date,
        coalesce(nullif(trim(amount), ''), '0')::numeric(12,2) as amount,
        lower(trim(payment_method)) as payment_method,
        lower(trim(status)) as status,
        trim(transaction_id) as transaction_id
    from source
)

select
    payment_id,
    order_id,
    payment_date,
    amount,
    payment_method,
    status,
    transaction_id,
    current_timestamp as created_at
from cleaned
where order_id is not null
  and payment_date is not null
