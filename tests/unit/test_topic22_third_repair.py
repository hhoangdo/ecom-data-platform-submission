from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_success_uses_one_private_bundle_and_writes_three_redacted_immutable_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Catches live execution bypassing the private bundle, adapter, or durable privacy contract."""
    budget = _load("scripts/gke/check_budget.py", "topic22_third_live")
    workspace = tmp_path / "workspace"
    private = workspace / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    gcloud_config = private / "gcloud-config"
    tf_data_dir = private / "terraform-data"
    gcloud_config.mkdir()
    tf_data_dir.mkdir()
    adc = gcloud_config / "application_default_credentials.json"
    adc.write_text("{}\n", encoding="utf-8")
    tfvars = private / "coursework.auto.tfvars"
    tfvars.write_text('project_id = "secret-project"\n', encoding="utf-8")
    backend = private / "backend.hcl"
    backend.write_text('bucket = "private-state-bucket"\nprefix = "edai2/topic22"\n', encoding="utf-8")
    browser_state = private / "browser-state.json"
    browser_state.write_text("{}\n", encoding="utf-8")
    sink = "gs://secret-recovery-sink"
    attestation = private / "recovery-attestation.json"
    attestation.write_text(json.dumps({"approved": True, "encrypted": True, "outside_workspace": True, "sink_uri_sha256": budget._hash(sink), "attestations": [{"custodian_sha256": "a" * 64, "approved_at_utc": "2026-08-12T00:00:00Z", "provenance_sha256": "b" * 64}, {"custodian_sha256": "c" * 64, "approved_at_utc": "2026-08-12T00:01:00Z", "provenance_sha256": "d" * 64}]}) + "\n", encoding="utf-8")
    observed = datetime.now(UTC).replace(microsecond=0)
    bundle = private / "operator-inputs.json"
    bundle.write_text(json.dumps({
        "schema_version": 1,
        "project_id": "secret-project",
        "billing_account_id": "SECRET-BILLING",
        "budget_notification_target": "projects/secret-project/notificationChannels/42",
        "recovery_sink": sink,
        "billing_console_url": "https://console.cloud.google.com/billing/secret",
        "billing_required_markers": ["[aria-label*='Billing']", "[data-testid='current-spend']"],
        "billing_pii_selectors": ["[data-field='billing-account-id']", "[aria-label*='email']"],
        "dns_probes": ["storage.googleapis.com"],
        "trial_expires_at": (observed + timedelta(days=30)).isoformat().replace("+00:00", "Z"),
        "spend_observed_at": observed.isoformat().replace("+00:00", "Z"),
        "conversion_observed_at": observed.isoformat().replace("+00:00", "Z"),
        "current_spend_vnd": 900_000,
        "console_spend_vnd": 900_001,
        "forecast_vnd": 1_800_000,
        "trial_credit_vnd": 7_500_000,
        "backend_bucket_preexists": True,
        "backend_bucket_proof_sha256": "a" * 64,
        "paths": {
            "recovery_sink_attestation": "recovery-attestation.json",
            "terraform_tfvars": "coursework.auto.tfvars",
            "terraform_backend_config": "backend.hcl",
            "browser_storage_state": "browser-state.json",
            "gcloud_config_dir": "gcloud-config",
            "application_default_credentials": "gcloud-config/application_default_credentials.json",
            "tf_data_dir": "terraform-data",
        },
    }) + "\n", encoding="utf-8")
    permissions = workspace / "permissions.json"
    permissions.write_text('{"project":["resourcemanager.projects.get"],"billing_account":["billing.resourceAssociations.list"]}\n', encoding="utf-8")
    envelope = workspace / "envelope.yaml"
    envelope.write_text("terraform_budget_usd: 240\npre_deployment_forecast_ceiling_usd: 180\nceilings: {evidence_session_ttl_hours: 6}\n", encoding="utf-8")
    preflight = workspace / "evidence" / "preflight.json"
    forecast = workspace / "evidence" / "forecast.json"
    ledger = workspace / "evidence" / "usage-ledger.json"
    revision = "0" * 40
    (tf_data_dir / "topic22-bootstrap-proof.json").write_text(json.dumps({
        "ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64,
        "backend_bucket_sha256": "b" * 64, "backend_prefix_sha256": "c" * 64,
        "backend_project_number_sha256": "d" * 64, "revision": revision,
    }) + "\n", encoding="utf-8")
    (tf_data_dir / "topic22-backend-bootstrap-proof.json").write_text(json.dumps({
        "ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64,
        "observed_proof_sha256": "a" * 64, "bucket_sha256": "b" * 64,
        "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"), "revision": revision,
    }) + "\n", encoding="utf-8")

    validated: set[Path] = set()
    def private_policy(path: Path, _kind: str) -> Path:
        validated.add(path.resolve())
        return path.resolve()

    calls: list[str] = []
    class Adapter:
        def __init__(self, token_supplier): self._token_supplier = token_supplier
        def project(self): calls.append("project"); assert self._token_supplier() == "memory-only-token"; return {"active": True, "project_number_sha256": "b" * 64}
        def billing(self): calls.append("billing"); return {"linked": True, "billing_link_hash_matches": True, "billing_account_name_matches": True, "billing_account_open": True, "billing_currency_vnd": True}
        def permissions(self, _project, _billing, _required): calls.append("permissions"); return {"project": ["resourcemanager.projects.get"], "billing_account": ["billing.resourceAssociations.list"]}
        def dns(self, _host): calls.append("dns"); return True
        def url(self, _url): calls.append("url"); return True
        def notification(self, _target): calls.append("notification"); return True

    private_auth_calls: list[tuple[list[str], dict[str, str]]] = []
    def private_gcloud(command: list[str], environment: dict[str, str]) -> str:
        private_auth_calls.append((command, dict(environment)))
        return "memory-only-token"

    def production_adapter(*, project_id: str, billing_account: str, token_supplier):
        assert project_id == "secret-project"
        assert billing_account == "SECRET-BILLING"
        return Adapter(token_supplier)

    monkeypatch.setattr(budget, "_run_gcloud_private", private_gcloud)
    monkeypatch.setattr(budget, "GcloudRestExternalAdapter", production_adapter)

    args = budget.parse_args([
        "--operator-inputs", str(bundle), "--required-permissions", str(permissions),
        "--live-external-preflight", "--preflight-output", str(preflight),
        "--envelope", str(envelope), "--usage-ledger", str(ledger),
        "--requested-profile", "suspended", "--requested-ttl", "0h", "--output", str(forecast),
    ])
    assert budget.execute(args, {}, workspace=workspace, private_path_validator=private_policy) == 0
    assert calls == ["project", "billing", "permissions", "notification", "dns", "url"]
    assert private_auth_calls == [(["gcloud", "auth", "print-access-token"], {
        "CLOUDSDK_CONFIG": str(gcloud_config.resolve()),
        "GOOGLE_APPLICATION_CREDENTIALS": str(adc.resolve()),
    })]
    assert {bundle.resolve(), attestation.resolve(), tfvars.resolve(), backend.resolve(), browser_state.resolve(), gcloud_config.resolve(), adc.resolve(), tf_data_dir.resolve()} <= validated
    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in (preflight, forecast, ledger)]
    persisted = json.dumps(artifacts, sort_keys=True)
    for raw in ("secret-project", "SECRET-BILLING", "secret-recovery-sink", "notificationChannels/42", "/billing/secret"):
        assert raw not in persisted
    assert artifacts[1]["normalized_budget_usd"] == 240
    assert artifacts[1]["budget_amount_vnd"] == 6_000_000
    assert artifacts[2]["observations"][0]["entry_sha256"]

    snapshots = [path.read_bytes() for path in (preflight, forecast, ledger)]
    assert budget.execute(args, {}, workspace=workspace, private_path_validator=private_policy) == 2
    assert [path.read_bytes() for path in (preflight, forecast, ledger)] == snapshots


def test_external_preflight_requires_project_number_billing_hash_exact_permissions_and_public_targets() -> None:
    """Catches absent identity facts, permission supersets, and localhost/IP probe targets passing live gates."""
    budget = _load("scripts/gke/check_budget.py", "topic22_third_external_fail_closed")

    class Adapter:
        def project(self): return {"active": True}
        def billing(self): return {"linked": True}
        def permissions(self, *_): return {"project": ["read", "extra"], "billing_account": ["write"]}
        def dns(self, _host): return True
        def url(self, _url): return True
        def notification(self, _target): return True

    report = budget.run_external_preflight(
        Adapter(),
        required_permissions={"project": ["read"], "billing_account": ["write"]},
        notification_target="projects/redacted/notificationChannels/42",
        recovery_sink="gs://redacted",
        dns_probes=["storage.googleapis.com"],
        required_urls=["https://127.0.0.1/billing"],
    )
    assert {"project_number", "billing_link", "permissions:project", "url"} <= set(report["failures"])


def test_gcloud_adapter_hashes_project_number_and_blocks_private_probe_targets_before_io() -> None:
    """Catches raw project-number output or an SSRF-capable production DNS/HTTPS probe."""
    budget = _load("scripts/gke/check_budget.py", "topic22_third_adapter_targets")
    https_calls: list[str] = []
    adapter = budget.GcloudRestExternalAdapter(
        "redacted-project", "redacted-billing", token_supplier=lambda: "memory-only",
        requester=lambda _method, _url, _headers, _payload: {"name": "projects/123456789", "projectId": "redacted-project", "state": "ACTIVE"},
        https_probe=lambda value: https_calls.append(value) or True,
    )
    project = adapter.project()
    assert project["project_number_sha256"] == budget._hash("123456789")
    assert "123456789" not in json.dumps(project)
    assert adapter.url("https://127.0.0.1/private") is False
    assert adapter.dns("127.0.0.1") is False
    assert https_calls == []


@pytest.mark.parametrize(
    "project_payload",
    [
        {"name": "projects/not-numeric", "projectId": "redacted-project", "state": "ACTIVE"},
        {"name": "projects/123456789/extra", "projectId": "redacted-project", "state": "ACTIVE"},
        {"name": "projects/123456789", "projectId": "different-project", "state": "ACTIVE"},
        {"projectId": "redacted-project", "state": "ACTIVE"},
    ],
)
def test_gcloud_adapter_rejects_malformed_or_cross_project_resource_manager_schema(project_payload: dict[str, object]) -> None:
    """Catches hashing a missing/ambiguous CRM field or accepting another private project."""
    budget = _load("scripts/gke/check_budget.py", "topic22_third_adapter_crm_reject")
    adapter = budget.GcloudRestExternalAdapter(
        "redacted-project", "redacted-billing", token_supplier=lambda: "memory-only",
        requester=lambda _method, _url, _headers, _payload: project_payload,
    )
    with pytest.raises(ValueError, match="Resource Manager project"):
        adapter.project()


def _realistic_plan() -> dict[str, object]:
    services = (
        "artifactregistry.googleapis.com", "billingbudgets.googleapis.com", "cloudbilling.googleapis.com",
        "cloudkms.googleapis.com", "cloudresourcemanager.googleapis.com", "compute.googleapis.com",
        "container.googleapis.com", "iam.googleapis.com", "monitoring.googleapis.com",
        "serviceusage.googleapis.com", "storage.googleapis.com",
    )
    resources = [
        ("data.google_project.current", "data", "google_project", "current", ["read"], {"number": "123456789"}),
        ("module.kms.data.google_storage_project_service_account.gcs", "data", "google_storage_project_service_account", "gcs", ["read"], {"email_address": "service-123@gs-project-accounts.iam.gserviceaccount.com"}),
        ("module.gke.google_container_cluster.edai2", "managed", "google_container_cluster", "edai2", ["create"], {"name": "edai2", "location": "us-central1-a", "workload_identity_config": [{"workload_pool": "secret-project.svc.id.goog"}]}),
        ("module.gke.google_container_node_pool.platform", "managed", "google_container_node_pool", "platform", ["create"], {"name": "platform", "location": "us-central1-a", "node_count": 0, "autoscaling": [{"min_node_count": 0, "max_node_count": 1}], "node_config": [{"machine_type": "e2-highmem-4", "spot": False}]}),
        ("module.gke.google_container_node_pool.spot", "managed", "google_container_node_pool", "spot", ["create"], {"name": "spot", "location": "us-central1-a", "node_count": 0, "autoscaling": [{"min_node_count": 0, "max_node_count": 2}], "node_config": [{"machine_type": "e2-standard-8", "spot": True}]}),
        ("module.registry.google_artifact_registry_repository.images", "managed", "google_artifact_registry_repository", "images", ["create"], {"repository_id": "edai2-images", "location": "us-central1", "format": "DOCKER"}),
        ("module.gcs.google_storage_bucket.edai2", "managed", "google_storage_bucket", "edai2", ["create"], {"location": "US-CENTRAL1", "uniform_bucket_level_access": True, "encryption": [{"default_kms_key_name": "projects/secret/locations/us/keyRings/edai2/cryptoKeys/edai2"}], "lifecycle_rule": [{"action": [{"type": "Delete"}], "condition": [{"age": 7, "matches_prefix": ["langfuse-events/", "agent-substrate/"]}]}, {"action": [{"type": "Delete"}], "condition": [{"age": 90, "matches_prefix": ["backups/", "model-cache/", "airflow-logs/"]}]}]}),
        ("module.kms.google_kms_crypto_key.edai2", "managed", "google_kms_crypto_key", "edai2", ["create"], {"rotation_period": "7776000s"}),
        ("module.kms.google_kms_crypto_key_iam_member.gcs_service_agent", "managed", "google_kms_crypto_key_iam_member", "gcs_service_agent", ["create"], {"role": "roles/cloudkms.cryptoKeyEncrypterDecrypter", "member": "serviceAccount:service-123@gs-project-accounts.iam.gserviceaccount.com"}),
        ("module.budget.google_billing_budget.edai2", "managed", "google_billing_budget", "edai2", ["create"], {"amount": [{"specified_amount": [{"currency_code": "VND", "units": "6000000"}]}], "budget_filter": [{"projects": ["projects/123456789"]}], "threshold_rules": [{"threshold_percent": 0.5}, {"threshold_percent": 0.75}, {"threshold_percent": 0.9}, {"threshold_percent": 1.0}]}),
    ]
    resources.extend((f"google_project_service.topic22[{service!r}]", "managed", "google_project_service", "topic22", ["create"], {"project": "secret-project", "service": service, "disable_on_destroy": False}) for service in services)
    prefix_roles = {
        "retrieval": ["model-cache/"], "drift": ["langfuse-events/"],
        "coordinator": ["agent-substrate/", "backups/"], "workers": ["airflow-logs/"],
    }
    for workload, prefixes in prefix_roles.items():
        gsa = f"edai2-{workload}@secret-project.iam.gserviceaccount.com"
        ksa = {"retrieval": "edai2-retrieval-agent", "drift": "edai2-drift-agent", "coordinator": "edai2-coordinator", "workers": "edai2-worker"}[workload]
        resources.extend([
            (f"module.iam.google_service_account.workload[{workload!r}]", "managed", "google_service_account", "workload", ["create"], {"account_id": f"edai2-{workload}"}),
            (f"module.iam.google_service_account_iam_member.workload_identity[{workload!r}]", "managed", "google_service_account_iam_member", "workload_identity", ["create"], {"role": "roles/iam.workloadIdentityUser", "member": f"serviceAccount:secret-project.svc.id.goog[edai2:{ksa}]", "service_account_id": f"projects/secret-project/serviceAccounts/{gsa}"}),
        ])
        for prefix in prefixes:
            resources.append((f"module.iam.google_storage_bucket_iam_member.prefix_access[{prefix!r}]", "managed", "google_storage_bucket_iam_member", "prefix_access", ["create"], {"role": "roles/storage.objectUser", "member": f"serviceAccount:{gsa}", "condition": [{"expression": f"resource.name.startsWith('projects/_/buckets/redacted/objects/{prefix}')"}]}))
    return {"format_version": "1.2", "applyable": True, "complete": True, "errored": False, "resource_changes": [
        {"address": address, "mode": mode, "type": kind, "name": name, "change": {"actions": actions, "after": after, "after_sensitive": {}}}
        for address, mode, kind, name, actions, after in resources
    ], "variables": {"trial_credit_vnd": {"value": 7_500_000}}, "output_changes": {"workload_identity_bindings": {"after_sensitive": False}}}


def test_plan_authorization_record_validates_exact_invariants_and_binds_three_hashes(tmp_path: Path) -> None:
    """Catches name/count-only authorization or output that exposes principals from a realistic plan."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_plan")
    plan = tmp_path / "topic22.tfplan"
    plan.write_bytes(b"exact-binary-plan")
    forecast = tmp_path / "forecast.json"
    forecast.write_text('{"ok":true,"normalized_budget_usd":240}\n', encoding="utf-8")
    revision = "c" * 40
    record = capture.sanitize_terraform_payload(
        _realistic_plan(),
        required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"},
        plan_sha256=capture.hash_file(plan), forecast_sha256=capture.hash_file(forecast), revision=revision,
    )
    assert record["plan_sha256"] == capture.hash_file(plan)
    assert record["forecast_sha256"] == capture.hash_file(forecast)
    assert record["revision"] == revision
    assert record["invariants"] == {
        "zone": "us-central1-a", "cluster": "edai2",
        "node_pools": [{"name": "platform", "machine_type": "e2-highmem-4", "spot": False, "min": 0, "max": 1}, {"name": "spot", "machine_type": "e2-standard-8", "spot": True, "min": 0, "max": 2}],
        "cmek": True, "bucket_lifecycle": {"7": ["agent-substrate/", "langfuse-events/"], "90": ["airflow-logs/", "backups/", "model-cache/"]},
        "prefix_iam_count": 5, "workload_identity_count": 4,
        "budget": {"currency": "VND", "amount_vnd": 6_000_000, "trial_credit_vnd": 7_500_000, "normalized_usd": 240, "thresholds": [0.5, 0.75, 0.9, 1.0], "project_number_filter": True},
        "project_services": ["artifactregistry.googleapis.com", "billingbudgets.googleapis.com", "cloudbilling.googleapis.com", "cloudkms.googleapis.com", "cloudresourcemanager.googleapis.com", "compute.googleapis.com", "container.googleapis.com", "iam.googleapis.com", "monitoring.googleapis.com", "serviceusage.googleapis.com", "storage.googleapis.com"],
        "data_reads": ["google_project", "google_storage_project_service_account"], "prohibited_resources": 0,
    }
    rendered = json.dumps(record)
    assert "@secret-project" not in rendered and "service-123" not in rendered and "123456789" not in rendered
    assert len(record["principal_fingerprints"]) == 5


