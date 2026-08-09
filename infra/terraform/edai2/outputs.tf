output "cluster_id" { value = module.gke.cluster_id }
output "bucket_name" { value = module.gcs.bucket_name }
output "kms_key_id" { value = module.kms.key_id }
output "artifact_registry_repositories" { value = module.artifact_registry.repositories }
output "budget_id" { value = module.budget.budget_id }
