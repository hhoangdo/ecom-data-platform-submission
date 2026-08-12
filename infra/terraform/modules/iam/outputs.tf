output "service_accounts" { value = [for account in google_service_account.workload_identity : account.email] }
output "workload_identity_bindings" {
  value = {
    for key, binding in google_service_account_iam_member.workload_identity : key => {
      ksa      = binding.member
      gsa      = google_service_account.workload_identity[key].email
      prefixes = local.workload_identity[key].prefixes
    }
  }
}
