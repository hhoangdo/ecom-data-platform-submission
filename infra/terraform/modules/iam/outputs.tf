output "service_accounts" { value = [for account in google_service_account.workload_identity : account.email] }
output "vault_service_account_email" { value = google_service_account.vault.email }
output "workload_identity_bindings" {
  value = {
    for key, binding in google_service_account_iam_member.workload_identity : key => {
      ksa      = binding.member
      gsa      = google_service_account.workload_identity[key].email
      prefixes = local.workload_identity[key].prefixes
    }
  }
}
output "atelet_workload_identity_binding" {
  value = {
    ksa      = google_service_account_iam_member.atelet_workload_identity.member
    gsa      = google_service_account.workload_identity["coordinator"].email
    prefixes = local.workload_identity["coordinator"].prefixes
  }
}
