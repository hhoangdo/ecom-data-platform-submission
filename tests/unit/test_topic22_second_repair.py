from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rest_preflight_uses_supported_endpoints_and_exact_notification_readback() -> None:
    """Catches a regression to unsupported gcloud IAM commands or accepting another notification channel."""
    budget = _load("scripts/gke/check_budget.py", "topic22_rest")
    requests: list[tuple[str, str, dict[str, object] | None]] = []

    def requester(method: str, url: str, _headers: dict[str, str], payload: dict[str, object] | None):
        requests.append((method, url, payload))
        if url.endswith("/v3/projects/private-project"):
            return {"state": "ACTIVE", "name": "projects/123", "projectId": "private-project"}
        if url.endswith("/v1/projects/private-project/billingInfo"):
            return {"billingEnabled": True, "billingAccountName": "billingAccounts/ABC"}
        if url.endswith("/v1/billingAccounts/ABC"):
            return {"name": "billingAccounts/ABC", "open": True, "currencyCode": "VND"}
        if url.endswith(":testIamPermissions") and "cloudresourcemanager" in url:
            return {"permissions": ["read"]}
        if url.endswith(":testIamPermissions") and "cloudbilling" in url:
            return {"permissions": ["write"]}
        if url.endswith("/v3/projects/private-project/notificationChannels/99"):
            return {"name": "projects/private-project/notificationChannels/other"}
        raise AssertionError(url)

    adapter = budget.GcloudRestExternalAdapter("private-project", "ABC", token_supplier=lambda: "token", requester=requester, dns_probe=lambda _: True, https_probe=lambda _: True)
    report = budget.run_external_preflight(adapter, required_permissions={"project": ["read"], "billing_account": ["write"]}, notification_target="projects/private-project/notificationChannels/99", recovery_sink="gs://private", dns_probes=["storage.googleapis.com"], required_urls=["https://console.example.test"])
    assert report["ok"] is False and "notification" in report["failures"]
    assert all("test-iam-permissions" not in url for _, url, _ in requests)
    assert any(method == "POST" and payload == {"permissions": ["read"]} for method, _, payload in requests)


def test_live_mode_requires_vnd_and_writes_failed_redacted_records_without_network(tmp_path: Path) -> None:
    """Catches the USD bypass or returning before writing the required failed-gate evidence."""
    budget = _load("scripts/gke/check_budget.py", "topic22_live_vnd")
    envelope = tmp_path / "envelope.yaml"
    envelope.write_text("terraform_budget_usd: 240\npre_deployment_forecast_ceiling_usd: 180\nceilings: {evidence_session_ttl_hours: 6}\n", encoding="utf-8")
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps({"approved": False}), encoding="utf-8")
    permissions = tmp_path / "permissions.json"
    permissions.write_text('{"project":["read"],"billing_account":["write"]}', encoding="utf-8")
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    preflight, forecast, ledger = tmp_path / "preflight.json", tmp_path / "forecast.json", tmp_path / "ledger.json"
    args = budget.parse_args(["--project", "private", "--billing-account-env", "BILLING", "--budget-notification-target-env", "NOTICE", "--recovery-sink-env", "SINK", "--recovery-sink-attestation", str(attestation), "--required-permissions", str(permissions), "--dns-probes", "storage.googleapis.com", "--required-url-envs", "URL", "--live-external-preflight", "--preflight-output", str(preflight), "--output", str(forecast), "--usage-ledger", str(ledger), "--envelope", str(envelope), "--trial-expires-at", "2099-01-01T00:00:00Z", "--spend-observed-at", now, "--requested-ttl", "0h", "--current-spend-usd", "1"])
    assert budget.execute(args, {"BILLING": "ABC", "NOTICE": "projects/private/notificationChannels/99", "SINK": "gs://private", "URL": "https://console.example.test"}, adapter_factory=lambda: pytest.fail("network adapter must not be created")) == 2
    assert preflight.is_file() and forecast.is_file() and not ledger.exists()
    assert "private" not in preflight.read_text(encoding="utf-8")