def test_plan_budget_binds_each_trial_credit_to_its_conservative_vnd_amount() -> None:
    """Catches a sanitizer reverting to the one historical six-million VND budget."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_dynamic_budget")
    plan = _realistic_plan()
    plan["variables"]["trial_credit_vnd"]["value"] = 9_000_001
    for change in plan["resource_changes"]:
        if change["type"] == "google_billing_budget":
            change["change"]["after"]["amount"][0]["specified_amount"][0]["units"] = "7200000"
    record = capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, plan_sha256="a" * 64, forecast_sha256="b" * 64, revision="c" * 40)
    assert record["invariants"]["budget"]["amount_vnd"] == 7_200_000


@pytest.mark.parametrize("mutation,match", [
    (("actions", ["delete"]), "action"),
    (("pool_max", 3), "node pool"),
    (("sensitive", True), "sensitive"),
])
def test_plan_authorization_rejects_destructive_sensitive_or_invariant_mismatch(mutation, match: str) -> None:
    """Catches a destructive plan, sensitive output, or wrong zero-pool ceiling reaching authorization."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", f"topic22_third_plan_{mutation[0]}")
    plan = _realistic_plan()
    if mutation[0] == "actions":
        plan["resource_changes"][2]["change"]["actions"] = mutation[1]
    elif mutation[0] == "pool_max":
        plan["resource_changes"][3]["change"]["after"]["autoscaling"][0]["max_node_count"] = mutation[1]
    else:
        plan["output_changes"]["workload_identity_bindings"]["after_sensitive"] = mutation[1]
    with pytest.raises(ValueError, match=match):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, plan_sha256="a" * 64, forecast_sha256="b" * 64, revision="c" * 40)


