output "cluster_id" { value = google_container_cluster.edai2.id }
output "zone" { value = google_container_cluster.edai2.location }
output "node_pool_names" { value = [google_container_node_pool.platform.name, google_container_node_pool.spot.name] }
