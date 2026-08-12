locals {
  topic22_required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudkms.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "monitoring.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "topic22" {
  for_each           = local.topic22_required_services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "gke" {
  source       = "../modules/gke"
  project_id   = var.project_id
  zone         = var.zone
  cluster_name = var.cluster_name
  depends_on   = [google_project_service.topic22]
}
module "artifact_registry" {
  source     = "../modules/artifact_registry"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.topic22]
}
module "gcs" {
  source      = "../modules/gcs"
  project_id  = var.project_id
  bucket_name = var.bucket_name
  region      = var.region
  kms_key_id  = module.kms.key_id
  depends_on  = [google_project_service.topic22, module.kms]
}
module "kms" {
  source     = "../modules/kms"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.topic22]
}
module "iam" {
  source      = "../modules/iam"
  project_id  = var.project_id
  bucket_name = var.bucket_name
  depends_on  = [google_project_service.topic22, module.gcs]
}
module "budget" {
  source              = "../modules/budget"
  billing_account_id  = var.billing_account_id
  project_id          = var.project_id
  notification_target = var.budget_notification_target
  budget_currency     = var.budget_currency
  trial_credit_vnd    = var.trial_credit_vnd
  depends_on          = [google_project_service.topic22]
}
