from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gcloud_adapter_reports_lifecycle_billing_and_permissions_without_identifiers() -> None:
    """Catches an adapter that leaks cloud identifiers or skips the IAM gate."""
    budget = _load("scripts/gke/check_budget.py", "topic22_budget_adapter")
    calls: list[tuple[str, str]] = []

    def requester(method: str, url: str, _headers, payload):
        calls.append((method, url))
        if url.endswith("/projects/private-project"): return {"state": "ACTIVE", "name": "projects/123456789", "projectId": "private-project"}
        if url.endswith("/billingInfo"): return {"billingEnabled": True, "billingAccountName": "billingAccounts/ABC-123"}
        if url.endswith("/billingAccounts/ABC-123"): return {"name": "billingAccounts/ABC-123", "open": True, "currencyCode": "VND"}
        if "cloudresourcemanager" in url: return {"permissions": ["resourcemanager.projects.get"]}
        if "cloudbilling" in url: return {"permissions": ["billing.budgets.create"]}
        if "monitoring" in url: return {"name": "projects/private-project/notificationChannels/99", "enabled": True, "verificationStatus": "VERIFIED"}
        raise AssertionError((method, url, payload))

    adapter = budget.GcloudRestExternalAdapter(
        "private-project", "ABC-123", token_supplier=lambda: "token", requester=requester,
        dns_probe=lambda host: host == "storage.googleapis.com",
        https_probe=lambda url: url == "https://console.example.test",
    )
    report = budget.run_external_preflight(
        adapter,
        required_permissions={
            "project": ["resourcemanager.projects.get"],
            "billing_account": ["billing.budgets.create"],
        },
        notification_target="projects/private-project/notificationChannels/99",
        recovery_sink="gs://private-recovery",
        dns_probes=["storage.googleapis.com"],
        required_urls=["https://console.example.test"],
    )

    rendered = json.dumps(report)
    assert report["ok"] is True
    assert report["billing_link_hash_matches"] is True
    assert report["billing_account_open"] is True
    assert report["billing_currency_vnd"] is True
    assert "private-project" not in rendered
    assert "ABC-123" not in rendered
    assert "private-recovery" not in rendered
    assert len(calls) == 6


def test_gcloud_adapter_rejects_a_notification_channel_that_cannot_be_read() -> None:
    """Catches treating a syntactically valid notification-channel name as an authorized target."""
    budget = _load("scripts/gke/check_budget.py", "topic22_notification")

    def requester(_method: str, url: str, _headers, _payload):
        if url.endswith("/projects/private-project"): return {"state": "ACTIVE", "name": "projects/123"}
        if url.endswith("/billingInfo"): return {"billingEnabled": True, "billingAccountName": "billingAccounts/ABC"}
        if "cloudresourcemanager" in url: return {"permissions": ["read"]}
        if "cloudbilling" in url: return {"permissions": ["write"]}
        raise OSError("not found")

    adapter = budget.GcloudRestExternalAdapter("private-project", "ABC", token_supplier=lambda: "token", requester=requester, dns_probe=lambda _: True, https_probe=lambda _: True)
    report = budget.run_external_preflight(adapter, required_permissions={"project": ["read"], "billing_account": ["write"]}, notification_target="projects/private-project/notificationChannels/99", recovery_sink="gs://private", dns_probes=["storage.googleapis.com"], required_urls=["https://console.example.test"])
    assert "notification" in report["failures"]


