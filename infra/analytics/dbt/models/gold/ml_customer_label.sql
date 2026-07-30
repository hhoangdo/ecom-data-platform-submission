with parameters as (
  select
    cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts,
    cast('{{ var('label_end_ts') }}' as timestamp) as label_end_ts
),
eligible_customers as (
  select customer.customer_id as id
  from {{ ref('dim_customer') }} customer
  cross join parameters p
  where customer.customer_id is not null
    and customer.created_ts <= p.feature_cutoff_ts
),
positive_customers as (
  select distinct payment.customer_id as id
  from {{ ref('fact_payment_attempt') }} payment
  cross join parameters p
  where payment.customer_id is not null
    and payment.is_payment_success
    and payment.payment_timestamp > p.feature_cutoff_ts
    and payment.payment_timestamp <= p.label_end_ts
    and payment.created_ts <= p.label_end_ts
)
select
  customer.id,
  cast(case when positive.id is not null then 1 else 0 end as integer) as label
from eligible_customers customer
left join positive_customers positive
  on customer.id = positive.id
