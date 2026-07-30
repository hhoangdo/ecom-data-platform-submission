with parameters as (
  select
    cast('{{ var('drift_start_ts') }}' as timestamp) as drift_start_ts,
    cast('{{ var('feature_cutoff_ts') }}' as timestamp) as feature_cutoff_ts,
    cast('{{ var('label_end_ts') }}' as timestamp) as label_end_ts,
    cast('{{ var('baseline_date') }}' as date) as baseline_date,
    cast({{ var('psi_warning') }} as double) as psi_warning,
    cast({{ var('psi_alert') }} as double) as psi_alert,
    cast({{ var('psi_epsilon') }} as double) as psi_epsilon,
    cast({{ var('psi_quantile_bins') }} as integer) as psi_quantile_bins,
    cast(
      date_diff(
        'day',
        cast('{{ var('feature_cutoff_ts') }}' as date),
        cast('{{ var('label_end_ts') }}' as date)
      )
      as integer
    ) as window_days
),
fixed_cohort as (
  select customer.customer_id
  from {{ ref('dim_customer') }} customer
  cross join parameters p
  where customer.customer_id is not null
    and customer.created_ts < cast(p.baseline_date as timestamp) + interval '1 day'
),
monitoring_dates as (
  select cast(date_value as date) as monitoring_date
  from parameters p
  cross join unnest(
    generate_series(
      p.baseline_date,
      cast(p.label_end_ts as date),
      interval '1 day'
    )
  ) as generated(date_value)
),
window_counts as (
  select
    dates.monitoring_date,
    customer.customer_id,
    count(orders.order_id) as feature_value
  from monitoring_dates dates
  cross join fixed_cohort customer
  cross join parameters p
  left join {{ ref('fact_order') }} orders
    on customer.customer_id = orders.customer_id
    and orders.order_timestamp >=
      cast(dates.monitoring_date as timestamp)
      - (p.window_days - 1) * interval '1 day'
    and orders.order_timestamp <
      cast(dates.monitoring_date as timestamp) + interval '1 day'
    and orders.created_ts <
      cast(dates.monitoring_date as timestamp) + interval '1 day'
  group by 1, 2
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
    bin.bin_index,
    (baseline.value_count - 1)
      * (cast(bin.bin_index as double) / p.psi_quantile_bins) as position,
    baseline.value_count
  from (
    select distinct value_count
    from baseline_ranked
  ) baseline
  cross join parameters p
  cross join range(0, p.psi_quantile_bins + 1) as bin(bin_index)
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
  select bin_index
  from (
    select count(*) as edge_count
    from quantile_edges
  ) edges
  cross join range(0, edges.edge_count + 1) as bins(bin_index)
),
binned_counts as (
  select
    counts.monitoring_date,
    (
      select count(*)
      from quantile_edges edge
      where edge.edge < counts.feature_value
    ) as bin_index,
    count(*) as observation_count
  from window_counts counts
  group by 1, 2
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
  cross join (
    select count(*) as customer_count
    from fixed_cohort
  ) cohort
),
normalized_distributions as (
  select
    monitoring_date,
    bin_index,
    smoothed_probability
      / sum(smoothed_probability) over (
        partition by monitoring_date
      ) as probability
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
  group by 1
),
daily_metrics as (
  select
    monitoring_date,
    count(*) as customer_count,
    avg(feature_value) as mean_value,
    coalesce(stddev_pop(feature_value), 0.0) as stddev_value
  from window_counts
  group by 1
),
canonical as (
  select
    metrics.monitoring_date,
    p.baseline_date,
    p.window_days,
    metrics.customer_count,
    round_even(metrics.mean_value, 12) as mean_value,
    round_even(metrics.stddev_value, 12) as stddev_value,
    greatest(round_even(psi.psi_value, 12), 0.0) as psi_vs_baseline,
    p.psi_warning,
    p.psi_alert
  from daily_metrics metrics
  join psi_by_date psi
    on metrics.monitoring_date = psi.monitoring_date
  cross join parameters p
)
select
  monitoring_date,
  'f_customer_order_frequency_7d' as feature_name,
  window_days,
  baseline_date,
  customer_count,
  mean_value,
  stddev_value,
  psi_vs_baseline,
  case
    when psi_vs_baseline >= psi_alert then 'alert'
    when psi_vs_baseline >= psi_warning then 'warning'
    else 'stable'
  end as drift_status,
  psi_vs_baseline >= psi_warning as warning_flag,
  psi_vs_baseline >= psi_alert as alert_flag
from canonical
