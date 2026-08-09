locals {
  repositories = toset(["edai2-rag-index", "edai2-retrieval-agent", "edai2-drift-agent", "edai2-coordinator", "edai2-feast-offline-writer", "edai2-feast-online-writer"])
}
resource "google_artifact_registry_repository" "images" {
  for_each      = local.repositories
  location      = var.region
  repository_id = each.value
  format        = "DOCKER"
  docker_config { immutable_tags = true }
}