def test_realistic_terraform_show_is_sanitized_and_forbidden_resource_rejected(tmp_path: Path) -> None:
    """Catches rejecting normal Terraform JSON or ignoring the advertised forbidden-resource gate."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_show")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_third_fixture")
    document = third._realistic_plan() | {"format_version": "1.2", "terraform_version": "1.15.8", "variables": {"project_id": {"value": "private"}, "trial_credit_vnd": {"value": 7_500_000}}, "planned_values": {"root_module": {}}, "resource_drift": [], "configuration": {"provider_config": {}}}
    output = tmp_path / "sanitized.json"
    plan = tmp_path / "plan"; plan.write_bytes(b"binary-plan")
    capture.sanitize_terraform_plan(plan, output, runner=lambda _: json.dumps(document), required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, forbidden_resources={"vm"})
    assert "private" not in output.read_text(encoding="utf-8")
    document["resource_changes"][2]["type"] = "google_compute_instance"
    with pytest.raises(ValueError, match="forbidden Terraform resource"):
        capture.sanitize_terraform_payload(document, required_resources=set(), forbidden_resources={"vm"})


def test_terraform_show_rejects_secret_like_values_outside_resource_changes() -> None:
    """Catches a sanitizer silently accepting a secret in Terraform's top-level variables."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_show_top_level_secret")
    payload = {
        "variables": {"api_token": {"value": "not-safe-to-persist"}},
        "format_version": "1.2", "applyable": True, "complete": True, "errored": False,
        "resource_changes": [{"address": "google_container_cluster.edai2", "type": "google_container_cluster", "name": "edai2", "mode": "managed", "change": {"actions": ["create"], "after_sensitive": {}}}],
    }
    with pytest.raises(ValueError, match="secret"):
        capture.sanitize_terraform_payload(payload, required_resources={"gke"})


def test_private_browser_and_backend_inputs_must_be_ignored_topic22_paths(tmp_path: Path) -> None:
    """Catches accepting an unauthenticated browser state or a backend config outside the private runtime root."""
    budget = _load("scripts/gke/check_budget.py", "topic22_paths")
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_browser")
    workspace = tmp_path / "workspace"
    private = workspace / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    state = private / "browser-state.json"
    backend = private / "backend.hcl"
    state.write_text("{}", encoding="utf-8")
    backend.write_text('bucket = "private"\nprefix = "topic22"\n', encoding="utf-8")
    assert capture.validate_private_browser_state(state, workspace) == state.resolve()
    policy = lambda path, _kind: path.resolve()
    assert budget.validate_private_backend_config(backend, workspace, policy) == backend.resolve()
    with pytest.raises(ValueError):
        capture.validate_private_browser_state(workspace / "state.json", workspace)


def test_budget_amount_is_conservatively_derived_from_vnd_trial_credit() -> None:
    """Catches accepting an arbitrary VND budget that no longer equals the locked USD 240 envelope."""
    budget = _load("scripts/gke/check_budget.py", "topic22_budget_math")
    assert budget.derive_budget_vnd(7_500_001) == 6_000_000
    assert budget.derive_budget_vnd(299) == 239


def test_terraform_budget_and_workload_identity_use_authoritative_mappings() -> None:
    """Catches project-id budget filters, guessed KSA names, or constructed GCS service-agent identities."""
    budget = (ROOT / "infra/terraform/modules/budget/main.tf").read_text(encoding="utf-8")
    iam = (ROOT / "infra/terraform/modules/iam/main.tf").read_text(encoding="utf-8")
    kms = (ROOT / "infra/terraform/modules/kms/main.tf").read_text(encoding="utf-8")
    assert "data \"google_project\" \"current\"" in budget and "projects/${data.google_project.current.number}" in budget
    assert "trial_credit_vnd" in budget and "floor(var.trial_credit_vnd * 240 / 300)" in budget
    assert "edai2-retrieval-agent" in iam and "edai2-worker" in iam
    assert "google_storage_project_service_account" in kms


