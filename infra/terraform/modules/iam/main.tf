locals { prefixes = toset(["model-cache/", "agent-substrate/", "langfuse-events/", "airflow-logs/", "backups/"]) }
resource "google_service_account" "workloads" {
  for_each = local.prefixes
  account_id = "edai2-${replace(trimsuffix(each.value, "/"), "_", "-")}" 
  display_name = "EDAI2 ${each.value}"
}
resource "google_storage_bucket_iam_member" "prefix_reader" {
  for_each = local.prefixes
  bucket = var.bucket_name
  role = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.workloads[each.key].email}"
  condition {
    title = "prefix-${replace(trimsuffix(each.value, "/"), "_", "-")}"
    expression = "resource.name.startsWith('projects/_/buckets/${var.bucket_name}/objects/${each.value}')"
  }
}
