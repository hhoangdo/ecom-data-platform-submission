output "repositories" { value = [for repository in google_artifact_registry_repository.images : "${repository.location}-docker.pkg.dev/${repository.project}/${repository.repository_id}"] }
