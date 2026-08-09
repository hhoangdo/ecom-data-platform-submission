resource "google_kms_key_ring" "edai2" {
  name = "edai2"
  location = var.region
}
resource "google_kms_crypto_key" "edai2" {
  name = "edai2"
  key_ring = google_kms_key_ring.edai2.id
  rotation_period = "7776000s"
}
