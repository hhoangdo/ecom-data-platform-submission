with parameters as (
  select cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts
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
    from {{ ref('feat_stream_60m') }} stream
  )
  where rn = 1
)
select
  customer.customer_id,
  p.feature_cutoff_ts as event_timestamp,
  customer.f_customer_total_orders_90d,
  customer.f_customer_paid_revenue_90d,
  customer.f_customer_avg_order_value_90d,
  customer.f_customer_distinct_categories_90d,
  coalesce(stream.f_stream_views_60m, 0) as f_stream_views_60m,
  coalesce(stream.f_stream_add_to_cart_60m, 0) as f_stream_add_to_cart_60m,
  coalesce(stream.f_stream_checkout_started_60m, 0) as f_stream_checkout_started_60m,
  coalesce(stream.f_stream_order_placed_60m, 0) as f_stream_order_placed_60m,
  coalesce(
    stream.f_stream_cart_to_purchase_ratio_60m,
    0.0
  ) as f_stream_cart_to_purchase_ratio_60m,
  p.feature_cutoff_ts as created
from {{ ref('feat_customer_90d') }} customer
cross join parameters p
left join latest_stream stream
  on customer.customer_id = stream.customer_id
