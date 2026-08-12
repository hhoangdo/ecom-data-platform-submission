resource "google_kms_key_ring" "edai2" {
  name     = "edai2"
  location = var.region
}
resource "google_kms_crypto_key" "edai2" {
  name            = "edai2"
  key_ring        = google_kms_key_ring.edai2.id
  rotation_period = "7776000s"
}
data "google_storage_project_service_account" "gcs" {
  project = var.project_id
}
resource "google_kms_crypto_key_iam_member" "gcs_service_agent" {
  crypto_key_id = google_kms_crypto_key.edai2.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_storage_project_service_account.gcs.email_address}"
}
