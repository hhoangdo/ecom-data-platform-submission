resource "google_billing_budget" "edai2" {
  billing_account = var.billing_account_id
  display_name = "EDAI2 USD 240"
  amount {
    specified_amount {
      currency_code = "USD"
      units = "240"
    }
  }
  budget_filter { projects = ["projects/${var.project_id}"] }
  dynamic "threshold_rules" {
    for_each = toset(["0.50", "0.75", "0.90", "1.00"])
    content { threshold_percent = tonumber(threshold_rules.value) }
  }
  all_updates_rule { monitoring_notification_channels = [var.notification_target] }
}
