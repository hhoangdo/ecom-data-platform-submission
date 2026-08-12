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
variable "budget_currency" {
  type        = string
  description = "Operator-approved billing currency; Topic 22 uses VND with a separately evidenced USD normalization."
  validation {
    condition     = var.budget_currency == "VND"
    error_message = "The approved Topic 22 billing currency is VND."
  }
}
variable "trial_credit_vnd" {
  type        = number
  description = "Timestamped VND trial credit; Terraform floors trial_credit_vnd * 240 / 300 to keep the VND cap conservative."
  validation {
    condition     = var.trial_credit_vnd > 0
    error_message = "Trial credit must be positive."
  }
}
