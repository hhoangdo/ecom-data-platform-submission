output "repositories" { value = [for repository in google_artifact_registry_repository.images : repository.id] }
