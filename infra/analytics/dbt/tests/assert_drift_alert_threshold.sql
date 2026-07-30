with parameters as (
  select cast({{ var('psi_alert') }} as double) as psi_alert
),
expected as (
  select
    health.monitoring_date as alert_date,
    health.feature_name,
    health.psi_vs_baseline as psi_value,
    p.psi_alert as threshold,
    'Investigate customer_order_frequency drift' as action
  from {{ ref('agg_feature_health_daily') }} health
  cross join parameters p
  where health.psi_vs_baseline >= p.psi_alert
    and health.drift_status = 'alert'
    and health.alert_flag
),
differences as (
  select * from expected
  except
  select * from {{ ref('feature_drift_alerts') }}
),
unexpected as (
  select * from {{ ref('feature_drift_alerts') }}
  except
  select * from expected
)
select 'missing_or_wrong' as violation, * from differences
union all
select 'unexpected' as violation, * from unexpected
