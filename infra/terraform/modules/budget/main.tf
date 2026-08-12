data "google_project" "current" {
  project_id = var.project_id
}
locals {
  # Floor fractional VND so the applied budget never exceeds the normalized USD 240 envelope.
  budget_amount_vnd = floor(var.trial_credit_vnd * 240 / 300)
}
resource "google_billing_budget" "edai2" {
  billing_account = var.billing_account_id
  display_name    = "EDAI2 normalized USD 240 budget"
  amount {
    specified_amount {
      currency_code = var.budget_currency
      units         = tostring(local.budget_amount_vnd)
    }
  }
  budget_filter { projects = ["projects/${data.google_project.current.number}"] }
  dynamic "threshold_rules" {
    for_each = toset(["0.50", "0.75", "0.90", "1.00"])
    content { threshold_percent = tonumber(threshold_rules.value) }
  }
  all_updates_rule { monitoring_notification_channels = [var.notification_target] }
}
