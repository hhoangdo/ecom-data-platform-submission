resource "google_storage_bucket" "edai2" {
  name = var.bucket_name
  location = var.region
  uniform_bucket_level_access = true
  versioning { enabled = true }
  lifecycle_rule {
    condition {
      age = 7
      matches_prefix = ["langfuse-events/", "agent-substrate/"]
    }
    action { type = "Delete" }
  }
  lifecycle_rule {
    condition {
      age = 90
      matches_prefix = ["backups/", "model-cache/", "airflow-logs/"]
    }
    action { type = "Delete" }
  }
}
