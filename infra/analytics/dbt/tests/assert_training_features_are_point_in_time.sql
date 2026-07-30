with parameters as (
  select cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts
),
eligible_customers as (
  select customer.customer_id
  from {{ ref('dim_customer') }} customer
  cross join parameters p
  where customer.customer_id is not null
    and customer.created_ts <= p.feature_cutoff_ts
),
eligible_orders as (
  select
    orders.order_id,
    orders.customer_id,
    orders.primary_category,
    orders.order_net_amount
  from {{ ref('fact_order') }} orders
  cross join parameters p
  where orders.customer_id is not null
    and orders.order_timestamp > p.feature_cutoff_ts - interval '90 days'
    and orders.order_timestamp <= p.feature_cutoff_ts
    and orders.created_ts <= p.feature_cutoff_ts
),
successful_orders as (
  select distinct payment.order_id
  from {{ ref('fact_payment_attempt') }} payment
  cross join parameters p
  where payment.is_payment_success
    and payment.payment_timestamp <= p.feature_cutoff_ts
    and payment.created_ts <= p.feature_cutoff_ts
),
offline as (
  select
    customer.customer_id,
    count(orders.order_id) as f_customer_total_orders_90d,
    coalesce(
      sum(case when paid.order_id is not null then orders.order_net_amount else 0 end),
      0.0
    ) as f_customer_paid_revenue_90d,
    coalesce(
      avg(case when paid.order_id is not null then orders.order_net_amount end),
      0.0
    ) as f_customer_avg_order_value_90d,
    count(distinct orders.primary_category) as f_customer_distinct_categories_90d
  from eligible_customers customer
  left join eligible_orders orders
    on customer.customer_id = orders.customer_id
  left join successful_orders paid
    on orders.order_id = paid.order_id
  group by 1
),
stream_hours as (
  select
    events.customer_id,
    date_trunc('hour', events.event_timestamp) as event_timestamp,
    sum(case when events.event_type = 'product_viewed' then 1 else 0 end) as f_stream_views_60m,
    sum(case when events.event_type = 'add_to_cart' then 1 else 0 end) as f_stream_add_to_cart_60m,
    sum(case when events.event_type = 'checkout_started' then 1 else 0 end) as f_stream_checkout_started_60m,
    sum(case when events.event_type = 'order_placed' then 1 else 0 end) as f_stream_order_placed_60m,
    case
      when sum(case when events.event_type = 'add_to_cart' then 1 else 0 end) > 0
      then sum(case when events.event_type = 'order_placed' then 1 else 0 end)::double
        / sum(case when events.event_type = 'add_to_cart' then 1 else 0 end)
      else 0
    end as f_stream_cart_to_purchase_ratio_60m,
    max(events.created_ts) as created
  from {{ ref('stg_commerce_events') }} events
  cross join parameters p
  where events.customer_id is not null
    and events.event_timestamp <= p.feature_cutoff_ts
    and events.created_ts <= p.feature_cutoff_ts
  group by 1, 2
),
latest_stream as (
  select * exclude (rn)
  from (
    select
      stream.*,
      row_number() over (
        partition by customer_id
        order by event_timestamp desc, created desc
      ) as rn
    from stream_hours stream
  )
  where rn = 1
),
expected as (
  select
    label.id,
    p.feature_cutoff_ts as event_timestamp,
    label.label,
    offline.f_customer_total_orders_90d,
    offline.f_customer_paid_revenue_90d,
    offline.f_customer_avg_order_value_90d,
    offline.f_customer_distinct_categories_90d,
    coalesce(stream.f_stream_views_60m, 0) as f_stream_views_60m,
    coalesce(stream.f_stream_add_to_cart_60m, 0) as f_stream_add_to_cart_60m,
    coalesce(stream.f_stream_checkout_started_60m, 0) as f_stream_checkout_started_60m,
    coalesce(stream.f_stream_order_placed_60m, 0) as f_stream_order_placed_60m,
    coalesce(stream.f_stream_cart_to_purchase_ratio_60m, 0.0) as f_stream_cart_to_purchase_ratio_60m,
    p.feature_cutoff_ts as created
  from {{ ref('ml_customer_label') }} label
  join offline
    on label.id = offline.customer_id
  cross join parameters p
  left join latest_stream stream
    on label.id = stream.customer_id
),
differences as (
  select
    coalesce(actual.id, expected.id) as id
  from {{ ref('ml_customer_purchase_training') }} actual
  full outer join expected
    on actual.id = expected.id
  where actual.id is null
    or expected.id is null
    or actual.event_timestamp is distinct from expected.event_timestamp
    or actual.label is distinct from expected.label
    or actual.f_customer_total_orders_90d is distinct from expected.f_customer_total_orders_90d
    or actual.f_customer_paid_revenue_90d is distinct from expected.f_customer_paid_revenue_90d
    or actual.f_customer_avg_order_value_90d is distinct from expected.f_customer_avg_order_value_90d
    or actual.f_customer_distinct_categories_90d is distinct from expected.f_customer_distinct_categories_90d
    or actual.f_stream_views_60m is distinct from expected.f_stream_views_60m
    or actual.f_stream_add_to_cart_60m is distinct from expected.f_stream_add_to_cart_60m
    or actual.f_stream_checkout_started_60m is distinct from expected.f_stream_checkout_started_60m
    or actual.f_stream_order_placed_60m is distinct from expected.f_stream_order_placed_60m
    or actual.f_stream_cart_to_purchase_ratio_60m is distinct from expected.f_stream_cart_to_purchase_ratio_60m
    or actual.created is distinct from expected.created
)
select * from differences
