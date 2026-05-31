with date_spine as (
    select generate_series(
        '{{ var("date_spine_start") }}'::date,
        '{{ var("date_spine_end") }}'::date,
        '1 day'::interval
    ) as full_date
)

select
    (extract(year from full_date) * 10000
     + extract(month from full_date) * 100
     + extract(day from full_date))::integer as date_key,
    full_date::date as full_date,
    extract(day from full_date)::integer as day,
    extract(month from full_date)::integer as month,
    to_char(full_date, 'Month') as month_name,
    to_char(full_date, 'Mon') as month_short_name,
    extract(quarter from full_date)::integer as quarter,
    extract(year from full_date)::integer as year,
    extract(dow from full_date)::integer as day_of_week,
    to_char(full_date, 'Day') as day_name,
    extract(doy from full_date)::integer as day_of_year,
    extract(week from full_date)::integer as week_of_year,
    case when extract(dow from full_date) in (0, 6) then true else false end as is_weekend,
    false as is_holiday,
    case
        when extract(month from full_date) between 1 and 3 then 1
        when extract(month from full_date) between 4 and 6 then 2
        when extract(month from full_date) between 7 and 9 then 3
        when extract(month from full_date) between 10 and 12 then 4
    end as fiscal_quarter,
    extract(year from full_date)::integer as fiscal_year,
    (date_trunc('month', full_date) + interval '1 month' - interval '1 day')::date as month_end_date,
    case
        when extract(month from full_date) in (3, 4, 5) then 'Spring'
        when extract(month from full_date) in (6, 7, 8) then 'Summer'
        when extract(month from full_date) in (9, 10, 11) then 'Fall'
        when extract(month from full_date) in (12, 1, 2) then 'Winter'
    end as season
from date_spine
