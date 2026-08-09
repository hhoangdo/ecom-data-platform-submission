output "service_accounts" { value = [for account in google_service_account.workloads : account.email] }
