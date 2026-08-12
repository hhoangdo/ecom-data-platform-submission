terraform {
  required_version = "~> 1.15.0"
  # Runtime supplies the untracked bucket/prefix backend config; local verification uses -backend=false.
  backend "gcs" {}
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}