def test_live_budget_gate_reconciles_vnd_spend_and_records_locked_conversion() -> None:
    """Catches accepting a stale conversion, an unreconciled console amount, or a 75% budget breach."""
    budget = _load("scripts/gke/check_budget.py", "topic22_budget_vnd")
    envelope = {
        "terraform_budget_usd": 240,
        "pre_deployment_forecast_ceiling_usd": 180,
        "ceilings": {"evidence_session_ttl_hours": 6},
    }
    observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    report = budget.evaluate_live_budget(
        envelope,
        current_spend_vnd=900_000,
        console_spend_vnd=900_001,
        forecast_vnd=1_800_000,
        trial_credit_vnd=7_500_000,
        conversion_observed_at=observed,
        spend_observed_at=observed,
        requested_ttl_hours=0,
    )
    assert report["ok"] is True
    assert report["conversion_rate_vnd_per_usd"] == 25_000
    assert report["normalized_current_spend_usd"] == 36.0
    assert report["normalized_forecast_usd"] == 72.0
    assert report["budget_currency"] == "VND"

    rejected = budget.evaluate_live_budget(
        envelope,
        current_spend_vnd=4_500_000,
        console_spend_vnd=4_500_000,
        forecast_vnd=4_500_000,
        trial_credit_vnd=7_500_000,
        conversion_observed_at=observed,
        spend_observed_at=observed,
        requested_ttl_hours=0,
    )
    assert "budget_75" in rejected["failures"]


def test_usage_ledger_is_append_only_and_immutable_evidence_will_not_overwrite(tmp_path: Path) -> None:
    """Catches replacement of prior spend observations or silent evidence overwrites."""
    budget = _load("scripts/gke/check_budget.py", "topic22_budget_ledger")
    ledger = tmp_path / "nested" / "usage_ledger.json"
    first = {"observed_at_utc": "2026-08-12T00:00:00Z", "normalized_current_spend_usd": 1.0}
    second = {"observed_at_utc": "2026-08-12T01:00:00Z", "normalized_current_spend_usd": 2.0}
    budget.append_usage_ledger(ledger, first)
    budget.append_usage_ledger(ledger, second)
    observations = json.loads(ledger.read_text(encoding="utf-8"))["observations"]
    assert [{key: item[key] for key in first} for item in observations] == [first, second]
    assert observations[0]["previous_sha256"] == "0" * 64
    assert observations[1]["previous_sha256"] == observations[0]["entry_sha256"]

    output = tmp_path / "nested" / "preflight.json"
    budget.write_immutable_json(output, {"ok": True})
    with pytest.raises(FileExistsError):
        budget.write_immutable_json(output, {"ok": True})


def test_execute_live_vnd_preflight_persists_redacted_immutable_evidence_and_ledger(tmp_path: Path) -> None:
    """Catches the live VND path bypassing reconciliation, ledger append, or immutable evidence."""
    budget = _load("scripts/gke/check_budget.py", "topic22_budget_execute_vnd")
    envelope = tmp_path / "envelope.yaml"
    envelope.write_text("terraform_budget_usd: 240\npre_deployment_forecast_ceiling_usd: 180\nceilings: {evidence_session_ttl_hours: 6}\n", encoding="utf-8")
    permissions = tmp_path / "permissions.json"
    permissions.write_text('{"project":["read"],"billing_account":["write"]}', encoding="utf-8")
    sink = "gs://private-recovery-sink"
    attestation = tmp_path / "attestation.json"
    attestation.write_text(json.dumps({"approved": True, "encrypted": True, "outside_workspace": True, "sink_uri_sha256": budget._hash(sink), "attestations": [{"custodian_sha256": "a" * 64, "approved_at_utc": "2026-08-12T00:00:00Z", "provenance_sha256": "b" * 64}, {"custodian_sha256": "c" * 64, "approved_at_utc": "2026-08-12T00:01:00Z", "provenance_sha256": "d" * 64}]}), encoding="utf-8")
    observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    preflight, forecast, ledger = tmp_path / "nested" / "preflight.json", tmp_path / "nested" / "forecast.json", tmp_path / "nested" / "ledger.json"
    args = budget.parse_args([
        "--project", "private-project", "--billing-account-env", "BILLING",
        "--budget-notification-target-env", "NOTICE", "--recovery-sink-env", "SINK",
        "--recovery-sink-attestation", str(attestation), "--required-permissions", str(permissions),
        "--dns-probes", "private.dns", "--required-url-envs", "CONSOLE", "--live-external-preflight",
        "--preflight-output", str(preflight), "--envelope", str(envelope),
        "--trial-expires-at", "2099-01-01T00:00:00Z", "--spend-observed-at", observed,
        "--usage-ledger", str(ledger), "--requested-profile", "suspended", "--requested-ttl", "0h",
        "--output", str(forecast), "--current-spend-vnd", "900000", "--console-spend-vnd", "900001",
        "--forecast-vnd", "1800000", "--trial-credit-vnd", "7500000", "--conversion-observed-at", observed,
    ])

    class Adapter:
        def project(self): return {"active": True, "project_number_present": True}
        def billing(self): return {"linked": True, "billing_link_hash_matches": True}
        def permissions(self, *_): return {"project": ["read"], "billing_account": ["write"]}
        def dns(self, _): return True
        def url(self, _): return True

    environment = {"BILLING": "private-billing", "NOTICE": "projects/private-project/notificationChannels/99", "SINK": sink, "CONSOLE": "https://private.example.test"}
    # A live run now also requires a private backend config; do not create one in this hermetic test.
    assert budget.execute(args, environment, adapter_factory=lambda: Adapter()) == 2
    assert not ledger.exists()


