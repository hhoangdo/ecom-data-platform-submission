resource "google_container_cluster" "edai2" {
  name = var.cluster_name
  location = var.zone
  remove_default_node_pool = true
  initial_node_count = 1
  networking_mode = "VPC_NATIVE"
  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
}
resource "google_container_node_pool" "platform" {
  name = "platform"
  location = var.zone
  cluster = google_container_cluster.edai2.name
  node_count = 0
  node_config {
    machine_type = "e2-highmem-4"
    image_type = "COS_CONTAINERD"
  }
  autoscaling {
    min_node_count = 0
    max_node_count = 1
  }
}
resource "google_container_node_pool" "spot" {
  name = "spot"
  location = var.zone
  cluster = google_container_cluster.edai2.name
  node_count = 0
  node_config {
    machine_type = "e2-standard-8"
    image_type = "COS_CONTAINERD"
    spot = true
  }
  autoscaling {
    min_node_count = 0
    max_node_count = 2
  }
}
