output "bucket_name" { value = google_storage_bucket.edai2.name }
output "prefixes" { value = ["model-cache/", "agent-substrate/", "langfuse-events/", "airflow-logs/", "backups/"] }
