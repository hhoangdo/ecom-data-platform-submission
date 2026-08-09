from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml


class ExternalAdapter(Protocol):
    def project(self) -> dict[str, Any]: ...
    def billing(self) -> dict[str, Any]: ...
    def permissions(self, project: dict[str, Any], billing: dict[str, Any], required: dict[str, list[str]]) -> dict[str, list[str]]: ...
    def dns(self, host: str) -> bool: ...
    def url(self, value: str) -> bool: ...


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_ttl(value: str) -> float:
    if not value.endswith("h"):
        raise ValueError("TTL must use whole-hour h notation")
    hours = float(value[:-1])
    if hours < 0 or hours > 6:
        raise ValueError("TTL must be between 0h and 6h")
    return hours


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(UTC)


def evaluate_budget(envelope: dict[str, Any], *, current_spend_usd: float, requested_ttl_hours: float, trial_remaining_hours: float) -> dict[str, Any]:
    failures: list[str] = []
    budget = float(envelope["terraform_budget_usd"])
    if current_spend_usd > float(envelope["pre_deployment_forecast_ceiling_usd"]):
        failures.append("forecast_ceiling")
    if current_spend_usd >= budget * 0.75:
        failures.append("budget_75")
    if requested_ttl_hours < 0 or requested_ttl_hours > float(envelope.get("ceilings", {}).get("evidence_session_ttl_hours", 6)):
        failures.append("ttl")
    if trial_remaining_hours < requested_ttl_hours:
        failures.append("trial_expiry")
    return {"ok": not failures, "failures": failures, "forecast_usd": current_spend_usd}


def run_external_preflight(adapter: ExternalAdapter, *, required_permissions: dict[str, list[str]], notification_target: str, recovery_sink: str, dns_probes: list[str], required_urls: list[str]) -> dict[str, Any]:
    project = adapter.project()
    billing = adapter.billing()
    granted = adapter.permissions(project, billing, required_permissions)
    failures = []
    if not project.get("active"): failures.append("project")
    if not billing.get("linked"): failures.append("billing")
    for scope, required in required_permissions.items():
        if not set(required).issubset(set(granted.get(scope, []))): failures.append(f"permissions:{scope}")
    if not notification_target: failures.append("notification")
    if not recovery_sink: failures.append("recovery_sink")
    if not all(adapter.dns(host) for host in dns_probes): failures.append("dns")
    if not all(adapter.url(value) for value in required_urls): failures.append("url")
    return {"ok": not failures, "failures": failures, "project_active": bool(project.get("active")), "billing_linked": bool(billing.get("linked")), "permission_counts": {scope: len(granted.get(scope, [])) for scope in required_permissions}, "notification_target_sha256": _hash(notification_target), "recovery_sink_sha256": _hash(recovery_sink), "dns_count": len(dns_probes), "url_count": len(required_urls)}


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--billing-account-env")
    parser.add_argument("--budget-notification-target-env")
    parser.add_argument("--recovery-sink-env")
    parser.add_argument("--recovery-sink-attestation")
    parser.add_argument("--required-permissions")
    parser.add_argument("--dns-probes")
    parser.add_argument("--required-url-envs")
    parser.add_argument("--live-external-preflight", action="store_true")
    parser.add_argument("--preflight-output")
    parser.add_argument("--trial-expires-at")
    parser.add_argument("--current-spend-usd", type=float)
    parser.add_argument("--spend-observed-at")
    parser.add_argument("--usage-ledger")
    parser.add_argument("--envelope")
    parser.add_argument("--requested-profile")
    parser.add_argument("--requested-ttl")
    parser.add_argument("--output")
    return parser.parse_args(arguments)


def _write(path: str | None, report: dict[str, Any]) -> None:
    if path:
        Path(path).write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")


def execute(args: argparse.Namespace, environment: dict[str, str] | None = None, adapter_factory: Callable[[], ExternalAdapter] | None = None) -> int:
    environment = os.environ if environment is None else environment
    required = ("project", "billing_account_env", "budget_notification_target_env", "recovery_sink_env", "recovery_sink_attestation", "required_permissions", "trial_expires_at", "current_spend_usd", "spend_observed_at", "envelope", "requested_ttl")
    if any(not getattr(args, name) for name in required):
        return 2
    try:
        ttl = parse_ttl(args.requested_ttl)
        observed = _parse_timestamp(args.spend_observed_at)
        now = datetime.now(UTC)
        if observed > now or (now - observed).total_seconds() > 86400:
            return 2
        expiry = _parse_timestamp(args.trial_expires_at)
        trial_hours = (expiry - now).total_seconds() / 3600
        envelope = yaml.safe_load(Path(args.envelope).read_text(encoding="utf-8"))
        budget = evaluate_budget(envelope, current_spend_usd=args.current_spend_usd, requested_ttl_hours=ttl, trial_remaining_hours=trial_hours)
        sink = environment.get(args.recovery_sink_env, "")
        attestation = json.loads(Path(args.recovery_sink_attestation).read_text(encoding="utf-8"))
        if not all((attestation.get("approved"), attestation.get("encrypted"), attestation.get("outside_workspace"), attestation.get("custodian_count", 0) >= 2, attestation.get("sink_uri_sha256") == _hash(sink))):
            budget["ok"] = False
            budget["failures"].append("recovery_sink_attestation")
        if not args.live_external_preflight:
            _write(args.output, budget)
            return 0 if budget["ok"] else 2
        if adapter_factory is None:
            return 2
        permissions = json.loads(Path(args.required_permissions).read_text(encoding="utf-8"))
        notification = environment.get(args.budget_notification_target_env, "")
        urls = [environment.get(name, "") for name in (args.required_url_envs or "").split(",") if name]
        report = run_external_preflight(adapter_factory(), required_permissions=permissions, notification_target=notification, recovery_sink=sink, dns_probes=[host for host in (args.dns_probes or "").split(",") if host], required_urls=urls)
        report["budget_ok"] = budget["ok"]
        report["ok"] = report["ok"] and budget["ok"]
        report["failures"] = sorted(set(report["failures"] + budget["failures"]))
        _write(args.preflight_output, report)
        _write(args.output, budget)
        return 0 if report["ok"] else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError):
        return 2


def main() -> int:
    return execute(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
