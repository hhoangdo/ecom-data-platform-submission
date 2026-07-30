select
  label.id,
  features.event_timestamp,
  label.label,
  features.f_customer_total_orders_90d,
  features.f_customer_paid_revenue_90d,
  features.f_customer_avg_order_value_90d,
  features.f_customer_distinct_categories_90d,
  features.f_stream_views_60m,
  features.f_stream_add_to_cart_60m,
  features.f_stream_checkout_started_60m,
  features.f_stream_order_placed_60m,
  features.f_stream_cart_to_purchase_ratio_60m,
  features.created
from {{ ref('ml_customer_label') }} label
inner join {{ ref('feat_customer_unified') }} features
  on label.id = features.customer_id
