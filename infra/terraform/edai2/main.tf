module "gke" {
  source       = "../modules/gke"
  project_id   = var.project_id
  zone         = var.zone
  cluster_name = var.cluster_name
}
module "artifact_registry" {
  source     = "../modules/artifact_registry"
  project_id = var.project_id
  region     = var.region
}
module "gcs" {
  source      = "../modules/gcs"
  project_id  = var.project_id
  bucket_name = var.bucket_name
  region      = var.region
}
module "kms" {
  source     = "../modules/kms"
  project_id = var.project_id
  region     = var.region
}
module "iam" {
  source      = "../modules/iam"
  project_id  = var.project_id
  bucket_name = var.bucket_name
}
module "budget" {
  source              = "../modules/budget"
  billing_account_id  = var.billing_account_id
  project_id          = var.project_id
  notification_target = var.budget_notification_target
}