def test_backend_init_command_requires_private_config_and_refuses_local_state(tmp_path: Path) -> None:
    """Catches a future plan/apply using local state rather than the validated private GCS backend config."""
    budget = _load("scripts/gke/check_budget.py", "topic22_backend_command")
    workspace = tmp_path / "workspace"
    private = workspace / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    config = private / "backend.hcl"
    config.write_text('bucket = "private"\nprefix = "edai2/topic22"\n', encoding="utf-8")
    policy = lambda path, _kind: path.resolve()
    command = budget.build_backend_init_command(config, workspace, policy)
    assert command[-2:] == ["-reconfigure", "-backend-config=" + str(config.resolve())]
    state = workspace / "infra" / "terraform" / "edai2" / "terraform.tfstate"
    state.parent.mkdir(parents=True)
    state.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="local Terraform state"):
        budget.build_backend_init_command(config, workspace, policy)


def test_workload_identity_helm_values_bind_only_declared_ksa_gsa_pairs() -> None:
    """Catches a later chart render assigning a GSA to the wrong KSA or emitting an undeclared pair."""
    budget = _load("scripts/gke/check_budget.py", "topic22_wi_values")
    bindings = {
        "retrieval": {"ksa": "serviceAccount:project.svc.id.goog[edai2:edai2-retrieval-agent]", "gsa": "retrieval@project.iam.gserviceaccount.com"},
        "drift": {"ksa": "serviceAccount:project.svc.id.goog[edai2:edai2-drift-agent]", "gsa": "drift@project.iam.gserviceaccount.com"},
        "coordinator": {"ksa": "serviceAccount:project.svc.id.goog[edai2:edai2-coordinator]", "gsa": "coordinator@project.iam.gserviceaccount.com"},
        "workers": {"ksa": "serviceAccount:project.svc.id.goog[edai2:edai2-worker]", "gsa": "workers@project.iam.gserviceaccount.com"},
    }
    assert budget.workload_identity_helm_values(bindings, "retrieval") == {"serviceAccount": {"name": "edai2-retrieval-agent", "annotations": {"iam.gke.io/gcp-service-account": "retrieval@project.iam.gserviceaccount.com"}}}
    bindings["retrieval"]["ksa"] = "serviceAccount:project.svc.id.goog[edai2:wrong]"
    with pytest.raises(ValueError, match="binding"):
        budget.workload_identity_helm_values(bindings, "retrieval")


def test_sanitized_apply_inventory_requires_every_topic22_foundation_category() -> None:
    """Catches a successful Terraform image being rendered from cluster-only evidence."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_inventory")
    payload = {"cluster": {"workloadIdentityConfig": {}}, "node_pools": [{"name": "platform", "autoscaling": {"minNodeCount": 0, "maxNodeCount": 1}, "config": {"machineType": "e2-highmem-4", "spot": False}}, {"name": "spot", "autoscaling": {"minNodeCount": 0, "maxNodeCount": 2}, "config": {"machineType": "e2-standard-8", "spot": True}}], "zone": "us-central1-a", "project_alias_sha256": "a" * 64, "revision": "b" * 40}
    with pytest.raises(ValueError, match="foundation"):
        capture.sanitize_apply_inventory(payload)
    with pytest.raises(ValueError, match="foundation"):
        capture.sanitize_apply_inventory(payload | {"backend": {"verified": True}})


def test_live_inventory_reducer_requires_all_readback_categories_and_no_forwarding_rule() -> None:
    """Catches an apply inventory calling foundation resources verified without live category readbacks."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_live_inventory")
    readbacks = {"registry": [{}, {}, {}, {}, {}, {}], "gcs": [{}], "kms_cmek": [{}], "workload_identity_iam": [{}, {}, {}, {}], "budget": [{}], "forwarding_rules": []}
    with pytest.raises(ValueError, match="foundation"):
        capture.reduce_topic22_readbacks(readbacks)
    readbacks["forwarding_rules"] = [{}]
    with pytest.raises(ValueError):
        capture.reduce_topic22_readbacks(readbacks)