def test_inventory_cli_reduces_complete_typed_adapter_readback_without_raw_principals(tmp_path: Path) -> None:
    """Catches cluster-only/count-only inventory or a CLI that bypasses the injected production boundary."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_inventory")
    revision = "d" * 40
    raw = {
        "project_alias_sha256": "1" * 64, "project_number_sha256": "2" * 64,
        "cluster": {"name": "edai2", "zone": "us-central1-a", "workload_pool_sha256": "3" * 64},
        "node_pools": [{"name": "platform", "machine_type": "e2-highmem-4", "spot": False, "min": 0, "max": 1, "current": 0}, {"name": "spot", "machine_type": "e2-standard-8", "spot": True, "min": 0, "max": 2, "current": 0}],
        "registries": [{"name": name, "format": "DOCKER", "location": "us-central1"} for name in ("edai2-rag-index", "edai2-retrieval-agent", "edai2-drift-agent", "edai2-coordinator", "edai2-feast-offline-writer", "edai2-feast-online-writer")],
        "bucket": {"name_sha256": "4" * 64, "location": "US-CENTRAL1", "cmek_sha256": "5" * 64, "lifecycle": {"7": ["agent-substrate/", "langfuse-events/"], "90": ["airflow-logs/", "backups/", "model-cache/"]}, "uniform_access": True},
        "kms": {"key_sha256": "5" * 64, "rotation_seconds": 7_776_000, "gcs_service_agent_sha256": "6" * 64, "gcs_role": "roles/cloudkms.cryptoKeyEncrypterDecrypter"},
        "workload_identity": [
            {"workload": "retrieval", "ksa": "edai2-retrieval-agent", "ksa_member_sha256": "7" * 64, "gsa_sha256": "8" * 64, "prefixes": ["model-cache/"]},
            {"workload": "drift", "ksa": "edai2-drift-agent", "ksa_member_sha256": "9" * 64, "gsa_sha256": "a" * 64, "prefixes": ["langfuse-events/"]},
            {"workload": "coordinator", "ksa": "edai2-coordinator", "ksa_member_sha256": "b" * 64, "gsa_sha256": "c" * 64, "prefixes": ["agent-substrate/", "backups/"]},
            {"workload": "workers", "ksa": "edai2-worker", "ksa_member_sha256": "d" * 64, "gsa_sha256": "e" * 64, "prefixes": ["airflow-logs/"]},
        ],
        "prefix_iam": [{"prefix": prefix, "gsa_sha256": fingerprint, "role": "roles/storage.objectUser"} for prefix, fingerprint in (("model-cache/", "8" * 64), ("langfuse-events/", "a" * 64), ("agent-substrate/", "c" * 64), ("backups/", "c" * 64), ("airflow-logs/", "e" * 64))],
        "budget": {"currency": "VND", "amount_vnd": 6_000_000, "trial_credit_vnd": 7_500_000, "normalized_usd": 240, "thresholds": [0.5, 0.75, 0.9, 1.0], "project_number_sha256": "2" * 64, "project_number_filter_matches": True, "notification_channel_sha256": "f" * 64, "notification_channel_matches": True},
        "backend": {"bucket_sha256": "4" * 64, "prefix_sha256": "f" * 64, "remote_state_present": True},
        "forwarding_rules": [],
    }
    class Adapter:
        def read(self, _operator_inputs): return raw

    bundle = tmp_path / "operator.json"
    bundle.write_text("{}\n", encoding="utf-8")
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps(capture.sanitize_terraform_payload(
        _realistic_plan(), required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"},
        plan_sha256="a" * 64, forecast_sha256="b" * 64, revision=revision,
    )) + "\n", encoding="utf-8")
    output = tmp_path / "inventory.json"
    assert capture.run_topic22_cli(["--terraform-inventory", "--operator-inputs", str(bundle), "--authorization-evidence", str(authorization), "--output", str(output), "--strict"], inventory_adapter_factory=lambda: Adapter(), operator_loader=lambda *_args: None, revision=revision) == 0
    inventory = json.loads(output.read_text(encoding="utf-8"))
    assert inventory["result"] == "successful" and inventory["revision"] == revision
    assert inventory["workload_identity"] == sorted(raw["workload_identity"], key=lambda item: item["workload"])
    persisted = output.read_text(encoding="utf-8")
    assert "@" not in persisted and "secret-project" not in persisted

    raw["forwarding_rules"] = [{"name": "forbidden"}]
    with pytest.raises(ValueError, match="forwarding"):
        capture.run_topic22_cli(["--terraform-inventory", "--operator-inputs", str(bundle), "--authorization-evidence", str(authorization), "--output", str(tmp_path / "rejected.json"), "--strict"], inventory_adapter_factory=lambda: Adapter(), operator_loader=lambda *_args: None, revision=revision)


def test_production_inventory_adapter_uses_rest_and_private_terraform_runtime_without_identifier_argv(tmp_path: Path) -> None:
    """Catches an advertised production adapter that only reads cluster/count placeholders."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_inventory_production")
    raw_project, raw_billing = "secret-project", "SECRET-BILLING"
    raw_bucket, backend_bucket = "secret-foundation-bucket", "secret-state-bucket"
    key = f"projects/{raw_project}/locations/us-central1/keyRings/edai2/cryptoKeys/edai2"
    bindings = {
        "retrieval": {"ksa": f"serviceAccount:{raw_project}.svc.id.goog[edai2:edai2-retrieval-agent]", "gsa": f"edai2-retrieval@{raw_project}.iam.gserviceaccount.com", "prefixes": ["model-cache/"]},
        "drift": {"ksa": f"serviceAccount:{raw_project}.svc.id.goog[edai2:edai2-drift-agent]", "gsa": f"edai2-drift@{raw_project}.iam.gserviceaccount.com", "prefixes": ["langfuse-events/"]},
        "coordinator": {"ksa": f"serviceAccount:{raw_project}.svc.id.goog[edai2:edai2-coordinator]", "gsa": f"edai2-coordinator@{raw_project}.iam.gserviceaccount.com", "prefixes": ["agent-substrate/", "backups/"]},
        "workers": {"ksa": f"serviceAccount:{raw_project}.svc.id.goog[edai2:edai2-worker]", "gsa": f"edai2-workers@{raw_project}.iam.gserviceaccount.com", "prefixes": ["airflow-logs/"]},
    }
    private = tmp_path / "private"
    private.mkdir()
    backend = private / "backend.hcl"
    backend.write_text(f'bucket = "{backend_bucket}"\nprefix = "edai2/topic22"\n', encoding="utf-8")
    tf_data = private / "tf-data"; tf_data.mkdir()
    tfvars = private / "vars.tfvars"; tfvars.write_text("# private\n", encoding="utf-8")
    notification = f"projects/{raw_project}/notificationChannels/42"
    operator = {"project_id": raw_project, "billing_account_id": raw_billing, "budget_notification_target": notification, "trial_credit_vnd": 7_500_000, "backend_bucket_proof_sha256": "f" * 64, "resolved_paths": {"terraform_backend_config": backend, "terraform_tfvars": tfvars, "tf_data_dir": tf_data, "gcloud_config_dir": private, "application_default_credentials": tfvars}}
    commands: list[list[str]] = []
    command_environments: list[dict[str, str]] = []
    outputs = {name: {"value": value} for name, value in {"bucket_name": raw_bucket, "kms_key_id": key, "workload_identity_bindings": bindings}.items()}

    def runner(command: list[str], environment: dict[str, str]) -> str:
        commands.append(command)
        command_environments.append(dict(environment))
        if command == ["gcloud", "auth", "print-access-token"]:
            return "memory-token\n"
        return json.dumps(outputs)

    def requester(_method: str, url: str, _headers, _payload):
        if "cloudresourcemanager" in url: return {"name": "projects/123456789", "projectId": raw_project, "state": "ACTIVE"}
        if "/clusters/edai2/nodePools" in url: return {"nodePools": [{"name": "platform", "instanceGroupUrls": ["https://compute.example/platform"], "autoscaling": {"minNodeCount": 0, "maxNodeCount": 1}, "config": {"machineType": "e2-highmem-4"}}, {"name": "spot", "instanceGroupUrls": ["https://compute.example/spot"], "autoscaling": {"minNodeCount": 0, "maxNodeCount": 2}, "config": {"machineType": "e2-standard-8", "spot": True}}]}
        if "/clusters/edai2" in url: return {"name": "edai2", "location": "us-central1-a", "workloadIdentityConfig": {"workloadPool": f"{raw_project}.svc.id.goog"}}
        if "artifactregistry" in url: return {"repositories": [{"name": f"projects/x/locations/us-central1/repositories/{name}", "format": "DOCKER"} for name in ("edai2-rag-index", "edai2-retrieval-agent", "edai2-drift-agent", "edai2-coordinator", "edai2-feast-offline-writer", "edai2-feast-online-writer")]}
        if url.endswith("/iam") and "storage" in url: return {"bindings": [{"role": "roles/storage.objectUser", "members": [f"serviceAccount:{entry['gsa']}"], "condition": {"expression": f"resource.name.startsWith('projects/_/buckets/{raw_bucket}/objects/{prefix}')"}} for entry in bindings.values() for prefix in entry["prefixes"]]}
        if "storage.googleapis.com/storage/v1/b/" in url and "/o?" not in url: return {"name": raw_bucket, "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "encryption": {"defaultKmsKeyName": key}, "lifecycle": {"rule": [{"action": {"type": "Delete"}, "condition": {"age": 7, "matchesPrefix": ["agent-substrate/", "langfuse-events/"]}}, {"action": {"type": "Delete"}, "condition": {"age": 90, "matchesPrefix": ["airflow-logs/", "backups/", "model-cache/"]}}]}}
        if "storage.googleapis.com/storage/v1/projects/" in url: return {"emailAddress": "service-123@gs-project-accounts.iam.gserviceaccount.com"}
        if "/o?" in url: return {"items": [{"name": "edai2/topic22/default.tfstate"}]}
        if "cloudkms" in url and "getIamPolicy" in url: return {"bindings": [{"role": "roles/cloudkms.cryptoKeyEncrypterDecrypter", "members": ["serviceAccount:service-123@gs-project-accounts.iam.gserviceaccount.com"]}]}
        if "cloudkms" in url: return {"name": key, "rotationPeriod": "7776000s"}
        if "iam.googleapis.com" in url: return {"bindings": [{"role": "roles/iam.workloadIdentityUser", "members": [entry["ksa"] for entry in bindings.values() if entry["gsa"] in url]}]}
        if "billingbudgets" in url: return {"budgets": [{"amount": {"specifiedAmount": {"currencyCode": "VND", "units": "6000000"}}, "budgetFilter": {"projects": ["projects/123456789"]}, "allUpdatesRule": {"monitoringNotificationChannels": [notification]}, "thresholdRules": [{"thresholdPercent": value} for value in (0.5, 0.75, 0.9, 1.0)]}]}
        if "forwardingRules" in url: return {"items": {}}
        if "instanceGroupManagers" in url: return {"items": {"zones/us-central1-a": {"instanceGroupManagers": [{"selfLink": "https://compute.example/platform", "targetSize": 0}, {"selfLink": "https://compute.example/spot", "targetSize": 0}]}}}
        raise AssertionError(url)

    adapter = capture.GcloudRestTopic22InventoryAdapter(workspace=tmp_path, operator_loader=lambda _path, _workspace: operator, runner=runner, requester=requester)
    sanitized = capture.sanitize_apply_inventory(adapter.read(private / "operator.json"), revision="d" * 40)
    assert sanitized["result"] == "successful"
    assert commands == [["terraform", "-chdir=infra/terraform/edai2", "output", "-json"], ["gcloud", "auth", "print-access-token"]]
    assert command_environments[1]["CLOUDSDK_CONFIG"] == str(private)
    assert command_environments[1]["GOOGLE_APPLICATION_CREDENTIALS"] == str(tfvars)
    assert command_environments[1]["TF_DATA_DIR"] == str(tf_data)
    assert all(raw_project not in part and raw_billing not in part and raw_bucket not in part for command in commands for part in command)


@pytest.mark.parametrize(
    "project_payload",
    [
        {"name": "projects/not-numeric", "projectId": "secret-project", "state": "ACTIVE"},
        {"name": "projects/123456789/extra", "projectId": "secret-project", "state": "ACTIVE"},
        {"name": "projects/123456789", "projectId": "different-project", "state": "ACTIVE"},
        {"projectId": "secret-project", "state": "ACTIVE"},
    ],
)
def test_inventory_adapter_rejects_malformed_or_cross_project_resource_manager_schema(tmp_path: Path, project_payload: dict[str, object]) -> None:
    """Catches inventory continuing after a noncanonical or cross-project CRM response."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_inventory_crm_reject")
    private = tmp_path / "private"
    private.mkdir()
    backend = private / "backend.hcl"
    backend.write_text('bucket = "private-state-bucket"\nprefix = "edai2/topic22"\n', encoding="utf-8")
    tf_data = private / "tf-data"
    tf_data.mkdir()
    credential = private / "adc.json"
    credential.write_text("{}\n", encoding="utf-8")
    operator = {
        "project_id": "secret-project", "billing_account_id": "SECRET-BILLING",
        "resolved_paths": {
            "terraform_backend_config": backend, "tf_data_dir": tf_data,
            "gcloud_config_dir": private, "application_default_credentials": credential,
        },
    }
    outputs = {name: {"value": value} for name, value in {
        "bucket_name": "private-foundation-bucket",
        "kms_key_id": "projects/secret-project/locations/us-central1/keyRings/edai2/cryptoKeys/edai2",
        "workload_identity_bindings": {},
    }.items()}

    def requester(_method: str, url: str, _headers, _payload):
        if "cloudresourcemanager" in url:
            return project_payload
        raise AssertionError("inventory must reject the CRM response before further readbacks")

    adapter = capture.GcloudRestTopic22InventoryAdapter(
        workspace=tmp_path, operator_loader=lambda _path, _workspace: operator,
        runner=lambda command, _environment: json.dumps(outputs) if command[0] == "terraform" else "memory-token",
        requester=requester,
    )
    with pytest.raises(ValueError, match="Resource Manager project"):
        adapter.read(private / "operator.json")


def test_terraform_png_and_manifest_visibly_bind_machine_record_plan_and_revision(tmp_path: Path) -> None:
    """Catches a one-line JSON image or manifest that names evidence without hash-binding it."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_terraform_png")
    root = tmp_path / "screenshots"; root.mkdir()
    machine = tmp_path / "terraform_apply.json"
    revision, plan_sha = "e" * 40, "a" * 64
    fourth = _load("tests/unit/test_topic22_fourth_repair.py", "topic22_third_canonical_fixture")
    payload = capture.sanitize_apply_inventory(fourth._typed_readbacks(), revision=revision)
    payload.update({"plan_sha256": plan_sha, "forecast_sha256": "b" * 64, "approval_record_sha256": "c" * 64})
    machine.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    output, manifest = root / "terraform_apply.png", root / "ui_manifest.json"
    entry = capture.record_capture(
        final_path=output, root=root,
        writer=lambda destination: capture.render_topic22_png(json.loads(machine.read_text(encoding="utf-8")), destination, machine_path=machine),
        source="https://evidence.local/terraform-apply", revision=revision,
        visible_selectors=capture.REQUIRED_VIEWS["terraform_apply.png"], machine_evidence=[str(machine)],
        proves="Sanitized apply inventory is successful.", does_not_prove="It does not prove workload readiness.", manifest_path=manifest, workspace=tmp_path,
    )
    assert entry["linked_machine_evidence"] == [{"path": "terraform_apply.json", "sha256": capture.hash_file(machine)}]
    assert entry["approved_plan_sha256"] == plan_sha
    extracted = capture.topic22_png_text(output)
    for visible in ("EDAI2 Topic 22 Terraform apply evidence", "Result: successful", revision, plan_sha, str(machine), capture.hash_file(machine), "Zone: us-central1-a", "platform", "spot"):
        assert visible in extracted
    capture.verify_topic22_screenshots(manifest, root, ["terraform_apply.png"], revision=revision, workspace=tmp_path)
    machine.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="machine evidence"):
        capture.verify_topic22_screenshots(manifest, root, ["terraform_apply.png"], revision=revision)


