with normalized as (
  select
    event_id,
    event_type,
    event_topic,
    try_cast(schema_version as integer) as schema_version,
    try_cast(event_timestamp as timestamp) as event_timestamp,
    try_cast(created_ts as timestamp) as created_ts,
    try_cast(ingest_ts as timestamp) as ingest_ts,
    producer,
    {{ json_string('correlation_ids', '$.session_id') }} as session_id,
    {{ json_string('correlation_ids', '$.anonymous_id') }} as anonymous_id,
    {{ json_string('correlation_ids', '$.customer_id') }} as customer_id,
    coalesce(
      {{ json_string('correlation_ids', '$.product_id') }},
      {{ json_string('payload', '$.product_id') }}
    ) as product_id,
    coalesce(
      {{ json_string('correlation_ids', '$.order_id') }},
      {{ json_string('payload', '$.order_id') }}
    ) as order_id,
    {{ json_string('correlation_ids', '$.payment_id') }} as payment_id,
    {{ json_string('payload', '$.primary_category') }} as primary_category,
    {{ json_string('payload', '$.device_type') }} as device_type,
    {{ json_string('payload', '$.source') }} as source,
    {{ json_string('payload', '$.order_status') }} as order_status,
    {{ json_double('payload', '$.order_net_amount') }} as order_net_amount,
    {{ json_string('payload', '$.payment_method') }} as payment_method,
    {{ json_double('payload', '$.amount') }} as payment_amount,
    {{ json_string('payload', '$.failure_reason') }} as failure_reason,
    payload
  from {{ ref('raw_kafka_commerce_events') }}
),
ranked as (
  select
    *,
    dense_rank() over (
      partition by event_id
      order by
        created_ts desc nulls last,
        ingest_ts desc nulls last,
        event_timestamp desc nulls last
    ) as winner_rank
  from normalized
),
winner_fingerprints as (
  select
    event_id,
    md5(
      concat_ws(
        '|',
        coalesce(event_type, ''),
        coalesce(event_topic, ''),
        coalesce(cast(schema_version as varchar), ''),
        coalesce(cast(event_timestamp as varchar), ''),
        coalesce(cast(created_ts as varchar), ''),
        coalesce(cast(ingest_ts as varchar), ''),
        coalesce(producer, ''),
        coalesce(session_id, ''),
        coalesce(anonymous_id, ''),
        coalesce(customer_id, ''),
        coalesce(product_id, ''),
        coalesce(order_id, ''),
        coalesce(payment_id, ''),
        coalesce(primary_category, ''),
        coalesce(device_type, ''),
        coalesce(source, ''),
        coalesce(order_status, ''),
        coalesce(cast(order_net_amount as varchar), ''),
        coalesce(payment_method, ''),
        coalesce(cast(payment_amount as varchar), ''),
        coalesce(failure_reason, ''),
        coalesce(cast(to_json(payload) as varchar), '')
      )
    ) as normalized_fingerprint
  from ranked
  where winner_rank = 1
)
select event_id
from winner_fingerprints
group by event_id
having count(distinct normalized_fingerprint) > 1