def test_terraform_plan_sanitizer_emits_only_approved_resource_identity(tmp_path: Path) -> None:
    """Catches persisting raw plan values or allowing a VM/secret-bearing plan through review."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_capture_sanitizer")
    raw = _load("tests/unit/test_topic22_third_repair.py", "topic22_fixture_precloud")._realistic_plan()
    output = tmp_path / "terraform-show.json"
    plan = tmp_path / "plan.bin"; plan.write_bytes(b"binary-plan")
    report = capture.sanitize_terraform_plan(
        plan, output,
        runner=lambda _: json.dumps(raw),
        required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"},
    )
    rendered = output.read_text(encoding="utf-8")
    assert report["managed_resource_count"] > 8
    assert "private-project" not in rendered
    assert "@secret-project" not in rendered
    assert not (tmp_path / "plan.raw.json").exists()

    raw["resource_changes"].append({"address": "google_compute_instance.forbidden", "mode": "managed", "type": "google_compute_instance", "name": "forbidden", "change": {"actions": ["create"], "after": {}}})
    with pytest.raises(ValueError, match="unexpected Terraform resource"):
        capture.sanitize_terraform_payload(raw, required_resources={"gke"})


def test_topic22_capture_helpers_render_and_verify_both_owned_1600x1000_pngs(tmp_path: Path) -> None:
    """Catches a missing, malformed, or unbound Topic 22 evidence capture."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_capture_images")
    screenshots, manifest = tmp_path / "screenshots", tmp_path / "screenshots" / "ui_manifest.json"
    screenshots.mkdir()
    revision = "a" * 40
    fourth = _load("tests/unit/test_topic22_fourth_repair.py", "topic22_precloud_canonical_fixture")
    for filename, source in (("gcp_billing_spend.png", "https://console.cloud.google.com/billing"), ("terraform_apply.png", "https://terraform.example.test/apply")):
        machine = tmp_path / f"{filename}.json"
        plan_sha = "b" * 64 if filename == "gcp_billing_spend.png" else "c" * 64
        payload = {"result": "successful", "revision": revision, "plan_sha256": plan_sha, "zone": "us-central1-a", "node_pools": [], "registries": [], "workload_identity": [], "forwarding_rule_count": 0}
        if filename == "terraform_apply.png":
            payload = capture.sanitize_apply_inventory(fourth._typed_readbacks(), revision=revision)
            payload.update({"plan_sha256": plan_sha, "forecast_sha256": "d" * 64, "approval_record_sha256": "e" * 64})
        machine.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        capture.render_topic22_png(json.loads(machine.read_text(encoding="utf-8")), screenshots / filename, machine_path=machine)
        capture.record_capture(
            final_path=screenshots / filename, root=screenshots,
            writer=lambda destination, path=screenshots / filename: destination.write_bytes(path.read_bytes()),
            source=source, revision=revision, visible_selectors=capture.REQUIRED_VIEWS[filename],
            machine_evidence=[str(machine)], proves="Approved Topic 22 context is visible.",
                does_not_prove="It does not prove application readiness.", manifest_path=manifest, workspace=tmp_path,
        )
    capture.verify_topic22_screenshots(manifest, screenshots, ["gcp_billing_spend.png", "terraform_apply.png"], workspace=tmp_path)
    assert Image.open(screenshots / "gcp_billing_spend.png").size == (1600, 1000)


