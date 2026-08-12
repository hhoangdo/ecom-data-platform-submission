output "budget_id" { value = google_billing_budget.edai2.name }
output "normalized_budget_usd" { value = 240 }
output "budget_amount_vnd" { value = local.budget_amount_vnd }
