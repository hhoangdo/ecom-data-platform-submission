from __future__ import annotations

from dataclasses import dataclass
import math

from vina_bim_shop.lakehouse.spark.constants import DP3_GOLD_TABLES


@dataclass(frozen=True)
class Section03SqlParameters:
    drift_start_ts: str
    feature_cutoff_ts: str
    label_end_ts: str
    baseline_date: str
    psi_warning: float
    psi_alert: float
    psi_epsilon: float = 1e-6
    psi_quantile_bins: int = 10

    def __post_init__(self) -> None:
        for name in ("drift_start_ts", "feature_cutoff_ts", "label_end_ts", "baseline_date"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("psi_warning", "psi_alert", "psi_epsilon"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not 0 < self.psi_epsilon < 1:
            raise ValueError("psi_epsilon must be between 0 and 1")
        if isinstance(self.psi_quantile_bins, bool) or self.psi_quantile_bins < 2:
            raise ValueError("psi_quantile_bins must be at least 2")

    @classmethod
    def from_generator_config(cls, config: object) -> "Section03SqlParameters":
        from vina_bim_shop.generators.drift import resolve_drift_window

        window = resolve_drift_window(config)

        def utc_iso(value: object) -> str:
            rendered = value.isoformat()  # type: ignore[union-attr]
            if rendered.endswith("+00:00"):
                return rendered[:-6] + "Z"
            return rendered if rendered.endswith("Z") else rendered + "Z"

        return cls(
            drift_start_ts=utc_iso(window.drift_start_ts),
            feature_cutoff_ts=utc_iso(window.feature_cutoff_ts),
            label_end_ts=utc_iso(window.label_end_ts),
            baseline_date=window.baseline_date.isoformat(),  # type: ignore[union-attr]
            psi_warning=config.drift.psi_warning,  # type: ignore[union-attr]
            psi_alert=config.drift.psi_alert,  # type: ignore[union-attr]
        )


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def category_cost_rate_sql(expression: str) -> str:
    return f"""case
  when {expression} = 'FMCG' then 0.72
  when {expression} = 'ELHA' then 0.82
  when {expression} = 'Fashion' then 0.55
  when {expression} = 'Home & Living' then 0.62
  else 0.65
end"""


def _legacy_ordered_gold_queries() -> list[tuple[str, str]]:
    category_rate = category_cost_rate_sql("category")
    item_category_rate = category_cost_rate_sql("oi.primary_category")
    return [
        (
            "dim_customer",
            """
select
  row_number() over (order by customer_id) as customer_key,
  customer_id,
  anonymous_id,
  signup_ts,
  country,
  region,
  city,
  city_code,
  segment,
  marketing_opt_in,
  preferred_device,
  acquisition_channel,
  created_ts,
  created_ts as valid_from_ts,
  cast(null as timestamp) as valid_to_ts,
  true as is_current
from stg_customers
""",
        ),
        (
            "dim_seller",
            """
select
  row_number() over (order by seller_id) as seller_key,
  seller_id,
  seller_name,
  seller_tier,
  primary_category,
  city,
  region,
  seller_rating,
  fulfillment_speed_days,
  inventory_reliability,
  price_band,
  is_official_store,
  created_ts,
  created_ts as valid_from_ts,
  cast(null as timestamp) as valid_to_ts,
  true as is_current
from stg_sellers
""",
        ),
        (
            "dim_product",
            """
select
  row_number() over (order by p.product_id) as product_key,
  p.product_id,
  s.seller_key,
  p.seller_id,
  p.primary_category,
  p.primary_subcategory,
  coalesce(p.brand, 'unknown') as brand,
  p.product_name,
  p.base_price,
  p.price_band,
  p.is_active,
  p.fulfillment_channel,
  p.category_attributes,
  p.created_ts,
  p.created_ts as valid_from_ts,
  cast(null as timestamp) as valid_to_ts,
  true as is_current
from stg_products p
left join dim_seller s
  on p.seller_id = s.seller_id
""",
        ),
        (
            "dim_category",
            f"""
with categories as (
  select distinct category, subcategory
  from stg_product_category_map
)
select
  row_number() over (order by category, subcategory) as category_key,
  category,
  subcategory,
  {category_rate} as category_cost_rate
from categories
""",
        ),
        (
            "dim_date",
            """
with dates as (
  select cast(order_timestamp as date) as calendar_date from stg_orders
  union
  select cast(payment_timestamp as date) as calendar_date from stg_payments
  union
  select cast(created_ts as date) as calendar_date from stg_shipments
  union
  select cast(snapshot_ts as date) as calendar_date from stg_inventory_snapshots
)
select
  cast(date_format(calendar_date, 'yyyyMMdd') as int) as date_key,
  calendar_date,
  case when dayofweek(calendar_date) = 1 then 0 else dayofweek(calendar_date) - 1 end as day_of_week,
  month(calendar_date) as month,
  year(calendar_date) as year,
  dayofweek(calendar_date) in (1, 7) as is_weekend
from dates
where calendar_date is not null
""",
        ),
        (
            "dim_payment_method",
            """
select
  row_number() over (order by payment_method) as payment_method_key,
  payment_method
from (
  select distinct payment_method
  from stg_payments
  where payment_method is not null
)
""",
        ),
        (
            "dim_order_status",
            """
select
  row_number() over (order by status) as order_status_key,
  status as order_status
from (
  select distinct status
  from stg_orders
  where status is not null
)
""",
        ),
        (
            "dim_shipment_status",
            """
select
  row_number() over (order by shipment_status) as shipment_status_key,
  shipment_status
from (
  select distinct shipment_status
  from stg_shipments
  where shipment_status is not null
)
""",
        ),
        (
            "dim_shipping_method",
            """
select
  row_number() over (order by coalesce(shipping_method, 'unknown')) as shipping_method_key,
  coalesce(shipping_method, 'unknown') as shipping_method
from (
  select distinct shipping_method
  from stg_shipments
)
""",
        ),
        (
            "dim_promotion",
            """
with promotions as (
  select
    promotion_id,
    promotion_name,
    funding_type,
    funding_detail,
    seller_id,
    category,
    discount_rate,
    platform_funding_share,
    seller_funding_share,
    promotion_start_ts,
    promotion_end_ts,
    created_ts
  from stg_promotions
),
no_promotion as (
  select
    'NO_PROMOTION' as promotion_id,
    'No promotion applied' as promotion_name,
    'none' as funding_type,
    cast(null as string) as funding_detail,
    cast(null as string) as seller_id,
    'none' as category,
    0.0 as discount_rate,
    0.0 as platform_funding_share,
    0.0 as seller_funding_share,
    cast(null as timestamp) as promotion_start_ts,
    cast(null as timestamp) as promotion_end_ts,
    cast(null as timestamp) as created_ts
),
unioned as (
  select * from promotions
  union all
  select * from no_promotion
)
select
  row_number() over (order by promotion_id) as promotion_key,
  promotion_id,
  promotion_name,
  funding_type,
  funding_detail,
  seller_id,
  category,
  discount_rate,
  platform_funding_share,
  seller_funding_share,
  promotion_start_ts,
  promotion_end_ts,
  created_ts
from unioned
""",
        ),
        (
            "bridge_product_category",
            """
select
  p.product_key,
  p.product_id,
  c.category_key,
  m.category,
  m.subcategory,
  m.is_primary,
  m.assigned_ts
from stg_product_category_map m
join dim_product p
  on m.product_id = p.product_id
join dim_category c
  on m.category = c.category
 and m.subcategory = c.subcategory
""",
        ),
        (
            "fact_order",
            """
with payment_rollup as (
  select
    order_id,
    max(case when payment_status = 'success' then 1 else 0 end) = 1 as has_successful_payment,
    count(*) as payment_attempt_count
  from stg_payments
  group by 1
)
select
  row_number() over (order by o.order_id) as order_key,
  o.order_id,
  c.customer_key,
  cast(date_format(cast(o.order_timestamp as date), 'yyyyMMdd') as int) as order_date_key,
  os.order_status_key,
  o.customer_id,
  o.session_id,
  o.anonymous_id,
  o.order_timestamp,
  o.created_ts,
  o.primary_category,
  o.status as order_status,
  o.shipping_city,
  o.shipping_region,
  o.shipping_method,
  o.fulfillment_channel,
  o.promotion_id,
  o.coupon_code,
  o.item_count,
  o.order_gross_amount,
  o.order_discount_amount,
  o.order_net_amount,
  coalesce(p.has_successful_payment, false) as has_successful_payment,
  o.status = 'paid' and coalesce(p.has_successful_payment, false) as is_paid_order,
  case when o.status = 'paid' and coalesce(p.has_successful_payment, false) then o.order_net_amount else 0 end as official_paid_revenue,
  case when o.status = 'paid' and coalesce(p.has_successful_payment, false) then o.order_gross_amount else 0 end as gross_merchandise_value,
  coalesce(p.payment_attempt_count, 0) as payment_attempt_count
from stg_orders o
left join dim_customer c
  on o.customer_id = c.customer_id
left join dim_order_status os
  on o.status = os.order_status
left join payment_rollup p
  on o.order_id = p.order_id
""",
        ),
        (
            "fact_order_item",
            f"""
with payment_rollup as (
  select
    order_id,
    max(case when payment_status = 'success' then 1 else 0 end) = 1 as has_successful_payment
  from stg_payments
  group by 1
)
select
  row_number() over (order by oi.order_item_id) as order_item_key,
  oi.order_item_id,
  oi.order_id,
  fo.order_key,
  fo.customer_key,
  p.product_key,
  c.category_key,
  pr.promotion_key,
  cast(date_format(cast(o.order_timestamp as date), 'yyyyMMdd') as int) as order_date_key,
  oi.product_id,
  oi.seller_id,
  oi.primary_category,
  oi.primary_subcategory,
  oi.quantity,
  oi.unit_price,
  oi.gross_amount,
  oi.discount_amount,
  oi.net_amount,
  {item_category_rate} as category_cost_rate,
  case when o.status = 'paid' and coalesce(pay.has_successful_payment, false) then oi.net_amount else 0 end as line_paid_revenue,
  case when o.status = 'paid' and coalesce(pay.has_successful_payment, false) then oi.gross_amount else 0 end as line_gmv,
  case when o.status = 'paid' and coalesce(pay.has_successful_payment, false) then oi.net_amount * {item_category_rate} else 0 end as estimated_cost,
  case when o.status = 'paid' and coalesce(pay.has_successful_payment, false) then oi.net_amount * (1 - {item_category_rate}) else 0 end as estimated_margin,
  oi.promotion_id,
  oi.created_ts
from stg_order_items oi
join stg_orders o
  on oi.order_id = o.order_id
left join payment_rollup pay
  on oi.order_id = pay.order_id
left join fact_order fo
  on oi.order_id = fo.order_id
left join dim_product p
  on oi.product_id = p.product_id
left join dim_category c
  on oi.primary_category = c.category
 and oi.primary_subcategory = c.subcategory
left join dim_promotion pr
  on coalesce(oi.promotion_id, 'NO_PROMOTION') = pr.promotion_id
""",
        ),
        (
            "fact_payment_attempt",
            """
select
  row_number() over (order by p.payment_id) as payment_attempt_key,
  p.payment_id,
  p.order_id,
  fo.order_key,
  c.customer_key,
  cast(date_format(cast(p.payment_timestamp as date), 'yyyyMMdd') as int) as payment_date_key,
  pm.payment_method_key,
  p.customer_id,
  p.payment_timestamp,
  p.created_ts,
  p.payment_method,
  p.amount,
  p.payment_status,
  p.payment_status = 'success' as is_payment_success,
  p.payment_status = 'failed' as is_payment_failed,
  p.failure_reason
from stg_payments p
left join fact_order fo
  on p.order_id = fo.order_id
left join dim_customer c
  on p.customer_id = c.customer_id
left join dim_payment_method pm
  on p.payment_method = pm.payment_method
""",
        ),
        (
            "fact_shipment",
            """
select
  row_number() over (order by s.shipment_id) as shipment_key,
  s.shipment_id,
  s.order_id,
  fo.order_key,
  c.customer_key,
  ss.shipment_status_key,
  sm.shipping_method_key,
  cast(date_format(cast(s.created_ts as date), 'yyyyMMdd') as int) as shipment_created_date_key,
  s.customer_id,
  s.shipping_city,
  s.shipping_region,
  coalesce(s.shipping_method, 'unknown') as shipping_method,
  s.shipment_status,
  s.shipment_status = 'delayed' as is_delivery_delayed,
  s.shipment_status = 'blocked_payment_failed' as is_payment_blocked,
  s.handoff_ts,
  s.estimated_delivery_ts,
  s.created_ts
from stg_shipments s
left join fact_order fo
  on s.order_id = fo.order_id
left join dim_customer c
  on s.customer_id = c.customer_id
left join dim_shipment_status ss
  on s.shipment_status = ss.shipment_status
left join dim_shipping_method sm
  on coalesce(s.shipping_method, 'unknown') = sm.shipping_method
""",
        ),
        (
            "fact_inventory_snapshot",
            """
select
  row_number() over (order by i.snapshot_id) as inventory_snapshot_key,
  i.snapshot_id,
  p.product_key,
  s.seller_key,
  cast(date_format(cast(i.snapshot_ts as date), 'yyyyMMdd') as int) as snapshot_date_key,
  i.product_id,
  i.seller_id,
  i.snapshot_ts,
  i.stock_on_hand,
  i.reserved_stock,
  i.stock_on_hand - i.reserved_stock as available_stock
from stg_inventory_snapshots i
left join dim_product p
  on i.product_id = p.product_id
left join dim_seller s
  on i.seller_id = s.seller_id
""",
        ),
        (
            "fact_promotion_application",
            """
select
  row_number() over (order by oi.order_item_id) as promotion_application_key,
  oi.order_item_id,
  oi.order_id,
  fo.order_key,
  fo.customer_key,
  pr.promotion_key,
  oi.promotion_id,
  oi.gross_amount,
  oi.discount_amount,
  oi.discount_amount * coalesce(pr.platform_funding_share, 0.0) as platform_discount_amount,
  oi.discount_amount * coalesce(pr.seller_funding_share, 1.0) as seller_discount_amount,
  pr.funding_type,
  pr.platform_funding_share,
  pr.seller_funding_share
from stg_order_items oi
join fact_order fo
  on oi.order_id = fo.order_id
left join dim_promotion pr
  on oi.promotion_id = pr.promotion_id
where oi.promotion_id is not null
""",
        ),
        (
            "feat_customer_90d",
            """
with customer_orders as (
  select
    fo.customer_id,
    max(fo.order_timestamp) as event_timestamp,
    count(*) as f_customer_total_orders_90d,
    sum(fo.official_paid_revenue) as f_customer_paid_revenue_90d,
    avg(nullif(fo.official_paid_revenue, 0)) as f_customer_avg_order_value_90d,
    count(distinct fo.primary_category) as f_customer_distinct_categories_90d,
    max(fo.created_ts) as created
  from fact_order fo
  group by 1
)
select
  customer_id,
  event_timestamp,
  coalesce(f_customer_total_orders_90d, 0) as f_customer_total_orders_90d,
  coalesce(f_customer_paid_revenue_90d, 0) as f_customer_paid_revenue_90d,
  coalesce(f_customer_avg_order_value_90d, 0) as f_customer_avg_order_value_90d,
  coalesce(f_customer_distinct_categories_90d, 0) as f_customer_distinct_categories_90d,
  created
from customer_orders
where customer_id is not null
""",
        ),
        (
            "feat_stream_60m",
            """
select
  customer_id,
  date_trunc('hour', event_timestamp) as event_timestamp,
  sum(case when event_type = 'product_viewed' then 1 else 0 end) as f_stream_views_60m,
  sum(case when event_type = 'add_to_cart' then 1 else 0 end) as f_stream_add_to_cart_60m,
  sum(case when event_type = 'checkout_started' then 1 else 0 end) as f_stream_checkout_started_60m,
  sum(case when event_type = 'order_placed' then 1 else 0 end) as f_stream_order_placed_60m,
  case
    when sum(case when event_type = 'add_to_cart' then 1 else 0 end) > 0
    then cast(sum(case when event_type = 'order_placed' then 1 else 0 end) as double)
       / sum(case when event_type = 'add_to_cart' then 1 else 0 end)
    else 0
  end as f_stream_cart_to_purchase_ratio_60m,
  max(created_ts) as created
from stg_commerce_events
where customer_id is not null
group by 1, 2
""",
        ),
        (
            "feat_customer_unified",
            """
with latest_stream as (
  select *
  from (
    select
      *,
      row_number() over (partition by customer_id order by event_timestamp desc) as rn
    from feat_stream_60m
  )
  where rn = 1
)
select
  c.customer_id,
  greatest(c.event_timestamp, coalesce(s.event_timestamp, c.event_timestamp)) as event_timestamp,
  c.f_customer_total_orders_90d,
  c.f_customer_paid_revenue_90d,
  c.f_customer_avg_order_value_90d,
  c.f_customer_distinct_categories_90d,
  coalesce(s.f_stream_views_60m, 0) as f_stream_views_60m,
  coalesce(s.f_stream_add_to_cart_60m, 0) as f_stream_add_to_cart_60m,
  coalesce(s.f_stream_checkout_started_60m, 0) as f_stream_checkout_started_60m,
  coalesce(s.f_stream_order_placed_60m, 0) as f_stream_order_placed_60m,
  coalesce(s.f_stream_cart_to_purchase_ratio_60m, 0) as f_stream_cart_to_purchase_ratio_60m,
  greatest(c.created, coalesce(s.created, c.created)) as created
from feat_customer_90d c
left join latest_stream s
  on c.customer_id = s.customer_id
""",
        ),
        (
            "obt_order_performance",
            """
with item_rollup as (
  select
    order_id,
    sum(quantity) as total_quantity,
    sum(estimated_cost) as estimated_cost,
    sum(estimated_margin) as estimated_margin,
    count(distinct product_id) as distinct_products,
    count(distinct seller_id) as distinct_sellers
  from fact_order_item
  group by 1
),
payment_rollup as (
  select
    order_id,
    max(payment_timestamp) as last_payment_ts,
    max(case when is_payment_success then payment_method end) as successful_payment_method,
    sum(case when is_payment_success then 1 else 0 end) as successful_payment_attempts,
    count(*) as payment_attempts
  from fact_payment_attempt
  group by 1
),
shipment_rollup as (
  select
    order_id,
    max(shipment_status) as shipment_status,
    max(case when is_delivery_delayed then 1 else 0 end) = 1 as is_delivery_delayed,
    max(case when is_payment_blocked then 1 else 0 end) = 1 as is_payment_blocked
  from fact_shipment
  group by 1
)
select
  fo.order_id,
  fo.order_timestamp,
  fo.customer_id,
  dc.segment,
  dc.city as customer_city,
  fo.primary_category,
  fo.order_status,
  fo.shipping_city,
  fo.shipping_region,
  fo.shipping_method,
  fo.promotion_id,
  fo.coupon_code,
  fo.item_count,
  coalesce(ir.total_quantity, 0) as total_quantity,
  coalesce(ir.distinct_products, 0) as distinct_products,
  coalesce(ir.distinct_sellers, 0) as distinct_sellers,
  fo.order_gross_amount,
  fo.order_discount_amount,
  fo.order_net_amount,
  fo.official_paid_revenue,
  fo.gross_merchandise_value,
  coalesce(ir.estimated_cost, 0) as estimated_cost,
  coalesce(ir.estimated_margin, 0) as estimated_margin,
  fo.has_successful_payment,
  fo.is_paid_order,
  coalesce(pr.payment_attempts, 0) as payment_attempts,
  coalesce(pr.successful_payment_attempts, 0) as successful_payment_attempts,
  pr.successful_payment_method,
  pr.last_payment_ts,
  sr.shipment_status,
  coalesce(sr.is_delivery_delayed, false) as is_delivery_delayed,
  coalesce(sr.is_payment_blocked, false) as is_payment_blocked
from fact_order fo
left join dim_customer dc
  on fo.customer_key = dc.customer_key
left join item_rollup ir
  on fo.order_id = ir.order_id
left join payment_rollup pr
  on fo.order_id = pr.order_id
left join shipment_rollup sr
  on fo.order_id = sr.order_id
""",
        ),
        (
            "agg_hourly_reconciled_kpi",
            """
with order_hourly as (
  select
    date_trunc('hour', order_timestamp) as metric_hour,
    count(*) as order_count,
    sum(case when is_paid_order then 1 else 0 end) as paid_order_count,
    sum(order_gross_amount) as gross_order_amount,
    sum(order_discount_amount) as discount_amount,
    sum(official_paid_revenue) as official_paid_revenue,
    sum(gross_merchandise_value) as gross_merchandise_value,
    sum(estimated_cost) as estimated_cost,
    sum(estimated_margin) as estimated_margin,
    sum(case when order_status = 'payment_failed' then 1 else 0 end) as cancelled_or_failed_order_count
  from obt_order_performance
  group by 1
),
payment_hourly as (
  select
    date_trunc('hour', payment_timestamp) as metric_hour,
    count(*) as payment_attempt_count,
    sum(case when is_payment_success then 1 else 0 end) as payment_success_count
  from fact_payment_attempt
  group by 1
),
shipment_hourly as (
  select
    date_trunc('hour', created_ts) as metric_hour,
    count(*) as shipment_count,
    sum(case when is_delivery_delayed then 1 else 0 end) as delayed_shipment_count
  from fact_shipment
  group by 1
),
event_hourly as (
  select
    date_trunc('hour', event_timestamp) as metric_hour,
    sum(case when event_type = 'checkout_started' then 1 else 0 end) as checkout_started_count,
    sum(case when event_type = 'order_placed' then 1 else 0 end) as order_placed_event_count
  from stg_commerce_events
  group by 1
)
select
  o.metric_hour,
  o.order_count,
  o.paid_order_count,
  o.gross_order_amount,
  o.discount_amount,
  o.official_paid_revenue,
  o.gross_merchandise_value,
  o.estimated_cost,
  o.estimated_margin,
  case when o.paid_order_count > 0 then o.official_paid_revenue / o.paid_order_count else 0 end as average_order_value,
  o.cancelled_or_failed_order_count,
  case when o.order_count > 0 then cast(o.cancelled_or_failed_order_count as double) / o.order_count else 0 end as cancellation_rate,
  coalesce(p.payment_attempt_count, 0) as payment_attempt_count,
  coalesce(p.payment_success_count, 0) as payment_success_count,
  case when coalesce(p.payment_attempt_count, 0) > 0 then cast(p.payment_success_count as double) / p.payment_attempt_count else 0 end as payment_success_rate,
  coalesce(s.shipment_count, 0) as shipment_count,
  coalesce(s.delayed_shipment_count, 0) as delayed_shipment_count,
  case when coalesce(s.shipment_count, 0) > 0 then cast(s.delayed_shipment_count as double) / s.shipment_count else 0 end as delivery_delay_rate,
  coalesce(e.checkout_started_count, 0) as checkout_started_count,
  coalesce(e.order_placed_event_count, 0) as order_placed_event_count,
  case when coalesce(e.checkout_started_count, 0) > 0 then cast(e.order_placed_event_count as double) / e.checkout_started_count else 0 end as conversion_rate
from order_hourly o
left join payment_hourly p using (metric_hour)
left join shipment_hourly s using (metric_hour)
left join event_hourly e using (metric_hour)
""",
        ),
    ]


def _section03_feature_queries(parameters: Section03SqlParameters) -> list[tuple[str, str]]:
    cutoff = _sql_string(parameters.feature_cutoff_ts)
    label_end = _sql_string(parameters.label_end_ts)
    baseline = _sql_string(parameters.baseline_date)
    drift_start = _sql_string(parameters.drift_start_ts)
    psi_warning = repr(float(parameters.psi_warning))
    psi_alert = repr(float(parameters.psi_alert))
    psi_epsilon = repr(float(parameters.psi_epsilon))
    psi_quantile_bins = str(int(parameters.psi_quantile_bins))
    common_parameters = f"""
with parameters as (
  select
    cast({drift_start} as timestamp) as drift_start_ts,
    cast({cutoff} as timestamp) as feature_cutoff_ts,
    cast({label_end} as timestamp) as label_end_ts,
    cast({baseline} as date) as baseline_date,
    cast({psi_warning} as double) as psi_warning,
    cast({psi_alert} as double) as psi_alert,
    cast({psi_epsilon} as double) as psi_epsilon,
    cast({psi_quantile_bins} as int) as psi_quantile_bins,
    datediff(cast({label_end} as date), cast({cutoff} as date)) as window_days
),"""

    return [
        (
            "feat_customer_90d",
            common_parameters
            + """
eligible_customers as (
  select customer.customer_id
  from dim_customer customer
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
  from fact_order orders
  cross join parameters p
  where orders.customer_id is not null
    and orders.order_timestamp > p.feature_cutoff_ts - interval 90 days
    and orders.order_timestamp <= p.feature_cutoff_ts
    and orders.created_ts <= p.feature_cutoff_ts
),
successful_orders as (
  select distinct payment.order_id
  from fact_payment_attempt payment
  cross join parameters p
  where payment.is_payment_success
    and payment.payment_timestamp <= p.feature_cutoff_ts
    and payment.created_ts <= p.feature_cutoff_ts
),
customer_orders as (
  select
    customer.customer_id,
    count(orders.order_id) as f_customer_total_orders_90d,
    sum(case when paid.order_id is not null then orders.order_net_amount else 0 end) as f_customer_paid_revenue_90d,
    avg(case when paid.order_id is not null then orders.order_net_amount end) as f_customer_avg_order_value_90d,
    count(distinct orders.primary_category) as f_customer_distinct_categories_90d
  from eligible_customers customer
  left join eligible_orders orders
    on customer.customer_id = orders.customer_id
  left join successful_orders paid
    on orders.order_id = paid.order_id
  group by customer.customer_id
)
select
  customer.customer_id,
  cast(p.feature_cutoff_ts as timestamp) as event_timestamp,
  coalesce(customer.f_customer_total_orders_90d, 0) as f_customer_total_orders_90d,
  coalesce(customer.f_customer_paid_revenue_90d, cast(0.0 as double)) as f_customer_paid_revenue_90d,
  coalesce(customer.f_customer_avg_order_value_90d, cast(0.0 as double)) as f_customer_avg_order_value_90d,
  coalesce(customer.f_customer_distinct_categories_90d, 0) as f_customer_distinct_categories_90d,
  cast(p.feature_cutoff_ts as timestamp) as created
from customer_orders customer
cross join parameters p
""",
        ),
        (
            "feat_stream_60m",
            common_parameters
            + """
available_events as (
  select events.*
  from stg_commerce_events events
  cross join parameters p
  where events.customer_id is not null
    and events.event_timestamp > p.feature_cutoff_ts - interval 60 minutes
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
    then cast(sum(case when event_type = 'order_placed' then 1 else 0 end) as double)
       / sum(case when event_type = 'add_to_cart' then 1 else 0 end)
    else cast(0.0 as double)
  end as f_stream_cart_to_purchase_ratio_60m,
  max(created_ts) as created
from available_events
group by customer_id, date_trunc('hour', event_timestamp)
""",
        ),
        (
            "feat_customer_unified",
            common_parameters
            + """
latest_stream as (
  select
    customer_id,
    event_timestamp,
    f_stream_views_60m,
    f_stream_add_to_cart_60m,
    f_stream_checkout_started_60m,
    f_stream_order_placed_60m,
    f_stream_cart_to_purchase_ratio_60m,
    created
  from (
    select
      stream.*,
      row_number() over (
        partition by customer_id
        order by event_timestamp desc, created desc
      ) as rn
    from feat_stream_60m stream
  ) ranked
  where rn = 1
)
select
  customer.customer_id,
  cast(p.feature_cutoff_ts as timestamp) as event_timestamp,
  customer.f_customer_total_orders_90d,
  customer.f_customer_paid_revenue_90d,
  customer.f_customer_avg_order_value_90d,
  customer.f_customer_distinct_categories_90d,
  coalesce(stream.f_stream_views_60m, 0) as f_stream_views_60m,
  coalesce(stream.f_stream_add_to_cart_60m, 0) as f_stream_add_to_cart_60m,
  coalesce(stream.f_stream_checkout_started_60m, 0) as f_stream_checkout_started_60m,
  coalesce(stream.f_stream_order_placed_60m, 0) as f_stream_order_placed_60m,
  coalesce(stream.f_stream_cart_to_purchase_ratio_60m, cast(0.0 as double)) as f_stream_cart_to_purchase_ratio_60m,
  cast(p.feature_cutoff_ts as timestamp) as created
from feat_customer_90d customer
cross join parameters p
left join latest_stream stream
  on customer.customer_id = stream.customer_id
""",
        ),
        (
            "ml_customer_label",
            common_parameters
            + """
eligible_customers as (
  select customer.customer_id as id
  from dim_customer customer
  cross join parameters p
  where customer.customer_id is not null
    and customer.created_ts <= p.feature_cutoff_ts
),
positive_customers as (
  select distinct payment.customer_id as id
  from fact_payment_attempt payment
  cross join parameters p
  where payment.customer_id is not null
    and payment.is_payment_success
    and payment.payment_timestamp > p.feature_cutoff_ts
    and payment.payment_timestamp <= p.label_end_ts
    and payment.created_ts <= p.label_end_ts
)
select
  cast(customer.id as string) as id,
  cast(case when positive.id is not null then 1 else 0 end as int) as label
from eligible_customers customer
left join positive_customers positive
  on customer.id = positive.id
""",
        ),
        (
            "agg_feature_health_daily",
            common_parameters
            + """
fixed_cohort as (
  select customer.customer_id
  from dim_customer customer
  cross join parameters p
  where customer.customer_id is not null
    and customer.created_ts < cast(p.baseline_date as timestamp) + interval 1 day
),
monitoring_dates as (
  select explode(sequence(to_date(p.baseline_date), to_date(p.label_end_ts), interval 1 day)) as monitoring_date
  from parameters p
),
window_counts as (
  select
    dates.monitoring_date,
    customer.customer_id,
    count(orders.order_id) as feature_value
  from monitoring_dates dates
  cross join fixed_cohort customer
  cross join parameters p
  left join fact_order orders
    on customer.customer_id = orders.customer_id
    and orders.order_timestamp >= cast(date_sub(dates.monitoring_date, p.window_days - 1) as timestamp)
    and orders.order_timestamp < cast(dates.monitoring_date as timestamp) + interval 1 day
    and orders.created_ts < cast(dates.monitoring_date as timestamp) + interval 1 day
  group by dates.monitoring_date, customer.customer_id
),
baseline_ranked as (
  select
    feature_value,
    row_number() over (order by feature_value, customer_id) - 1 as value_index,
    count(*) over () as value_count
  from window_counts
  cross join parameters p
  where monitoring_date = p.baseline_date
),
quantile_positions as (
  select
    bin_index,
    (baseline.value_count - 1)
      * (cast(bin_index as double) / p.psi_quantile_bins) as position,
    baseline.value_count
  from (select distinct value_count from baseline_ranked) baseline
  cross join parameters p
  lateral view explode(sequence(0, p.psi_quantile_bins)) bins as bin_index
),
quantile_edges as (
  select distinct
    lower_value.feature_value
      + (position.position - floor(position.position))
        * (upper_value.feature_value - lower_value.feature_value) as edge
  from quantile_positions position
  join baseline_ranked lower_value
    on lower_value.value_index = cast(floor(position.position) as bigint)
  join baseline_ranked upper_value
    on upper_value.value_index = least(
      cast(floor(position.position) as bigint) + 1,
      position.value_count - 1
    )
),
bin_numbers as (
  select explode(sequence(0, edge_count)) as bin_index
  from (select count(*) as edge_count from quantile_edges) edges
),
binned_counts as (
  select
    binned.monitoring_date,
    binned.bin_index,
    count(*) as observation_count
  from (
    select
      counts.monitoring_date,
      counts.customer_id,
      count(edge.edge) as bin_index
    from window_counts counts
    left join quantile_edges edge
      on edge.edge < counts.feature_value
    group by counts.monitoring_date, counts.customer_id
  ) binned
  group by binned.monitoring_date, binned.bin_index
),
distribution_grid as (
  select
    dates.monitoring_date,
    bins.bin_index,
    coalesce(counts.observation_count, 0) as observation_count
  from monitoring_dates dates
  cross join bin_numbers bins
  left join binned_counts counts
    on dates.monitoring_date = counts.monitoring_date
    and bins.bin_index = counts.bin_index
),
smoothed_distributions as (
  select
    grid.monitoring_date,
    grid.bin_index,
    case
      when grid.observation_count = 0 then p.psi_epsilon
      else cast(grid.observation_count as double) / cohort.customer_count
    end as smoothed_probability
  from distribution_grid grid
  cross join parameters p
  cross join (select count(*) as customer_count from fixed_cohort) cohort
),
normalized_distributions as (
  select
    monitoring_date,
    bin_index,
    smoothed_probability
      / sum(smoothed_probability) over (partition by monitoring_date) as probability
  from smoothed_distributions
),
psi_by_date as (
  select
    current.monitoring_date,
    sum(
      (current.probability - baseline.probability)
      * ln(current.probability / baseline.probability)
    ) as psi_value
  from normalized_distributions current
  cross join parameters p
  join normalized_distributions baseline
    on baseline.monitoring_date = p.baseline_date
    and current.bin_index = baseline.bin_index
  group by current.monitoring_date
),
daily_metrics as (
  select
    monitoring_date,
    count(*) as customer_count,
    avg(feature_value) as mean_value,
    coalesce(stddev_pop(feature_value), cast(0.0 as double)) as stddev_value
  from window_counts
  group by monitoring_date
),
canonical as (
  select
    metrics.monitoring_date,
    p.baseline_date,
    p.window_days,
    metrics.customer_count,
    bround(metrics.mean_value, 12) as mean_value,
    bround(metrics.stddev_value, 12) as stddev_value,
    greatest(bround(psi.psi_value, 12), cast(0.0 as double)) as psi_vs_baseline,
    p.psi_warning,
    p.psi_alert
  from daily_metrics metrics
  join psi_by_date psi
    on metrics.monitoring_date = psi.monitoring_date
  cross join parameters p
)
select
  cast(monitoring_date as date) as monitoring_date,
  'f_customer_order_frequency_7d' as feature_name,
  cast(window_days as int) as window_days,
  cast(baseline_date as date) as baseline_date,
  cast(customer_count as bigint) as customer_count,
  cast(mean_value as double) as mean_value,
  cast(stddev_value as double) as stddev_value,
  cast(psi_vs_baseline as double) as psi_vs_baseline,
  case
    when psi_vs_baseline >= psi_alert then 'alert'
    when psi_vs_baseline >= psi_warning then 'warning'
    else 'stable'
  end as drift_status,
  psi_vs_baseline >= psi_warning as warning_flag,
  psi_vs_baseline >= psi_alert as alert_flag
from canonical
""",
        ),
        (
            "feature_drift_alerts",
            common_parameters
            + """
health as (
  select * from agg_feature_health_daily
)
select
  cast(health.monitoring_date as date) as alert_date,
  health.feature_name,
  cast(health.psi_vs_baseline as double) as psi_value,
  cast(p.psi_alert as double) as threshold,
  'Investigate customer_order_frequency drift' as action
from health
cross join parameters p
where health.psi_vs_baseline >= p.psi_alert
""",
        ),
        (
            "ml_customer_purchase_training",
            common_parameters.rstrip(",")
            + """
select
  cast(label.id as string) as id,
  cast(features.event_timestamp as timestamp) as event_timestamp,
  cast(label.label as int) as label,
  features.f_customer_total_orders_90d,
  features.f_customer_paid_revenue_90d,
  features.f_customer_avg_order_value_90d,
  features.f_customer_distinct_categories_90d,
  features.f_stream_views_60m,
  features.f_stream_add_to_cart_60m,
  features.f_stream_checkout_started_60m,
  features.f_stream_order_placed_60m,
  features.f_stream_cart_to_purchase_ratio_60m,
  cast(features.created as timestamp) as created
from ml_customer_label label
inner join feat_customer_unified features
  on label.id = features.customer_id
""",
        ),
    ]


def ordered_core_gold_queries() -> list[tuple[str, str]]:
    """Return every non-DP3 Gold query in deterministic dependency order."""
    return [
        (table_name, query)
        for table_name, query in _legacy_ordered_gold_queries()
        if table_name not in DP3_GOLD_TABLES
    ]


def ordered_feature_queries(parameters: Section03SqlParameters) -> list[tuple[str, str]]:
    """Return the seven parameterized Section 03 Gold queries in DP3 order."""
    queries = _section03_feature_queries(parameters)
    assert tuple(table_name for table_name, _query in queries) == DP3_GOLD_TABLES
    return queries


def ordered_gold_queries(parameters: Section03SqlParameters) -> list[tuple[str, str]]:
    """Return the core Gold queries followed by the parameterized DP3 queries."""
    return [*ordered_core_gold_queries(), *ordered_feature_queries(parameters)]
