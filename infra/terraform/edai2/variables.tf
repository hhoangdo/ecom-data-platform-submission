variable "project_id" { type = string }
variable "billing_account_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "zone" {
  type    = string
  default = "us-central1-a"
}
variable "cluster_name" {
  type    = string
  default = "edai2"
}
variable "bucket_name" { type = string }
variable "budget_notification_target" { type = string }
