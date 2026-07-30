with parameters as (
  select cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts
),
eligible_customers as (
  select c.customer_id
  from {{ ref('dim_customer') }} c
  cross join parameters p
  where c.customer_id is not null
    and c.created_ts <= p.feature_cutoff_ts
),
eligible_orders as (
  select
    o.order_id,
    o.customer_id,
    o.primary_category,
    o.order_net_amount
  from {{ ref('fact_order') }} o
  cross join parameters p
  where o.customer_id is not null
    and o.order_timestamp > p.feature_cutoff_ts - interval '90 days'
    and o.order_timestamp <= p.feature_cutoff_ts
    and o.created_ts <= p.feature_cutoff_ts
),
successful_orders as (
  select distinct payment.order_id
  from {{ ref('fact_payment_attempt') }} payment
  cross join parameters p
  where payment.is_payment_success
    and payment.payment_timestamp <= p.feature_cutoff_ts
    and payment.created_ts <= p.feature_cutoff_ts
),
customer_orders as (
  select
    customer.customer_id,
    count(orders.order_id) as f_customer_total_orders_90d,
    sum(
      case when paid.order_id is not null then orders.order_net_amount else 0 end
    ) as f_customer_paid_revenue_90d,
    avg(
      case when paid.order_id is not null then orders.order_net_amount end
    ) as f_customer_avg_order_value_90d,
    count(distinct orders.primary_category) as f_customer_distinct_categories_90d
  from eligible_customers customer
  left join eligible_orders orders
    on customer.customer_id = orders.customer_id
  left join successful_orders paid
    on orders.order_id = paid.order_id
  group by 1
)
select
  customer.customer_id,
  p.feature_cutoff_ts as event_timestamp,
  coalesce(customer.f_customer_total_orders_90d, 0) as f_customer_total_orders_90d,
  coalesce(customer.f_customer_paid_revenue_90d, 0.0) as f_customer_paid_revenue_90d,
  coalesce(customer.f_customer_avg_order_value_90d, 0.0) as f_customer_avg_order_value_90d,
  coalesce(
    customer.f_customer_distinct_categories_90d,
    0
  ) as f_customer_distinct_categories_90d,
  p.feature_cutoff_ts as created
from customer_orders customer
cross join parameters p
