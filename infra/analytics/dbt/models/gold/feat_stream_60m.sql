with parameters as (
  select cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts
),
available_events as (
  select events.*
  from {{ ref('stg_commerce_events') }} events
  cross join parameters p
  where events.customer_id is not null
    and events.event_timestamp <= p.feature_cutoff_ts
    and events.created_ts <= p.feature_cutoff_ts
)
select
  customer_id,
  date_trunc('hour', event_timestamp) as event_timestamp,
  sum(case when event_type = 'product_viewed' then 1 else 0 end) as f_stream_views_60m,
  sum(case when event_type = 'add_to_cart' then 1 else 0 end) as f_stream_add_to_cart_60m,
  sum(case when event_type = 'checkout_started' then 1 else 0 end) as f_stream_checkout_started_60m,
  sum(case when event_type = 'order_placed' then 1 else 0 end) as f_stream_order_placed_60m,
  case
    when sum(case when event_type = 'add_to_cart' then 1 else 0 end) > 0
    then sum(case when event_type = 'order_placed' then 1 else 0 end)::double
       / sum(case when event_type = 'add_to_cart' then 1 else 0 end)
    else 0
  end as f_stream_cart_to_purchase_ratio_60m,
  max(created_ts) as created
from available_events
group by 1, 2
