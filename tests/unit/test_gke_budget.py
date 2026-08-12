from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "gke" / "check_budget.py"
    spec = importlib.util.spec_from_file_location("check_budget", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _profiles_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "gke" / "manage_profile.py"
    spec = importlib.util.spec_from_file_location("manage_profile", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_budget_gate_rejects_forecast_above_locked_ceiling() -> None:
    module = _module()
    result = module.evaluate_budget(
        {"terraform_budget_usd": 240, "pre_deployment_forecast_ceiling_usd": 180},
        current_spend_usd=181,
        requested_ttl_hours=2,
        trial_remaining_hours=48,
    )
    assert result["ok"] is False
    assert "forecast_ceiling" in result["failures"]


def test_external_preflight_redacts_identifiers_and_fails_missing_permission() -> None:
    module = _module()

    class Adapter:
        def project(self): return {"active": True, "project_id": "secret-project"}
        def billing(self): return {"linked": True, "billing_account": "0123-4567-ABCD"}
        def permissions(self, _project, _billing, _required): return {"project": ["resourcemanager.projects.get"], "billing_account": []}
        def dns(self, _host): return True
        def url(self, _value): return True

    report = module.run_external_preflight(
        Adapter(),
        required_permissions={"project": ["resourcemanager.projects.get"], "billing_account": ["billing.budgets.create"]},
        notification_target="mailto:person@example.test",
        recovery_sink="gs://secret-sink",
        dns_probes=["storage.googleapis.com"],
        required_urls=["https://console.example.test"],
    )
    assert report["ok"] is False
    rendered = str(report)
    assert "secret-project" not in rendered
    assert "0123-4567-ABCD" not in rendered
    assert "gs://secret-sink" not in rendered


@pytest.mark.parametrize("failure", ["project", "billing", "permissions", "notification", "recovery_sink", "dns", "url"])
def test_external_preflight_fails_closed_for_every_external_gate(failure: str) -> None:
    module = _module()

    class Adapter:
        def project(self): return {"active": failure != "project", "project_id": "private-project"}
        def billing(self): return {"linked": failure != "billing", "billing_account": "private-billing"}
        def permissions(self, *_): return {"project": [] if failure == "permissions" else ["read"], "billing_account": ["write"]}
        def dns(self, _): return failure != "dns"
        def url(self, _): return failure != "url"

    report = module.run_external_preflight(
        Adapter(), required_permissions={"project": ["read"], "billing_account": ["write"]},
        notification_target="" if failure == "notification" else "mailto:private@example.test",
        recovery_sink="" if failure == "recovery_sink" else "gs://private-sink",
        dns_probes=["private.dns"], required_urls=["https://private.example.test"],
    )
    assert report["ok"] is False
    assert all(value not in json.dumps(report) for value in ("private-project", "private-billing", "private@example.test", "private-sink", "private.example.test"))


@pytest.mark.parametrize("spend,ttl,trial,expected", [(10, 2, 48, True), (180, 7, 48, False), (180, -1, 48, False), (180, 2, 1, False), (181, 2, 48, False), (180, 2, 48, False)])
def test_budget_gate_enforces_forecast_and_duration_boundaries(spend: float, ttl: float, trial: float, expected: bool) -> None:
    module = _module()
    result = module.evaluate_budget({"terraform_budget_usd": 240, "pre_deployment_forecast_ceiling_usd": 180, "ceilings": {"evidence_session_ttl_hours": 6}}, current_spend_usd=spend, requested_ttl_hours=ttl, trial_remaining_hours=trial)
    assert result["ok"] is expected


def test_cli_requires_explicit_adapter_for_live_preflight_and_writes_redacted_output(tmp_path: Path) -> None:
    module = _module()
    envelope = tmp_path / "envelope.yaml"
    envelope.write_text("terraform_budget_usd: 240\npre_deployment_forecast_ceiling_usd: 180\nceilings: {evidence_session_ttl_hours: 6}\n", encoding="utf-8")
    permissions = tmp_path / "permissions.json"
    permissions.write_text('{"project":["read"],"billing_account":["write"]}', encoding="utf-8")
    attestation = tmp_path / "attestation.json"
    sink = "gs://private-recovery-sink"
    attestation.write_text(json.dumps({"approved": True, "encrypted": True, "outside_workspace": True, "custodian_count": 2, "sink_uri_sha256": module._hash(sink)}), encoding="utf-8")
    output = tmp_path / "preflight.json"
    observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    args = module.parse_args(["--project", "private-project", "--billing-account-env", "BILLING", "--budget-notification-target-env", "NOTICE", "--recovery-sink-env", "SINK", "--recovery-sink-attestation", str(attestation), "--required-permissions", str(permissions), "--dns-probes", "private.dns", "--required-url-envs", "CONSOLE", "--live-external-preflight", "--preflight-output", str(output), "--envelope", str(envelope), "--trial-expires-at", "2099-01-01T00:00:00Z", "--current-spend-usd", "10", "--spend-observed-at", observed, "--requested-profile", "core", "--requested-ttl", "2h"])
    environment = {"BILLING": "private-billing", "NOTICE": "projects/private-project/notificationChannels/99", "SINK": sink, "CONSOLE": "https://private.example.test"}
    assert module.execute(args, environment, adapter_factory=None) == 2

    class Adapter:
        def project(self): return {"active": True, "project_id": "private-project"}
        def billing(self): return {"linked": True, "billing_account": "private-billing"}
        def permissions(self, *_): return {"project": ["read"], "billing_account": ["write"]}
        def dns(self, _): return True
        def url(self, _): return True

    # Live mode is deliberately VND-only and additionally requires a private backend config.
    assert module.execute(args, environment, adapter_factory=lambda: Adapter()) == 2


@pytest.mark.parametrize("ttl", ["7h", "-1h", "bad"])
def test_profile_duration_rejects_invalid_or_excessive_ttl(ttl: str) -> None:
    with pytest.raises(ValueError):
        _profiles_module().parse_ttl(ttl)


def test_profile_render_requires_ttl_for_active_profiles_and_is_dry_run_only() -> None:
    module = _profiles_module()
    profiles = {"profiles": {"suspended": {"platform_nodes": 0}, "core": {"platform_nodes": 1}}}
    with pytest.raises(ValueError):
        module.render_profile(profiles, "core", None, dry_run=True)
    plan = module.render_profile(profiles, "core", "2h", dry_run=True)
    assert plan == {"dry_run": True, "profile": "core", "ttl_hours": 2, "resources": {"platform_nodes": 1}}