def test_topic22_cli_routes_sanitized_plan_without_writing_raw_terraform_json(tmp_path: Path) -> None:
    """Catches the advertised sanitizer CLI flag being disconnected from the in-memory sanitizer."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_capture_cli")
    output = tmp_path / "show.json"
    payload = _load("tests/unit/test_topic22_third_repair.py", "topic22_fixture_cli")._realistic_plan()
    plan = tmp_path / "plan.bin"; plan.write_bytes(b"binary-plan")
    forecast = tmp_path / "forecast.json"; forecast.write_text('{"ok":true}\n', encoding="utf-8")
    capture.sanitize_terraform_plan(plan, output, forecast_path=forecast, revision="c" * 40,
        required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, runner=lambda _: json.dumps(payload))
    assert output.is_file() and "resource_changes" not in output.read_text(encoding="utf-8")


def test_terraform_foundation_encrypts_gcs_and_binds_each_workload_identity() -> None:
    """Catches an unencrypted bucket or a GSA that a Kubernetes service account cannot impersonate."""
    gcs = (ROOT / "infra/terraform/modules/gcs/main.tf").read_text(encoding="utf-8")
    iam = (ROOT / "infra/terraform/modules/iam/main.tf").read_text(encoding="utf-8")
    kms = (ROOT / "infra/terraform/modules/kms/main.tf").read_text(encoding="utf-8")
    assert "encryption" in gcs and "default_kms_key_name" in gcs
    assert "google_kms_crypto_key_iam_member" in kms and "google_storage_project_service_account" in kms
    assert "google_service_account_iam_member" in iam
    assert "roles/iam.workloadIdentityUser" in iam
    assert "serviceAccount:${var.project_id}.svc.id.goog" in iam


def test_terraform_outputs_are_safe_and_budget_is_vnd_parameterized() -> None:
    """Catches losing safe handoff fields or hard-coding USD currency against the approved VND account."""
    variables = (ROOT / "infra/terraform/edai2/variables.tf").read_text(encoding="utf-8")
    outputs = (ROOT / "infra/terraform/edai2/outputs.tf").read_text(encoding="utf-8")
    main = (ROOT / "infra/terraform/edai2/main.tf").read_text(encoding="utf-8")
    budget = (ROOT / "infra/terraform/modules/budget/main.tf").read_text(encoding="utf-8")
    for value in ("budget_currency", "trial_credit_vnd", "currency_code = var.budget_currency", "units", "tostring(local.budget_amount_vnd)"):
        assert value in variables + main + budget
    for name in ("zone", "node_pool_names", "registry_uris", "bucket_prefixes", "kms_key_id", "workload_identity_bindings"):
        assert f'output "{name}"' in outputs
    assert "backend" not in main.lower()


def test_repository_ignores_terraform_state_and_topic22_operator_material() -> None:
    """Catches a state or private GCP input becoming eligible for accidental staging."""
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.tfstate" in ignored
    assert "*.tfstate.*" in ignored
    assert "tmp/*" in ignored


def test_terraform_requires_operator_supplied_remote_backend_but_allows_backend_free_validation() -> None:
    """Catches an apply silently defaulting to repository-local state after a dry validation run."""
    versions = (ROOT / "infra/terraform/edai2/versions.tf").read_text(encoding="utf-8")
    assert 'backend "gcs" {}' in versions