def test_billing_writer_uses_real_markers_annotation_and_masks_pii_without_synthetic_page_phrases(tmp_path: Path) -> None:
    """Catches requiring fabricated GCP text or capturing unresolved account/person identifiers."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_third_billing_capture")
    state = tmp_path / "state.json"; state.write_text("{}\n", encoding="utf-8")
    calls: list[object] = []

    class Locator:
        def __init__(self, selector: str): self.selector = selector
        def count(self): return 1
        def inner_text(self, timeout=0): return "Billing Overview Current spend Budget"
        def evaluate_all(self, _script): calls.append(("mask", self.selector))
    class Page:
        url = "https://console.cloud.google.com/billing/overview"
        def goto(self, _url, **_kwargs): calls.append("goto")
        def locator(self, selector): return Locator(selector)
        def wait_for_selector(self, selector, **_kwargs): calls.append(("marker", selector))
        def evaluate(self, _script, annotation): calls.append(("annotation", annotation))
        def screenshot(self, **kwargs): Path(kwargs["path"]).write_bytes(b"png")

    writer = capture._billing_page_writer(
        "https://console.cloud.google.com/billing/overview", state,
        project_alias_sha256="a" * 64, observed_at="2026-08-12T00:00:00Z",
        required_markers=["[aria-label*='Billing']", "[data-testid='current-spend']"],
        pii_selectors=["[data-field='billing-account-id']", "[aria-label*='email']"],
        page_factory=lambda _state: Page(),
    )
    writer(tmp_path / "billing.png")
    assert ("marker", "[aria-label*='Billing']") in calls
    assert ("mask", "[data-field='billing-account-id']") in calls
    annotation = next(item[1] for item in calls if isinstance(item, tuple) and item[0] == "annotation")
    assert annotation == {"project_alias_sha256": "a" * 64, "observed_at_utc": "2026-08-12T00:00:00Z"}
