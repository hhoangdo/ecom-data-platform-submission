locals {
  workload_identity = {
    "retrieval"   = { account_id = "edai2-retrieval", ksa = "edai2-retrieval-agent", prefixes = ["model-cache/"] }
    "drift"       = { account_id = "edai2-drift", ksa = "edai2-drift-agent", prefixes = ["langfuse-events/"] }
    "coordinator" = { account_id = "edai2-coordinator", ksa = "edai2-coordinator", prefixes = ["agent-substrate/", "backups/"] }
    "workers"     = { account_id = "edai2-workers", ksa = "edai2-worker", prefixes = ["airflow-logs/"] }
  }
  prefix_access = merge([for workload, identity in local.workload_identity : {
    for prefix in identity.prefixes : prefix => workload
  }]...)
}
resource "google_service_account" "workload_identity" {
  for_each     = local.workload_identity
  account_id   = each.value.account_id
  display_name = "EDAI2 workload ${each.key}"
}
resource "google_storage_bucket_iam_member" "prefix_access" {
  for_each = local.prefix_access
  bucket   = var.bucket_name
  role     = "roles/storage.objectUser"
  member   = "serviceAccount:${google_service_account.workload_identity[each.value].email}"
  condition {
    title      = "prefix-${replace(trimsuffix(each.key, "/"), "_", "-")}"
    expression = "resource.name.startsWith('projects/_/buckets/${var.bucket_name}/objects/${each.key}')"
  }
}
resource "google_service_account_iam_member" "workload_identity" {
  for_each           = local.workload_identity
  service_account_id = google_service_account.workload_identity[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[edai2:${each.value.ksa}]"
}
