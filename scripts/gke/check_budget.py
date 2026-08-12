from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode, urlsplit
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

from vina_bim_shop.topic22_private import (
    _private_topic22_path as _shared_private_topic22_path,
    backend_values as _shared_backend_values,
    load_operator_inputs as _shared_load_operator_inputs,
    resource_manager_project_number,
    rest_request as _shared_rest_request,
    validate_billing_selectors as _shared_validate_billing_selectors,
    validate_private_operator_path as _shared_validate_private_operator_path,
)


TOPIC22_REQUIRED_SERVICES = frozenset({
    "artifactregistry.googleapis.com", "billingbudgets.googleapis.com", "cloudbilling.googleapis.com",
    "cloudkms.googleapis.com", "cloudresourcemanager.googleapis.com", "compute.googleapis.com",
    "container.googleapis.com", "iam.googleapis.com", "monitoring.googleapis.com",
    "serviceusage.googleapis.com", "storage.googleapis.com",
})

TOPIC22_OPERATION_PERMISSIONS = {
    "project_read": {"scope": "project", "permissions": ("resourcemanager.projects.get", "resourcemanager.projects.getIamPolicy")},
    "project_service": {"scope": "project", "permissions": ("serviceusage.services.enable", "serviceusage.services.get", "serviceusage.services.list", "servicemanagement.services.bind")},
    "artifact_registry": {"scope": "project", "permissions": ("artifactregistry.repositories.create", "artifactregistry.repositories.get", "artifactregistry.repositories.list")},
    "gke": {"scope": "project", "permissions": ("container.clusters.create", "container.clusters.get", "container.clusters.list", "container.nodePools.create", "container.nodePools.get", "container.nodePools.list")},
    "compute_inventory": {"scope": "project", "permissions": ("compute.instances.list", "compute.instanceGroupManagers.list", "compute.forwardingRules.list", "compute.networks.list", "compute.subnetworks.list", "compute.firewalls.list", "compute.addresses.list")},
    "storage": {"scope": "project", "permissions": ("storage.buckets.create", "storage.buckets.get", "storage.buckets.list", "storage.buckets.getIamPolicy", "storage.buckets.setIamPolicy", "storage.objects.create", "storage.objects.delete", "storage.objects.get", "storage.objects.list", "storage.objects.update", "storage.services.get")},
    "kms": {"scope": "project", "permissions": ("cloudkms.cryptoKeys.create", "cloudkms.cryptoKeys.get", "cloudkms.cryptoKeys.getIamPolicy", "cloudkms.cryptoKeys.setIamPolicy", "cloudkms.keyRings.create", "cloudkms.keyRings.get", "cloudkms.keyRings.list")},
    "iam": {"scope": "project", "permissions": ("iam.serviceAccounts.create", "iam.serviceAccounts.get", "iam.serviceAccounts.list", "iam.serviceAccounts.getIamPolicy", "iam.serviceAccounts.setIamPolicy")},
    "notification": {"scope": "project", "permissions": ("monitoring.notificationChannels.get",)},
    "billing": {"scope": "billing_account", "permissions": ("billing.accounts.get", "billing.accounts.getIamPolicy", "billing.resourceAssociations.list", "billing.budgets.create", "billing.budgets.get", "billing.budgets.list", "billing.budgets.update")},
}

TOPIC22_BOOTSTRAP_AUTHORITY_GATES = {
    "parent_project_create": ("parent", ("resourcemanager.projects.create",)),
    "billing_association": ("billing", ("billing.resourceAssociations.create",)),
    "project_billing_assignment": ("project", ("resourcemanager.projects.createBillingAssignment",)),
    "backend_storage": ("project", ("storage.buckets.create", "storage.buckets.get", "storage.buckets.getIamPolicy", "storage.buckets.list", "storage.objects.list")),
    "reuse_inventory": ("project", ("resourcemanager.projects.getIamPolicy", "container.clusters.list", "artifactregistry.repositories.list", "cloudkms.keyRings.list", "iam.serviceAccounts.list", "compute.instances.list", "compute.instanceGroupManagers.list", "compute.forwardingRules.list", "compute.networks.list", "compute.subnetworks.list", "compute.firewalls.list", "compute.addresses.list")),
    "service_usage_read_enable": ("service_usage", ("serviceusage.services.list", "serviceusage.effectivepolicy.get", "serviceusage.services.enable", "serviceusage.operations.get")),
    "service_bind": ("service_management", ("servicemanagement.services.bind",)),
}


class ExternalAdapter(Protocol):
    def project(self) -> dict[str, Any]: ...
    def billing(self) -> dict[str, Any]: ...
    def permissions(self, project: dict[str, Any], billing: dict[str, Any], required: dict[str, list[str]]) -> dict[str, list[str]]: ...
    def dns(self, host: str) -> bool: ...
    def url(self, value: str) -> bool: ...
    def notification(self, value: str) -> bool: ...


class _RedactedArgumentParser(argparse.ArgumentParser):
    """Never reflect operator-supplied argv or paths in a Topic 22 CLI failure."""

    def error(self, _message: str) -> None:
        self.exit(2, "TOPIC22_INPUT_ERROR\n")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _run_gcloud(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _access_token() -> str:
    token = _run_gcloud(["gcloud", "auth", "print-access-token"]).strip()
    if not token:
        raise ValueError("empty access token")
    return token


def _rest_request(method: str, url: str, headers: dict[str, str], payload: dict[str, object] | None) -> dict[str, Any]:
    return _shared_rest_request(method, url, headers, payload)


def _is_notification_target(value: str) -> bool:
    parts = value.split("/")
    return len(parts) == 4 and parts[0] == "projects" and parts[2] == "notificationChannels" and bool(parts[1]) and bool(parts[3])


def _public_hostname(value: str) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or "/" in value or "@" in value:
        return False
    host = value.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return bool(re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", host))
    return False


def _public_https_url(value: str) -> bool:
    if not isinstance(value, str) or value != value.strip():
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return parsed.scheme == "https" and not parsed.username and not parsed.password and port in (None, 443) and _public_hostname(parsed.hostname or "")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def _safe_https_probe(value: str) -> bool:
    if not _public_https_url(value):
        return False
    request = urllib.request.Request(value, method="HEAD")
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=10) as response:  # nosec B310 -- public HTTPS URL validated above; redirects disabled
        return 200 <= response.status < 400


class GcloudRestExternalAdapter:
    """Read-only production adapter using supported Google REST APIs, never CLI IAM subcommands."""

    def __init__(
        self,
        project_id: str,
        billing_account: str,
        token_supplier: Callable[[], str] = _access_token,
        requester: Callable[[str, str, dict[str, str], dict[str, object] | None], dict[str, Any]] = _rest_request,
        dns_probe: Callable[[str], bool] | None = None,
        https_probe: Callable[[str], bool] = _safe_https_probe,
    ) -> None:
        self._project_id = project_id
        self._billing_account = billing_account
        self._token_supplier = token_supplier
        self._requester = requester
        self._dns_probe = dns_probe or self._dns
        self._https_probe = https_probe

    @staticmethod
    def _dns(host: str) -> bool:
        if not _public_hostname(host):
            return False
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError:
            return False
        try:
            return bool(addresses) and all(ipaddress.ip_address(address[4][0]).is_global for address in addresses)
        except ValueError:
            return False

    def _request(self, method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
        token = self._token_supplier()
        try:
            return self._requester(method, url, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, payload)
        finally:
            token = ""

    def project(self) -> dict[str, Any]:
        payload = self._request("GET", f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(self._project_id, safe='')}")
        project_number = resource_manager_project_number(payload, self._project_id)
        return {
            "active": payload.get("state") == "ACTIVE",
            "project_sha256": _hash(self._project_id),
            "project_number_sha256": _hash(project_number),
        }

    def billing(self) -> dict[str, Any]:
        payload = self._request("GET", f"https://cloudbilling.googleapis.com/v1/projects/{quote(self._project_id, safe='')}/billingInfo")
        linked = payload.get("billingAccountName")
        expected_name = f"billingAccounts/{self._billing_account}"
        account = self._request("GET", f"https://cloudbilling.googleapis.com/v1/{expected_name}")
        return {
            "linked": payload.get("billingEnabled") is True,
            "billing_link_hash_matches": linked == expected_name,
            "billing_account_open": account.get("open") is True,
            "billing_currency_vnd": account.get("currencyCode") == "VND",
            "billing_account_name_matches": account.get("name") == expected_name,
            "billing_account_sha256": _hash(self._billing_account),
        }

    def permissions(self, _project: dict[str, Any], _billing: dict[str, Any], required: dict[str, list[str]]) -> dict[str, list[str]]:
        results: dict[str, list[str]] = {}
        for scope, permissions in required.items():
            if not permissions or not all(isinstance(item, str) and item for item in permissions):
                raise ValueError("required permissions are invalid")
            if scope == "project":
                url = f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(self._project_id, safe='')}:testIamPermissions"
            elif scope == "billing_account":
                url = f"https://cloudbilling.googleapis.com/v1/billingAccounts/{quote(self._billing_account, safe='')}:testIamPermissions"
            else:
                raise ValueError("unknown permission scope")
            payload = self._request("POST", url, {"permissions": permissions})
            granted = payload.get("permissions", [])
            if not isinstance(granted, list) or not all(isinstance(value, str) for value in granted):
                raise ValueError("gcloud IAM response is invalid")
            results[scope] = granted
        return results

    def dns(self, host: str) -> bool:
        return self._dns_probe(host)

    def url(self, value: str) -> bool:
        return _public_https_url(value) and self._https_probe(value)

    def notification(self, value: str) -> bool:
        if not _is_notification_target(value):
            return False
        project, channel = value.split("/")[1], value.split("/")[3]
        try:
            payload = self._request("GET", f"https://monitoring.googleapis.com/v3/projects/{quote(project, safe='')}/notificationChannels/{quote(channel, safe='')}")
        except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError):
            return False
        verification = payload.get("verificationStatus")
        return (
            payload.get("name") == value
            and payload.get("enabled") is True
            and verification == "VERIFIED"
        )


GcloudExternalAdapter = GcloudRestExternalAdapter


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


def _fresh_timestamp(value: str) -> datetime:
    observed = _parse_timestamp(value)
    now = datetime.now(UTC)
    if observed > now or (now - observed).total_seconds() > 86400:
        raise ValueError("observation is stale")
    return observed


def evaluate_live_budget(
    envelope: dict[str, Any],
    *,
    current_spend_vnd: float,
    console_spend_vnd: float,
    forecast_vnd: float,
    trial_credit_vnd: float,
    conversion_observed_at: str,
    spend_observed_at: str,
    requested_ttl_hours: float,
    trial_expires_at: str = "9999-12-31T23:59:59Z",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize VND observations to the USD envelope and fail closed on every gate."""
    _fresh_timestamp(conversion_observed_at)
    _fresh_timestamp(spend_observed_at)
    if trial_credit_vnd <= 0 or min(current_spend_vnd, console_spend_vnd, forecast_vnd) < 0:
        raise ValueError("VND money values are invalid")
    now = datetime.now(UTC) if now is None else now.astimezone(UTC)
    trial_expiry = _parse_timestamp(trial_expires_at)
    trial_remaining_hours = (trial_expiry - now).total_seconds() / 3600
    rate = trial_credit_vnd / 300.0
    current_usd = current_spend_vnd / rate
    console_usd = console_spend_vnd / rate
    forecast_usd = forecast_vnd / rate
    failures: list[str] = []
    budget_usd = float(envelope["terraform_budget_usd"])
    if abs(current_usd - console_usd) > 5:
        failures.append("spend_reconciliation")
    if forecast_usd > float(envelope["pre_deployment_forecast_ceiling_usd"]):
        failures.append("forecast_ceiling")
    if current_usd >= budget_usd:
        failures.append("budget_100")
    elif current_usd >= budget_usd * 0.9:
        failures.append("budget_90")
    elif current_usd >= budget_usd * 0.75:
        failures.append("budget_75")
    if requested_ttl_hours < 0 or requested_ttl_hours > float(envelope.get("ceilings", {}).get("evidence_session_ttl_hours", 6)):
        failures.append("ttl")
    if trial_remaining_hours < requested_ttl_hours:
        failures.append("trial_expiry")
    return {
        "ok": not failures,
        "failures": failures,
        "budget_currency": "VND",
        "conversion_rate_vnd_per_usd": rate,
        "conversion_rate_source": "operator-observed VND trial credit divided by official USD 300 trial credit",
        "conversion_observed_at_utc": conversion_observed_at,
        "spend_observed_at_utc": spend_observed_at,
        "official_trial_credit_usd": 300,
        "trial_credit_vnd": trial_credit_vnd,
        "trial_expires_at_utc": trial_expires_at,
        "trial_remaining_hours": trial_remaining_hours,
        "requested_ttl_hours": requested_ttl_hours,
        "normalized_current_spend_usd": current_usd,
        "normalized_console_spend_usd": console_usd,
        "normalized_forecast_usd": forecast_usd,
        "current_spend_vnd": current_spend_vnd,
        "console_spend_vnd": console_spend_vnd,
        "forecast_vnd": forecast_vnd,
        "normalized_budget_usd": budget_usd,
        "budget_amount_vnd": derive_budget_vnd(trial_credit_vnd),
        "normalized_forecast_ceiling_usd": float(envelope["pre_deployment_forecast_ceiling_usd"]),
        "forecast_ceiling_vnd": float(envelope["pre_deployment_forecast_ceiling_usd"]) * rate,
    }


def derive_budget_vnd(trial_credit_vnd: float) -> int:
    """Floor fractional VND so the deployed cap never exceeds the normalized USD 240 envelope."""
    if trial_credit_vnd <= 0:
        raise ValueError("trial credit must be positive")
    return math.floor(trial_credit_vnd * 240 / 300)


def run_external_preflight(adapter: ExternalAdapter, *, required_permissions: dict[str, list[str]], notification_target: str, recovery_sink: str, dns_probes: list[str], required_urls: list[str]) -> dict[str, Any]:
    project = adapter.project()
    billing = adapter.billing()
    invalid_permission_spec = (
        not required_permissions
        or set(required_permissions) != {"project", "billing_account"}
        or any(not isinstance(values, list) or not values or len(values) != len(set(values)) or not all(isinstance(value, str) and value for value in values) for values in required_permissions.values())
    )
    granted = adapter.permissions(project, billing, required_permissions) if not invalid_permission_spec else {}
    failures = []
    project_number_sha256 = project.get("project_number_sha256")
    if project.get("active") is not True: failures.append("project")
    if not isinstance(project_number_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", project_number_sha256): failures.append("project_number")
    if billing.get("linked") is not True: failures.append("billing")
    if billing.get("billing_link_hash_matches") is not True: failures.append("billing_link")
    if billing.get("billing_account_name_matches") is not True: failures.append("billing_account")
    if billing.get("billing_account_open") is not True: failures.append("billing_open")
    if billing.get("billing_currency_vnd") is not True: failures.append("billing_currency")
    if invalid_permission_spec: failures.append("permissions:spec")
    for scope, required in required_permissions.items():
        supplied = granted.get(scope)
        if not isinstance(supplied, list) or len(supplied) != len(set(supplied)) or set(supplied) != set(required): failures.append(f"permissions:{scope}")
    notification_valid = _is_notification_target(notification_target) and adapter.notification(notification_target)
    if not notification_valid: failures.append("notification")
    if not recovery_sink: failures.append("recovery_sink")
    if not dns_probes or not all(_public_hostname(host) and adapter.dns(host) for host in dns_probes): failures.append("dns")
    if not required_urls or not all(_public_https_url(value) and adapter.url(value) for value in required_urls): failures.append("url")
    return {"ok": not failures, "failures": failures, "project_active": project.get("active") is True, "project_number_sha256": project_number_sha256 if isinstance(project_number_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", project_number_sha256) else None, "billing_linked": billing.get("linked") is True, "billing_link_hash_matches": billing.get("billing_link_hash_matches") is True, "billing_account_open": billing.get("billing_account_open") is True, "billing_currency_vnd": billing.get("billing_currency_vnd") is True, "permission_counts": {scope: len(granted.get(scope, [])) if isinstance(granted.get(scope), list) else 0 for scope in required_permissions}, "notification_target_sha256": _hash(notification_target), "recovery_sink_sha256": _hash(recovery_sink), "dns_count": len(dns_probes), "url_count": len(required_urls)}


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = _RedactedArgumentParser()
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
    parser.add_argument("--current-spend-vnd", type=float)
    parser.add_argument("--console-spend-vnd", type=float)
    parser.add_argument("--forecast-vnd", type=float)
    parser.add_argument("--trial-credit-vnd", type=float)
    parser.add_argument("--conversion-observed-at")
    parser.add_argument("--terraform-backend-config")
    parser.add_argument("--operator-inputs")
    parser.add_argument("--redacted-account-summary", action="store_true")
    parser.add_argument("--prepare-kube-target", action="store_true")
    parser.add_argument("--private-terraform-action", choices=("init", "plan", "apply"))
    parser.add_argument("--verify-private-backend", choices=("bootstrap", "initialized"))
    parser.add_argument("--private-bootstrap", action="store_true")
    parser.add_argument("--write-private-wi-values", action="store_true")
    return parser.parse_args(arguments)


def write_immutable_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(report, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _private_current_revision(workspace: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, check=False, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip() if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()) else "0" * 40


def append_usage_ledger(path: Path, observation: dict[str, Any]) -> None:
    """Append one hash-chained observation after validating the complete existing chain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or set(payload) != {"observations"} or not isinstance(payload["observations"], list):
            raise ValueError("usage ledger is invalid")
        observations = payload["observations"]
    else:
        observations = []
    previous = "0" * 64
    for existing in observations:
        if not isinstance(existing, dict) or existing.get("previous_sha256") != previous:
            raise ValueError("usage ledger hash chain is invalid")
        supplied = existing.get("entry_sha256")
        body = {key: value for key, value in existing.items() if key != "entry_sha256"}
        expected = _hash(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        if supplied != expected:
            raise ValueError("usage ledger hash chain is invalid")
        previous = supplied
    entry = {**observation, "previous_sha256": previous}
    entry["entry_sha256"] = _hash(json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    observations.append(entry)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps({"observations": observations}, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _private_topic22_path(value: str | Path, workspace: Path, *, directory: bool = False) -> Path:
    return _shared_private_topic22_path(value, workspace, directory=directory)


def validate_private_operator_path(path: Path, kind: str, workspace: Path) -> Path:
    """Require a real ignored path whose ACL/mode does not grant broad access."""
    return _shared_validate_private_operator_path(path, kind, workspace)


def _backend_values(path: Path) -> dict[str, str]:
    return _shared_backend_values(path)


def validate_private_backend_config(value: str | Path, workspace: Path, path_validator: Callable[[Path, str], Path] | None = None) -> Path:
    path = (path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace)))(Path(value), "backend_config")
    _backend_values(path)
    return path


def _reject_repository_terraform_runtime(workspace: Path) -> None:
    terraform_root = workspace / "infra" / "terraform" / "edai2"
    if (terraform_root / ".terraform").exists() or any(terraform_root.rglob("*.tfstate")) or any(terraform_root.rglob("*.tfstate.*")):
        raise ValueError("local Terraform state or backend metadata blocks remote execution")


def verify_backend_bucket_proof(
    bucket: str,
    prefix: str,
    phase: str,
    *,
    requester: Callable[[str, str, dict[str, str], dict[str, object] | None], dict[str, object]],
    project_number: str | None = None,
) -> dict[str, object]:
    """Read and fingerprint the exact pre-existing GCS backend without exposing its identity."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]", bucket) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*[A-Za-z0-9]", prefix) or phase not in {"bootstrap", "initialized"}:
        raise ValueError("backend proof input is invalid")
    base = f"https://storage.googleapis.com/storage/v1/b/{quote(bucket, safe='')}"
    metadata = requester("GET", base, {}, None)
    policy = requester("GET", f"{base}/iam", {}, None)
    if not all(isinstance(value, dict) for value in (metadata, policy)):
        raise ValueError("backend proof is invalid")
    uniform = metadata.get("iamConfiguration", {}).get("uniformBucketLevelAccess", {}).get("enabled") if isinstance(metadata.get("iamConfiguration"), dict) else None
    versioning = metadata.get("versioning", {}).get("enabled") if isinstance(metadata.get("versioning"), dict) else None
    bindings = policy.get("bindings")
    if metadata.get("location") != "US-CENTRAL1" or uniform is not True or versioning is not True or not isinstance(bindings, list) or (project_number is not None and str(metadata.get("projectNumber")) != project_number):
        raise ValueError("backend proof is invalid")
    principals = [member for binding in bindings if isinstance(binding, dict) for member in binding.get("members", []) if isinstance(member, str)]
    if any(member in {"allUsers", "allAuthenticatedUsers"} for member in principals):
        raise ValueError("backend proof is invalid")
    names: list[str] = []
    page_token: str | None = None
    seen_tokens: set[str] = set()
    for _ in range(20):
        query = {"prefix": prefix + "/"}
        if page_token is not None:
            query["pageToken"] = page_token
        objects = requester("GET", f"{base}/o?{urlencode(query)}", {}, None)
        items = objects.get("items", []) if isinstance(objects, dict) else None
        if not isinstance(items, list) or any(not isinstance(item, dict) or not isinstance(item.get("name"), str) for item in items):
            raise ValueError("backend proof is invalid")
        names.extend(item["name"] for item in items)
        next_token = objects.get("nextPageToken")
        if next_token is None:
            break
        if not isinstance(next_token, str) or not next_token or next_token in seen_tokens:
            raise ValueError("backend proof is invalid")
        seen_tokens.add(next_token)
        page_token = next_token
    else:
        raise ValueError("backend proof is invalid")
    state_name = f"{prefix}/default.tfstate"
    state_present = names == [state_name]
    if (phase == "initialized" and not state_present) or (phase == "bootstrap" and names):
        raise ValueError("backend proof is invalid")
    proof = {
        "bucket_sha256": _hash(bucket), "prefix_sha256": _hash(prefix), "project_number_sha256": _hash(project_number) if project_number is not None else None, "location_us_central1": True,
        "uniform_bucket_level_access": True, "versioning_enabled": True,
        "public_access_absent": True, "state_object_present": state_present, "phase": phase,
    }
    return {**proof, "proof_sha256": _hash(json.dumps(proof, sort_keys=True, separators=(",", ":")))}


def verify_private_backend_bundle(
    operator: dict[str, Any],
    *,
    token_runner: Callable[[list[str], dict[str, str]], str] | None = None,
    requester: Callable[[str, str, dict[str, str], dict[str, object] | None], dict[str, object]] = _rest_request,
    phase: str = "initialized",
) -> dict[str, object]:
    """Dispatch a redacted backend proof using only the bundle's private gcloud/ADC paths."""
    paths = operator.get("resolved_paths")
    if not isinstance(paths, dict) or not isinstance(operator.get("project_id"), str):
        raise ValueError("private backend bundle is invalid")
    config = _backend_values(Path(paths["terraform_backend_config"]))
    environment = dict(os.environ)
    environment.update({"CLOUDSDK_CONFIG": str(paths["gcloud_config_dir"]), "GOOGLE_APPLICATION_CREDENTIALS": str(paths["application_default_credentials"])})
    runner = _run_gcloud_private if token_runner is None else token_runner
    token = runner(["gcloud", "auth", "print-access-token"], environment).strip()
    if not token:
        raise ValueError("private backend token is empty")
    try:
        project = requester("GET", f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(operator['project_id'], safe='')}", {"Authorization": f"Bearer {token}"}, None)
        project_number = resource_manager_project_number(project, operator["project_id"])
        return verify_backend_bucket_proof(
            config["bucket"], config["prefix"], phase,
            requester=lambda method, url, _headers, body: requester(method, url, {"Authorization": f"Bearer {token}"}, body),
            project_number=project_number,
        )
    finally:
        token = ""


def create_private_backend_bucket(
    call: Callable[[str, str, dict[str, object] | None], dict[str, object]],
    *, bucket: str, prefix: str, project_number: str, data_dir: Path, completed: dict[str, bool] | None = None,
) -> dict[str, object]:
    """Create the sole fresh-project backend bucket, then prove it before Terraform can run."""
    if not isinstance(data_dir, Path) or not re.fullmatch(r"[0-9]+", project_number):
        raise ValueError("backend bootstrap is invalid")
    payload = {
        "name": bucket, "location": "US-CENTRAL1",
        "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}},
        "versioning": {"enabled": True},
    }
    created = False
    try:
        response = call("POST", f"https://storage.googleapis.com/storage/v1/b?project={quote(project_number, safe='')}", payload)
        if not isinstance(response, dict) or response.get("name") != bucket:
            raise ValueError("backend bootstrap is invalid")
        created = True
        return verify_backend_bucket_proof(
            bucket, prefix, "bootstrap",
            requester=lambda method, url, _headers, body: call(method, url, body), project_number=project_number,
        )
    except (OSError, ValueError, TypeError, urllib.error.HTTPError) as error:
        if created:
            write_bootstrap_partial_handoff(data_dir, phase="fresh_backend_create", completed={**(completed or {}), "backend_bucket_created": True}, bucket=bucket)
        raise ValueError("backend bootstrap is invalid") from error


def ensure_partial_handoff(data_dir: Path, *, phase: str, completed: dict[str, bool], bucket: str | None = None) -> None:
    """Persist the only redacted rollback handoff after a fresh bootstrap mutation fails."""
    expected = ("project_create_requested", "project_created", "billing_linked", "apis_enabled", "backend_bucket_created")
    if not isinstance(data_dir, Path) or phase not in {"project_create", "billing_link", "api_enable", "fresh_backend_create"}:
        raise ValueError("bootstrap partial handoff is invalid")
    if (data_dir / "topic22-bootstrap-partial.json").exists():
        return
    state = {name: completed.get(name) is True for name in expected}
    actions = [name for name, done in state.items() if done]
    payload: dict[str, object] = {"ok": False, "phase": phase, **state, "rollback_required": bool(actions), "owned_rollback_actions": actions, "do_not_delete_existing": True, "cost_estimate_usd_upper_bound": 0, "resume_condition": "operator_review_required"}
    if bucket is not None:
        payload["bucket_sha256"] = _hash(bucket)
    write_immutable_json(data_dir / "topic22-bootstrap-partial.json", payload)


write_bootstrap_partial_handoff = ensure_partial_handoff


def validate_private_backend_gate(operator: dict[str, object], proof: dict[str, object], *, phase: str) -> dict[str, object]:
    """Bind a read-only backend proof to the private bundle and reject reuse/partial state."""
    if phase not in {"bootstrap", "initialized"} or not isinstance(operator.get("backend_bucket_preexists"), bool):
        raise ValueError("backend gate is invalid")
    expected = operator.get("backend_bucket_proof_sha256")
    if not isinstance(expected, str) or (operator["backend_bucket_preexists"] is True and not re.fullmatch(r"[0-9a-f]{64}", expected)) or (operator["backend_bucket_preexists"] is False and expected != ""):
        raise ValueError("backend gate is invalid")
    if proof.get("phase") != phase or proof.get("state_object_present") is not (phase == "initialized") or not isinstance(proof.get("proof_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", proof["proof_sha256"]):
        raise ValueError("backend gate is invalid")
    if phase == "bootstrap" and operator["backend_bucket_preexists"] is True and proof["proof_sha256"] != expected:
        raise ValueError("backend gate is invalid")
    return {"ok": True, "phase": phase, "backend_bucket_proof_sha256": proof["proof_sha256"] if phase == "bootstrap" else expected, "observed_proof_sha256": proof["proof_sha256"], "bucket_sha256": proof.get("bucket_sha256"), "prefix_sha256": proof.get("prefix_sha256"), "project_number_sha256": proof.get("project_number_sha256")}


def _bootstrap_backend_binding(operator: dict[str, object], data_dir: Path) -> tuple[bool, str]:
    """Resolve the immutable bootstrap proof into the sole runtime backend binding."""
    if operator.get("backend_bucket_preexists") is True:
        value = operator.get("backend_bucket_proof_sha256")
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            return True, value
    try:
        record = json.loads((data_dir / "topic22-bootstrap-proof.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("private backend proof is required") from error
    binding = record.get("backend_bucket_proof_sha256") if isinstance(record, dict) else None
    if not isinstance(record, dict) or record.get("ok") is not True or record.get("phase") != "bootstrap" or not isinstance(binding, str) or not re.fullmatch(r"[0-9a-f]{64}", binding):
        raise ValueError("private backend proof is required")
    return True, binding


def _backend_proof_record(data_dir: Path, operator: dict[str, object], phase: str) -> dict[str, object]:
    """Read the immutable phase proof written by the private backend verifier, never a bundle assertion alone."""
    try:
        record = json.loads((data_dir / f"topic22-backend-{phase}-proof.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("private backend proof is required") from error
    if not isinstance(record, dict) or not {"ok", "phase", "backend_bucket_proof_sha256", "observed_proof_sha256", "observed_at_utc", "revision"} <= set(record) or record.get("ok") is not True:
        raise ValueError("private backend proof is required")
    try:
        observed = _parse_timestamp(str(record["observed_at_utc"]))
    except ValueError as error:
        raise ValueError("private backend proof is required") from error
    if abs((datetime.now(UTC) - observed).total_seconds()) > 900 or not re.fullmatch(r"[0-9a-f]{40}", str(record.get("revision", ""))):
        raise ValueError("private backend proof is required")
    try:
        return validate_private_backend_gate(operator, {"phase": record["phase"], "state_object_present": phase == "initialized", "proof_sha256": record["observed_proof_sha256"]}, phase=phase)
    except (KeyError, ValueError) as error:
        raise ValueError("private backend proof is required") from error


def validate_initialized_backend_record(data_dir: Path, initialized: dict[str, object]) -> dict[str, object]:
    """Require the post-apply proof to describe the same private backend identity as the fresh bootstrap proof."""
    try:
        bootstrap = json.loads((data_dir / "topic22-backend-bootstrap-proof.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("private backend proof is required") from error
    fields = ("bucket_sha256", "prefix_sha256", "project_number_sha256", "revision")
    if not isinstance(bootstrap, dict) or initialized.get("phase") != "initialized" or any(not isinstance(initialized.get(name), str) or initialized.get(name) != bootstrap.get(name) for name in fields):
        raise ValueError("private backend proof is invalid")
    try:
        started, finished = _parse_timestamp(str(bootstrap["observed_at_utc"])), _parse_timestamp(str(initialized["observed_at_utc"]))
    except (KeyError, ValueError) as error:
        raise ValueError("private backend proof is invalid") from error
    if finished < started or (finished - started).total_seconds() > 900:
        raise ValueError("private backend proof is invalid")
    return initialized


def validate_private_bootstrap_contract(readback: object, project_id: str, backend_proof_sha256: str) -> dict[str, object]:
    """Classify a private fresh LRO or a reused empty project before normal Terraform authorization exists."""
    if not isinstance(readback, dict) or readback.get("mode") not in {"fresh", "reused"} or not isinstance(project_id, str) or not re.fullmatch(r"[0-9a-f]{64}", backend_proof_sha256):
        raise ValueError("bootstrap contract is invalid")
    project = readback.get("project")
    try:
        number = resource_manager_project_number(project, project_id)
    except ValueError as error:
        raise ValueError("bootstrap contract is invalid") from error
    enabled = readback.get("enabled_services")
    if not isinstance(project, dict) or project.get("state") != "ACTIVE" or readback.get("billing_linked") is not True or not isinstance(enabled, set) or not TOPIC22_REQUIRED_SERVICES <= enabled:
        raise ValueError("bootstrap contract is invalid")
    backend = readback.get("backend")
    if not isinstance(backend, dict) or backend.get("phase") != "bootstrap" or backend.get("state_object_present") is not False or backend.get("proof_sha256") != backend_proof_sha256:
        raise ValueError("bootstrap contract is invalid")
    if readback["mode"] == "fresh":
        lro = readback.get("project_lro")
        if not isinstance(lro, dict) or lro.get("done") is not True or not isinstance(lro.get("response"), dict):
            raise ValueError("bootstrap contract is invalid")
        try:
            if resource_manager_project_number(lro["response"], project_id) != number:
                raise ValueError("bootstrap contract is invalid")
        except ValueError as error:
            raise ValueError("bootstrap contract is invalid") from error
    extras = enabled - TOPIC22_REQUIRED_SERVICES
    return {
        "ok": True, "mode": str(readback["mode"]), "project_number_sha256": _hash(number),
        "extra_enabled_service_count": len(extras),
        "extra_enabled_services_sha256": _hash("\n".join(sorted(extras))),
    }


_REUSE_EMPTY_CATEGORIES = {
    "gke_clusters": ("container.googleapis.com", "clusters", "https://container.googleapis.com/v1/projects/{project}/locations/-/clusters", "clusters"),
    "artifact_repositories": ("artifactregistry.googleapis.com", "repositories", "https://artifactregistry.googleapis.com/v1/projects/{project}/locations/-/repositories", "repositories"),
    "storage_buckets": ("storage.googleapis.com", "items", "https://storage.googleapis.com/storage/v1/b?project={number}", "items"),
    "kms_key_rings": ("cloudkms.googleapis.com", "keyRings", "https://cloudkms.googleapis.com/v1/projects/{project}/locations/-/keyRings", "keyRings"),
    "iam_service_accounts": ("iam.googleapis.com", "accounts", "https://iam.googleapis.com/v1/projects/{project}/serviceAccounts", "accounts"),
    "billing_budgets": ("billingbudgets.googleapis.com", "budgets", "https://billingbudgets.googleapis.com/v1/billingAccounts/{billing}/budgets", "budgets"),
    "compute_instances": ("compute.googleapis.com", "instances", "https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/instances", "items"),
    "compute_migs": ("compute.googleapis.com", "instanceGroupManagers", "https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/instanceGroupManagers", "items"),
    "compute_forwarding_rules": ("compute.googleapis.com", "forwardingRules", "https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/forwardingRules", "items"),
    "compute_networks": ("compute.googleapis.com", "items", "https://compute.googleapis.com/compute/v1/projects/{project}/global/networks", "items"),
    "compute_subnetworks": ("compute.googleapis.com", "subnetworks", "https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/subnetworks", "items"),
    "compute_firewalls": ("compute.googleapis.com", "items", "https://compute.googleapis.com/compute/v1/projects/{project}/global/firewalls", "items"),
    "compute_addresses": ("compute.googleapis.com", "addresses", "https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/addresses", "items"),
    "project_iam": ("", "bindings", "https://cloudresourcemanager.googleapis.com/v3/projects/{project}:getIamPolicy", "bindings"),
}
_GOOGLE_DEFAULT_NETWORK = {"default"}
_GOOGLE_DEFAULT_FIREWALLS = {"default-allow-icmp", "default-allow-internal", "default-allow-rdp", "default-allow-ssh"}


def verify_reused_project_empty(
    call: Callable[[str, str, dict[str, object] | None], dict[str, object]],
    project_id: str,
    project_number: str,
    *,
    billing_account: str = "",
    enabled_services: set[str] | None = None,
    backend_bucket: str = "",
    page_limit: int = 20,
) -> dict[str, object]:
    """Fail closed unless the reused ACTIVE project has no Topic 22-relevant resources."""
    if page_limit < 1:
        raise ValueError("bootstrap contract is invalid")
    if not billing_account or enabled_services is None or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]", backend_bucket):
        raise ValueError("cannot prove reused project empty")
    observed: list[str] = []
    for category, (service, field, template, response_field) in _REUSE_EMPTY_CATEGORIES.items():
        if service and service not in enabled_services:
            raise ValueError("cannot prove reused project empty")
        base = template.format(project=quote(project_id, safe=""), number=quote(project_number, safe=""), billing=quote(billing_account, safe=""))
        token, seen = "", set()
        for _ in range(page_limit):
            separator = "&" if "?" in base else "?"
            page = call("GET", base if not token else f"{base}{separator}pageToken={quote(token, safe='')}")
            entries = page.get(response_field, {} if response_field == "items" and category.startswith("compute_") and category not in {"compute_networks", "compute_firewalls"} else [])
            if response_field == "items" and category.startswith("compute_") and category not in {"compute_networks", "compute_firewalls"}:
                if not isinstance(entries, dict) or any(not isinstance(value, dict) or not isinstance(value.get(field, []), list) for value in entries.values()):
                    raise ValueError("bootstrap contract is invalid")
                entries = [entry for value in entries.values() for entry in value.get(field, [])]
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                raise ValueError("bootstrap contract is invalid")
            if category == "billing_budgets":
                entries = [entry for entry in entries if f"projects/{project_number}" in (entry.get("budgetFilter", {}).get("projects", []) if isinstance(entry.get("budgetFilter"), dict) else [])]
            if category == "storage_buckets":
                entries = [entry for entry in entries if entry.get("name") != backend_bucket]
            if category == "compute_networks" and all(entry.get("name") in _GOOGLE_DEFAULT_NETWORK for entry in entries):
                entries = []
            if category == "compute_firewalls" and all(entry.get("name") in _GOOGLE_DEFAULT_FIREWALLS for entry in entries):
                entries = []
            if entries:
                raise ValueError("reused project is not empty")
            next_token = page.get("nextPageToken", "")
            if not isinstance(next_token, str) or (next_token and next_token in seen):
                raise ValueError("bootstrap contract is invalid")
            if not next_token:
                observed.append(category)
                break
            seen.add(next_token); token = next_token
        else:
            raise ValueError("bootstrap contract is invalid")
    return {"reused_project_empty": True, "reused_resource_category_count": len(observed), "reused_resource_categories_sha256": _hash("\n".join(observed))}


def _enabled_services_readback(
    call: Callable[[str, str, dict[str, object] | None], dict[str, object]], project_number: str, *, page_limit: int,
) -> set[str]:
    """Read the Service Usage enabled state before a reuse gate; malformed paging is never empty."""
    services, token, seen = set(), "", set()
    base = f"https://serviceusage.googleapis.com/v1/projects/{quote(project_number, safe='')}/services"
    for _ in range(page_limit):
        query = "?filter=state%3AENABLED" if not token else f"?filter=state%3AENABLED&pageToken={quote(token, safe='')}"
        listed = call("GET", f"{base}{query}")
        entries = listed.get("services", [])
        if not isinstance(entries, list):
            raise ValueError("bootstrap contract is invalid")
        for item in entries:
            if not isinstance(item, dict) or not isinstance(item.get("config"), dict):
                raise ValueError("bootstrap contract is invalid")
            name = item["config"].get("name")
            if item.get("state") == "ENABLED" and isinstance(name, str):
                services.add(name)
            else:
                raise ValueError("bootstrap contract is invalid")
        next_token = listed.get("nextPageToken", "")
        if not isinstance(next_token, str) or (next_token and next_token in seen):
            raise ValueError("bootstrap contract is invalid")
        if not next_token:
            return services
        seen.add(next_token); token = next_token
    raise ValueError("bootstrap contract is invalid")


def validate_private_bootstrap_authorization(operator: dict[str, object], account: dict[str, object], *, workspace: Path | None = None) -> dict[str, object]:
    """Require a current private monetary authorization and verified VND billing account before any bootstrap write."""
    paths = operator.get("resolved_paths")
    path = paths.get("bootstrap_authorization") if isinstance(paths, dict) else None
    if not isinstance(path, Path):
        raise ValueError("bootstrap authorization is invalid")
    try:
        authorization = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("bootstrap authorization is invalid") from error
    required = {
        "operator_approved", "forecast_sha256", "revision", "trial_credit_vnd", "current_spend_vnd",
        "console_spend_vnd", "forecast_vnd", "trial_expires_at", "conversion_observed_at", "spend_observed_at",
        "requested_ttl_hours", "project_parent",
    }
    if not isinstance(authorization, dict) or set(authorization) != required or authorization.get("operator_approved") is not True:
        raise ValueError("bootstrap authorization is invalid")
    if account.get("billing_account_open") is not True or account.get("billing_currency_vnd") is not True:
        raise ValueError("bootstrap authorization is invalid")
    scalar_names = required - {"operator_approved", "forecast_sha256", "revision", "project_parent"}
    if any(authorization.get(name) != operator.get(name) for name in scalar_names):
        raise ValueError("bootstrap authorization is invalid")
    if not isinstance(authorization.get("forecast_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", authorization["forecast_sha256"]) or not isinstance(authorization.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", authorization["revision"]):
        raise ValueError("bootstrap authorization is invalid")
    if workspace is not None:
        forecast = workspace / "evidence" / "04_2_llm_design" / "gke" / "cost_forecast_topic22.json"
        if not forecast.is_file() or hashlib.sha256(forecast.read_bytes()).hexdigest() != authorization["forecast_sha256"] or authorization["revision"] != _private_current_revision(workspace):
            raise ValueError("bootstrap authorization is invalid")
    try:
        envelope_path = (workspace or Path.cwd()) / "configs" / "gke" / "cost_envelope.yaml"
        envelope = yaml.safe_load(envelope_path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or envelope.get("terraform_budget_usd") != 240 or envelope.get("pre_deployment_forecast_ceiling_usd") != 180:
            raise ValueError("bootstrap authorization is invalid")
        verdict = evaluate_live_budget(
            envelope,
            current_spend_vnd=float(authorization["current_spend_vnd"]), console_spend_vnd=float(authorization["console_spend_vnd"]),
            forecast_vnd=float(authorization["forecast_vnd"]), trial_credit_vnd=float(authorization["trial_credit_vnd"]),
            conversion_observed_at=str(authorization["conversion_observed_at"]), spend_observed_at=str(authorization["spend_observed_at"]),
            requested_ttl_hours=float(authorization["requested_ttl_hours"]), trial_expires_at=str(authorization["trial_expires_at"]),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("bootstrap authorization is invalid") from error
    if verdict.get("ok") is not True:
        raise ValueError("bootstrap authorization is invalid")
    if not isinstance(authorization.get("project_parent"), str) or authorization["project_parent"] not in {"none"} and not re.fullmatch(r"(?:folders|organizations)/[0-9]+", authorization["project_parent"]):
        raise ValueError("bootstrap authorization is invalid")
    return authorization


def validate_private_bootstrap_authorities(
    call: Callable[[str, str, dict[str, object] | None], dict[str, object]],
    *, project_id: str, project_number: str, billing_account: str, project_parent: str, mode: str,
) -> None:
    """Use only supported scope-specific testIamPermissions calls, rejecting partial grants."""
    endpoints: dict[str, tuple[str, tuple[str, ...]]] = {
        "billing_association": (f"https://cloudbilling.googleapis.com/v1/billingAccounts/{quote(billing_account, safe='')}:testIamPermissions", TOPIC22_BOOTSTRAP_AUTHORITY_GATES["billing_association"][1] + (("billing.budgets.list",) if mode == "reused" else ())),
        "project_operations": (f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(project_id, safe='')}:testIamPermissions", TOPIC22_BOOTSTRAP_AUTHORITY_GATES["project_billing_assignment"][1] + TOPIC22_BOOTSTRAP_AUTHORITY_GATES["service_usage_read_enable"][1] + TOPIC22_BOOTSTRAP_AUTHORITY_GATES["backend_storage"][1] + TOPIC22_BOOTSTRAP_AUTHORITY_GATES["reuse_inventory"][1]),
    }
    if mode == "fresh" and project_parent != "none":
        endpoints["parent_project_create"] = (f"https://cloudresourcemanager.googleapis.com/v3/{quote(project_parent, safe='/')}:testIamPermissions", TOPIC22_BOOTSTRAP_AUTHORITY_GATES["parent_project_create"][1])
    for service in sorted(TOPIC22_REQUIRED_SERVICES):
        endpoints[f"service_bind:{service}"] = (f"https://servicemanagement.googleapis.com/v1/services/{quote(service, safe='')}:testIamPermissions", TOPIC22_BOOTSTRAP_AUTHORITY_GATES["service_bind"][1])
    for _name, (url, permissions) in endpoints.items():
        result = call("POST", url, {"permissions": list(permissions)})
        granted = result.get("permissions")
        if not isinstance(granted, list) or set(granted) != set(permissions) or len(granted) != len(set(granted)):
            raise ValueError("bootstrap authority is invalid")


def private_project_create_payload(project_id: str, project_parent: str) -> dict[str, str]:
    """Create v3 project payload without inventing a parent for a personal-trial account."""
    if not isinstance(project_id, str) or not project_id or not isinstance(project_parent, str):
        raise ValueError("bootstrap authorization is invalid")
    if project_parent == "none":
        return {"projectId": project_id}
    if not re.fullmatch(r"(?:folders|organizations)/[0-9]+", project_parent):
        raise ValueError("bootstrap authorization is invalid")
    return {"projectId": project_id, "parent": project_parent}


def execute_private_bootstrap(
    operator: dict[str, object],
    *,
    token_runner: Callable[[list[str], dict[str, str]], str] | None = None,
    requester: Callable[[str, str, dict[str, str], dict[str, object] | None], dict[str, object]] = _rest_request,
    backend_verifier: Callable[..., dict[str, object]] = verify_private_backend_bundle,
    poll_limit: int = 20,
    workspace: Path | None = None,
) -> dict[str, object]:
    """Execute the private create-or-reuse bootstrap protocol and return only its redacted proof."""
    paths, project_id, billing = operator.get("resolved_paths"), operator.get("project_id"), operator.get("billing_account_id")
    if not isinstance(paths, dict) or not isinstance(project_id, str) or not isinstance(billing, str) or poll_limit < 1:
        raise ValueError("bootstrap contract is invalid")
    config, adc = paths.get("gcloud_config_dir"), paths.get("application_default_credentials")
    if not isinstance(config, Path) or not isinstance(adc, Path):
        raise ValueError("bootstrap contract is invalid")
    data_dir = paths.get("tf_data_dir")
    if not isinstance(data_dir, Path):
        raise ValueError("bootstrap contract is invalid")
    completed = {"project_create_requested": False, "project_created": False, "billing_linked": False, "apis_enabled": False, "backend_bucket_created": False}
    phase = ["project_create"]

    def partial_stop(reason: str, error: BaseException) -> None:
        if any(completed.values()):
            write_bootstrap_partial_handoff(data_dir, phase=reason, completed=completed)
        raise ValueError("bootstrap contract is invalid") from error
    environment = {**os.environ, "CLOUDSDK_CONFIG": str(config), "GOOGLE_APPLICATION_CREDENTIALS": str(adc)}
    runner = _run_gcloud_private if token_runner is None else token_runner
    token = runner(["gcloud", "auth", "print-access-token"], environment).strip()
    if not token:
        raise ValueError("bootstrap contract is invalid")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def call(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        try:
            value = requester(method, url, headers, payload)
        except urllib.error.HTTPError:
            if any(completed.values()):
                write_bootstrap_partial_handoff(data_dir, phase=phase[0], completed=completed)
            raise
        except (OSError, ValueError, TypeError) as error:
            partial_stop(phase[0], error)
        if not isinstance(value, dict):
            raise ValueError("bootstrap contract is invalid")
        return value

    def complete_lro(operation: dict[str, object], *, api_base: str, response_required: bool) -> dict[str, object]:
        current = operation
        for _ in range(poll_limit):
            if current.get("done") is True:
                if current.get("error") is not None or (response_required and not isinstance(current.get("response"), dict)):
                    raise ValueError("bootstrap contract is invalid")
                return current
            name = current.get("name")
            if not isinstance(name, str) or not re.fullmatch(r"operations/[A-Za-z0-9._/-]+", name):
                raise ValueError("bootstrap contract is invalid")
            current = call("GET", f"{api_base}/{name}")
        raise ValueError("bootstrap contract is invalid")

    account = call("GET", f"https://cloudbilling.googleapis.com/v1/billingAccounts/{quote(billing, safe='')}")
    if account.get("name") != f"billingAccounts/{billing}":
        raise ValueError("bootstrap authorization is invalid")
    authorization = validate_private_bootstrap_authorization(operator, {
        "billing_account_open": account.get("open") is True,
        "billing_currency_vnd": account.get("currencyCode") == "VND",
    }, workspace=workspace)
    try:
        project = call("GET", f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(project_id, safe='')}")
        mode, lro = "reused", None
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise ValueError("bootstrap contract is invalid") from None
        parent = str(authorization["project_parent"])
        if parent != "none":
            parent_permission = TOPIC22_BOOTSTRAP_AUTHORITY_GATES["parent_project_create"][1]
            parent_result = call("POST", f"https://cloudresourcemanager.googleapis.com/v3/{quote(parent, safe='/')}:testIamPermissions", {"permissions": list(parent_permission)})
            if parent_result.get("permissions") != list(parent_permission):
                raise ValueError("bootstrap authority is invalid")
        create_operation = call("POST", "https://cloudresourcemanager.googleapis.com/v3/projects", private_project_create_payload(project_id, parent))
        completed["project_create_requested"] = True
        try:
            lro = complete_lro(create_operation, api_base="https://cloudresourcemanager.googleapis.com/v3", response_required=True)
            completed["project_created"] = True
            project = call("GET", f"https://cloudresourcemanager.googleapis.com/v3/projects/{quote(project_id, safe='')}")
        except (OSError, ValueError, TypeError, urllib.error.HTTPError) as error:
            partial_stop("project_create", error)
        mode = "fresh"
    try:
        project_number = resource_manager_project_number(project, project_id)
        if project.get("state") != "ACTIVE":
            raise ValueError("bootstrap contract is invalid")
    except (ValueError, TypeError, KeyError) as error:
        partial_stop("project_create", error)
    try:
        validate_private_bootstrap_authorities(call, project_id=project_id, project_number=project_number, billing_account=billing, project_parent=str(authorization["project_parent"]), mode=mode)
        backend_config = _backend_values(Path(paths["terraform_backend_config"]))
    except (OSError, ValueError, TypeError) as error:
        partial_stop("project_create", error)
    reuse_proof: dict[str, object] = {}
    if mode == "reused":
        if operator.get("backend_bucket_preexists") is not True:
            raise ValueError("backend bootstrap is invalid")
        preexisting_backend = backend_verifier(operator, phase="bootstrap")
        validate_private_backend_gate(operator, preexisting_backend, phase="bootstrap")
        enabled_before_mutation = _enabled_services_readback(call, project_number, page_limit=poll_limit)
        reuse_proof = verify_reused_project_empty(call, project_id, project_number, billing_account=billing, enabled_services=enabled_before_mutation, backend_bucket=backend_config["bucket"], page_limit=poll_limit)
    elif operator.get("backend_bucket_preexists") is not False:
        raise ValueError("backend bootstrap is invalid")
    phase[0] = "billing_link"
    linked = call("PUT", f"https://cloudbilling.googleapis.com/v1/projects/{quote(project_id, safe='')}/billingInfo", {"billingAccountName": f"billingAccounts/{billing}"})
    if linked.get("billingEnabled") is not True or linked.get("billingAccountName") != f"billingAccounts/{billing}":
        partial_stop("billing_link", ValueError("billing link readback"))
    if mode == "fresh":
        completed["billing_linked"] = True
    service_parent = f"projects/{project_number}"
    phase[0] = "api_enable"
    try:
        complete_lro(call("POST", f"https://serviceusage.googleapis.com/v1/{service_parent}/services:batchEnable", {"serviceIds": sorted(TOPIC22_REQUIRED_SERVICES)}), api_base="https://serviceusage.googleapis.com/v1", response_required=False)
        if mode == "fresh":
            completed["apis_enabled"] = True
        services = _enabled_services_readback(call, project_number, page_limit=poll_limit)
    except (OSError, ValueError, TypeError, urllib.error.HTTPError) as error:
        if mode == "fresh":
            ensure_partial_handoff(data_dir, phase="api_enable", completed=completed)
        raise ValueError("bootstrap contract is invalid") from error
    if mode == "fresh":
        proof = create_private_backend_bucket(call, bucket=backend_config["bucket"], prefix=backend_config["prefix"], project_number=project_number, data_dir=data_dir, completed=completed)
    else:
        proof = preexisting_backend
    readback = {"mode": mode, "project": project, "billing_linked": True, "enabled_services": services, "backend": proof, **reuse_proof}
    if lro is not None:
        readback["project_lro"] = lro
    bootstrap_binding = proof.get("proof_sha256") if mode == "fresh" else operator.get("backend_bucket_proof_sha256")
    proof = validate_private_bootstrap_contract(readback, project_id, str(bootstrap_binding))
    durable_proof = {**proof, "forecast_sha256": authorization["forecast_sha256"], "revision": authorization["revision"]}
    write_immutable_json(data_dir / "topic22-bootstrap-proof.json", durable_proof)
    return durable_proof


def recovery_attestation_ok(attestation: object, recovery_sink: str) -> bool:
    """Require two independent, timestamped, hash-only custodian attestations for recovery."""
    if not isinstance(attestation, dict) or set(attestation) != {"approved", "encrypted", "outside_workspace", "sink_uri_sha256", "attestations"}:
        return False
    entries = attestation.get("attestations")
    if attestation.get("approved") is not True or attestation.get("encrypted") is not True or attestation.get("outside_workspace") is not True or attestation.get("sink_uri_sha256") != _hash(recovery_sink) or not isinstance(entries, list) or len(entries) != 2:
        return False
    custodians: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"custodian_sha256", "approved_at_utc", "provenance_sha256"}:
            return False
        custodian, provenance, timestamp = entry.get("custodian_sha256"), entry.get("provenance_sha256"), entry.get("approved_at_utc")
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in (custodian, provenance)):
            return False
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            return False
        custodians.add(str(custodian))
    return len(custodians) == 2


def build_terraform_runtime_contract(
    *,
    backend_config: str | Path,
    tfvars: str | Path,
    tf_data_dir: str | Path,
    workspace: Path,
    backend_bucket_preexists: bool,
    backend_bucket_proof_sha256: str,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, object]:
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))
    config = validate_private_backend_config(backend_config, workspace, validator)
    variables = validator(Path(tfvars), "terraform_tfvars")
    data_dir = validator(Path(tf_data_dir), "tf_data_dir")
    if backend_bucket_preexists is not True or not re.fullmatch(r"[0-9a-f]{64}", backend_bucket_proof_sha256 or ""):
        raise ValueError("pre-existing backend bucket proof is required")
    _reject_repository_terraform_runtime(workspace)
    plan_path = data_dir / "topic22.tfplan"
    common = ["terraform", "-chdir=infra/terraform/edai2"]
    return {
        "environment": {"TF_DATA_DIR": str(data_dir)},
        "init": [*common, "init", "-reconfigure", f"-backend-config={config}"],
        "plan": [*common, "plan", f"-var-file={variables}", f"-out={plan_path}"],
        "apply": [*common, "apply", str(plan_path)],
        "backend_bucket_proof_sha256": backend_bucket_proof_sha256,
    }


def execute_private_terraform_action(
    contract_path: str | Path,
    operator: dict[str, object],
    action: str,
    *,
    approval: dict[str, object] | None = None,
    runner: Callable[[list[str], dict[str, str]], str] | None = None,
    workspace: Path | None = None,
) -> dict[str, object]:
    """Run one fixed action from an ignored contract; raw process output never crosses this boundary."""
    if action not in {"init", "plan", "apply"} or not isinstance(operator.get("resolved_paths"), dict):
        raise ValueError("private Terraform action is invalid")
    paths = operator["resolved_paths"]
    data_dir = paths.get("tf_data_dir")
    config_dir = paths.get("gcloud_config_dir")
    adc = paths.get("application_default_credentials")
    if not all(isinstance(value, Path) for value in (data_dir, config_dir, adc)):
        raise ValueError("private Terraform action is invalid")
    _backend_proof_record(data_dir, operator, "bootstrap")
    contract_file = Path(contract_path).resolve()
    if contract_file != data_dir.resolve() / "topic22-terraform-runtime.json":
        raise ValueError("private Terraform action is invalid")
    document = json.loads(contract_file.read_text(encoding="utf-8"))
    command = document.get(action) if isinstance(document, dict) else None
    environment = document.get("environment") if isinstance(document, dict) else None
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command) or not isinstance(environment, dict) or environment.get("TF_DATA_DIR") != str(data_dir):
        raise ValueError("private Terraform action is invalid")
    if workspace is not None:
        config, tfvars = paths.get("terraform_backend_config"), paths.get("terraform_tfvars")
        if not isinstance(config, Path) or not isinstance(tfvars, Path):
            raise ValueError("private Terraform action is invalid")
        backend_preexists, backend_binding = _bootstrap_backend_binding(operator, data_dir)
        expected = build_terraform_runtime_contract(
            backend_config=config, tfvars=tfvars, tf_data_dir=data_dir, workspace=workspace,
            backend_bucket_preexists=backend_preexists,
            backend_bucket_proof_sha256=backend_binding,
        )
        if document != expected:
            raise ValueError("private Terraform contract is invalid")
    private_environment = dict(os.environ)
    private_environment.update({"TF_DATA_DIR": str(data_dir), "CLOUDSDK_CONFIG": str(config_dir), "GOOGLE_APPLICATION_CREDENTIALS": str(adc)})
    plan_path = data_dir / "topic22.tfplan"
    if action == "apply":
        if approval is None:
            approval_path = data_dir / "topic22-approval.json"
            try:
                approval = json.loads(approval_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("approved private Terraform plan is required") from error
        if not isinstance(approval, dict) or set(approval) != {"operator_approved", "plan_sha256", "forecast_sha256", "revision"} or approval.get("operator_approved") is not True or not plan_path.is_file():
            raise ValueError("approved private Terraform plan is required")
        try:
            binding = json.loads((data_dir / "topic22-runtime-binding.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("approved private Terraform plan is required") from error
        plan_sha256, forecast_sha256, revision = approval.get("plan_sha256"), approval.get("forecast_sha256"), approval.get("revision")
        if not isinstance(binding, dict) or set(binding) != {"forecast_sha256", "revision"} or plan_sha256 != hashlib.sha256(plan_path.read_bytes()).hexdigest() or forecast_sha256 != binding.get("forecast_sha256") or revision != binding.get("revision") or not isinstance(forecast_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", forecast_sha256) or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("approved private Terraform plan is required")
        if workspace is not None:
            current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
            if revision != current:
                raise ValueError("approved private Terraform plan is required")
    executor = runner or (lambda argv, env: subprocess.run(argv, env=env, check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    raw = executor(command, private_environment)
    raw = ""
    if action != "apply":
        return {"ok": True, "action": action}
    return {"ok": True, "action": "apply", "plan_sha256": approval["plan_sha256"], "forecast_sha256": approval["forecast_sha256"], "revision": approval["revision"]}


def write_terraform_runtime_contract(
    *,
    backend_config: str | Path,
    tfvars: str | Path,
    tf_data_dir: str | Path,
    workspace: Path,
    backend_bucket_proof_sha256: str,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> Path:
    """Atomically persist the sole private plan/apply command contract for an operator."""
    contract = build_terraform_runtime_contract(
        backend_config=backend_config, tfvars=tfvars, tf_data_dir=tf_data_dir, workspace=workspace,
        backend_bucket_preexists=True, backend_bucket_proof_sha256=backend_bucket_proof_sha256,
        path_validator=path_validator,
    )
    destination = Path(tf_data_dir).resolve() / "topic22-terraform-runtime.json"
    if destination.exists():
        raise FileExistsError("private Terraform runtime contract already exists")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=destination.parent, suffix=".tmp") as handle:
        json.dump(contract, handle, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def build_backend_init_command(value: str | Path, workspace: Path, path_validator: Callable[[Path, str], Path] | None = None) -> list[str]:
    """Return the only allowed Topic 22 initialization form for future plan/apply execution."""
    config = validate_private_backend_config(value, workspace, path_validator)
    _reject_repository_terraform_runtime(workspace)
    return ["terraform", "-chdir=infra/terraform/edai2", "init", "-reconfigure", f"-backend-config={config}"]


def validate_billing_selectors(markers: object, pii: object) -> tuple[list[str], list[str]]:
    """Delegate both standalone CLIs to the same selector policy."""
    return _shared_validate_billing_selectors(markers, pii)


def load_operator_inputs(
    value: str | Path,
    workspace: Path,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, Any]:
    """Delegate both standalone CLIs to the same private-bundle contract."""
    return _shared_load_operator_inputs(value, workspace, path_validator)


def write_redacted_account_summary(
    operator_inputs: str | Path,
    output: str | Path,
    workspace: Path,
    *,
    operator_loader: Callable[..., dict[str, Any]] = load_operator_inputs,
    adapter_factory: Callable[[str, str, dict[str, str]], object] | None = None,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> int:
    """Write an immutable read-only account summary containing fingerprints only."""
    destination = Path(output)
    try:
        operator = operator_loader(operator_inputs, workspace, path_validator)
        private_environment = dict(os.environ)
        private_environment.update({
            "CLOUDSDK_CONFIG": str(operator["resolved_paths"]["gcloud_config_dir"]),
            "GOOGLE_APPLICATION_CREDENTIALS": str(operator["resolved_paths"]["application_default_credentials"]),
        })
        if adapter_factory is None:
            adapter = GcloudRestExternalAdapter(
                operator["project_id"], operator["billing_account_id"],
                token_supplier=lambda: _run_gcloud_private(["gcloud", "auth", "print-access-token"], private_environment),
            )
        else:
            adapter = adapter_factory(operator["project_id"], operator["billing_account_id"], private_environment)
        project, billing = adapter.project(), adapter.billing()
        hashes = (
            project.get("project_sha256"), project.get("project_number_sha256"),
            billing.get("billing_account_sha256"),
        )
        if project.get("active") is not True or billing.get("linked") is not True or billing.get("billing_link_hash_matches") is not True or billing.get("billing_account_name_matches") is not True or billing.get("billing_account_open") is not True or billing.get("billing_currency_vnd") is not True or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise ValueError("account readback failed")
        write_immutable_json(destination, {
            "schema_version": 1, "ok": True, "project_active": True,
            "project_alias_sha256": hashes[0], "project_number_sha256": hashes[1],
            "billing_linked": True, "billing_link_hash_matches": True,
            "billing_account_name_matches": True, "billing_account_open": True, "billing_currency_vnd": True,
            "billing_account_sha256": hashes[2],
        })
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, subprocess.SubprocessError):
        if not destination.exists():
            write_immutable_json(destination, {"schema_version": 1, "ok": False, "failures": ["account_summary"]})
        return 2


def _run_get_credentials_redacted(command: list[str], environment: dict[str, str]) -> None:
    completed = subprocess.run(command, env=environment, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise ValueError("private kube credential bootstrap failed")


def _run_gcloud_private(command: list[str], environment: dict[str, str]) -> str:
    completed = subprocess.run(command, env=environment, check=True, capture_output=True, text=True, encoding="utf-8")
    value = completed.stdout.strip()
    if not value:
        raise ValueError("private gcloud result is empty")
    return value


def _bind_private_kube_document(document: object, project_id: str) -> dict[str, object]:
    """Accept only the one GKE context emitted for this private project and fixed cluster."""
    if not isinstance(document, dict):
        raise ValueError("private kubeconfig is invalid")
    expected = f"gke_{project_id}_us-central1-a_edai2"
    contexts, clusters, users, current = (document.get("contexts"), document.get("clusters"), document.get("users"), document.get("current-context"))
    if not all(isinstance(value, list) for value in (contexts, clusters, users)) or current != expected:
        raise ValueError("private kubeconfig is invalid")
    selected_context = [entry for entry in contexts if isinstance(entry, dict) and entry.get("name") == expected]
    selected_cluster = [entry for entry in clusters if isinstance(entry, dict) and entry.get("name") == expected]
    selected_user = [entry for entry in users if isinstance(entry, dict) and entry.get("name") == expected]
    if len(contexts) != 1 or len(clusters) != 1 or len(users) != 1 or len(selected_context) != 1 or len(selected_cluster) != 1 or len(selected_user) != 1:
        raise ValueError("private kubeconfig is invalid")
    context = selected_context[0].get("context")
    cluster = selected_cluster[0].get("cluster")
    if not isinstance(context, dict) or context.get("cluster") != expected or context.get("user") != expected or not isinstance(cluster, dict):
        raise ValueError("private kubeconfig is invalid")
    server = cluster.get("server")
    try:
        parsed = urlsplit(server) if isinstance(server, str) else None
    except ValueError:
        parsed = None
    if not parsed or parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError("private kubeconfig is invalid")
    selected_context[0]["name"] = "edai2-gke"
    selected_context[0]["context"] = {**context, "cluster": "edai2-gke", "user": "edai2-gke"}
    selected_cluster[0]["name"] = "edai2-gke"
    selected_user[0]["name"] = "edai2-gke"
    document["current-context"] = "edai2-gke"
    return document


def prepare_private_kube_target(
    operator_inputs: str | Path,
    workspace: Path,
    *,
    operator_loader: Callable[..., dict[str, Any]] = load_operator_inputs,
    runner: Callable[[list[str], dict[str, str]], None] = _run_get_credentials_redacted,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, object]:
    """Create a dedicated private kubeconfig and a redacted fixed-context helper."""
    workspace = workspace.resolve()
    bundle = _private_topic22_path(Path(operator_inputs), workspace)
    operator = operator_loader(bundle, workspace, path_validator)
    runtime_root = bundle.parent.resolve()
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))
    if Path(validator(runtime_root, "kube_runtime_dir")).resolve() != runtime_root:
        raise ValueError("private kube runtime path is invalid")
    kubeconfig, helper = runtime_root / "kubeconfig", runtime_root / "kube-target.json"
    if kubeconfig.exists() or helper.exists():
        raise FileExistsError("private kube target already exists")
    environment = dict(os.environ)
    environment.update({
        "CLOUDSDK_CORE_PROJECT": operator["project_id"],
        "CLOUDSDK_CONFIG": str(operator["resolved_paths"]["gcloud_config_dir"]),
        "GOOGLE_APPLICATION_CREDENTIALS": str(operator["resolved_paths"]["application_default_credentials"]),
        "KUBECONFIG": str(kubeconfig),
    })
    command = ["gcloud", "container", "clusters", "get-credentials", "edai2", "--zone", "us-central1-a"]
    try:
        runner(command, environment)
        document = _bind_private_kube_document(yaml.safe_load(kubeconfig.read_text(encoding="utf-8")), str(operator["project_id"]))
        temporary = kubeconfig.with_name(".kubeconfig.tmp")
        temporary.write_text(yaml.safe_dump(document, sort_keys=True), encoding="utf-8")
        os.replace(temporary, kubeconfig)
        target = {"schema_version": 1, "kubeconfig": kubeconfig.relative_to(workspace).as_posix(), "context": "edai2-gke", "zone": "us-central1-a"}
        write_immutable_json(helper, target)
        return target
    except BaseException:
        kubeconfig.unlink(missing_ok=True)
        (runtime_root / ".kubeconfig.tmp").unlink(missing_ok=True)
        raise


def dispatch_private_helper(
    args: argparse.Namespace,
    workspace: Path,
    *,
    account_writer: Callable[..., int] = write_redacted_account_summary,
    kube_preparer: Callable[..., dict[str, object]] = prepare_private_kube_target,
    operator_loader: Callable[..., dict[str, Any]] = load_operator_inputs,
    terraform_executor: Callable[..., dict[str, object]] = execute_private_terraform_action,
    backend_verifier: Callable[..., dict[str, object]] = verify_private_backend_bundle,
    bootstrap_executor: Callable[..., dict[str, object]] = execute_private_bootstrap,
    wi_writer: Callable[..., Path] | None = None,
    terraform_output_runner: Callable[[list[str], dict[str, str]], str] | None = None,
    helm_runner: Callable[[list[str]], str] | None = None,
) -> int | None:
    """Dispatch exactly one private helper mode without invoking budget evaluation."""
    selected = int(bool(args.redacted_account_summary)) + int(bool(args.prepare_kube_target)) + int(bool(args.private_terraform_action)) + int(bool(args.verify_private_backend)) + int(bool(args.private_bootstrap)) + int(bool(args.write_private_wi_values))
    if selected == 0:
        return None
    if selected != 1 or not args.operator_inputs:
        return 2
    if args.redacted_account_summary:
        if not args.output:
            return 2
        return account_writer(args.operator_inputs, args.output, workspace)
    if args.output:
        return 2
    if args.prepare_kube_target:
        kube_preparer(args.operator_inputs, workspace)
        return 0
    operator = operator_loader(args.operator_inputs, workspace)
    if args.write_private_wi_values:
        try:
            bindings = read_private_workload_identity_bindings(operator, terraform_output_runner)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
            return 2
        writer = write_private_workload_identity_helm_values if wi_writer is None else wi_writer
        combined = writer(bindings, workspace / "tmp" / "edai2-gcp" / "topic22-workload-identity-values.yaml", workspace)
        validate_private_wi_helm_consumers(bindings, combined, workspace, runner=helm_runner)
        return 0
    if args.private_bootstrap:
        bootstrap_executor(operator, workspace=workspace)
        return 0
    if args.verify_private_backend:
        proof = backend_verifier(operator, phase=args.verify_private_backend)
        gate = validate_private_backend_gate(operator, proof, phase=args.verify_private_backend)
        paths = operator.get("resolved_paths") if isinstance(operator, dict) else None
        if not isinstance(paths, dict) or not isinstance(paths.get("tf_data_dir"), Path):
            return 2
        revision = _private_current_revision(workspace)
        write_immutable_json(paths["tf_data_dir"] / f"topic22-backend-{args.verify_private_backend}-proof.json", {**gate, "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "revision": revision})
        return 0
    paths = operator.get("resolved_paths") if isinstance(operator, dict) else None
    if not isinstance(paths, dict) or not isinstance(paths.get("tf_data_dir"), Path):
        return 2
    terraform_executor(paths["tf_data_dir"] / "topic22-terraform-runtime.json", operator, args.private_terraform_action, workspace=workspace)
    if args.private_terraform_action == "apply":
        proof = backend_verifier(operator, phase="initialized")
        gate = validate_private_backend_gate(operator, proof, phase="initialized")
        revision = _private_current_revision(workspace)
        initialized = {**gate, "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "revision": revision}
        validate_initialized_backend_record(paths["tf_data_dir"], initialized)
        write_immutable_json(paths["tf_data_dir"] / "topic22-backend-initialized-proof.json", initialized)
    return 0


_WORKLOAD_KSAS = {
    "retrieval": "edai2-retrieval-agent", "drift": "edai2-drift-agent",
    "coordinator": "edai2-coordinator", "workers": "edai2-worker",
}


def read_private_workload_identity_bindings(
    operator: dict[str, object],
    runner: Callable[[list[str], dict[str, str]], str] | None = None,
) -> dict[str, object]:
    """Read the sole sensitive Terraform WI output in memory; never persist raw principals."""
    paths = operator.get("resolved_paths") if isinstance(operator, dict) else None
    if not isinstance(paths, dict):
        raise ValueError("private workload identity output is invalid")
    data_dir = paths.get("tf_data_dir")
    config_dir = paths.get("gcloud_config_dir")
    adc = paths.get("application_default_credentials")
    if not all(isinstance(value, Path) for value in (data_dir, config_dir, adc)):
        raise ValueError("private workload identity output is invalid")
    environment = dict(os.environ)
    environment.update({"TF_DATA_DIR": str(data_dir), "CLOUDSDK_CONFIG": str(config_dir), "GOOGLE_APPLICATION_CREDENTIALS": str(adc)})
    command = ["terraform", "-chdir=infra/terraform/edai2", "output", "-json", "workload_identity_bindings"]
    execute = runner or (lambda argv, env: subprocess.run(argv, env=env, check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    bindings = json.loads(execute(command, environment))
    if not isinstance(bindings, dict) or set(bindings) != set(_WORKLOAD_KSAS):
        raise ValueError("private workload identity output is invalid")
    for workload in _WORKLOAD_KSAS:
        workload_identity_helm_values(bindings, workload)
    return bindings


def workload_identity_helm_values(bindings: dict[str, object], workload: str) -> dict[str, object]:
    """Translate sanitized Terraform WI output into an exact Helm ServiceAccount override."""
    expected_ksa = _WORKLOAD_KSAS.get(workload)
    entry = bindings.get(workload) if isinstance(bindings, dict) else None
    if not expected_ksa or not isinstance(entry, dict):
        raise ValueError("workload identity binding is invalid")
    ksa, gsa = entry.get("ksa"), entry.get("gsa")
    if not isinstance(ksa, str) or not ksa.endswith(f"[edai2:{expected_ksa}]") or not isinstance(gsa, str) or "@" not in gsa:
        raise ValueError("workload identity binding is invalid")
    return {"serviceAccount": {"name": expected_ksa, "annotations": {"iam.gke.io/gcp-service-account": gsa}}}


def write_private_workload_identity_helm_values(
    bindings: dict[str, object],
    destination: Path,
    workspace: Path,
    *,
    path_validator: Callable[[Path, str], Path] | None = None,
    ignore_checker: Callable[[Path], bool] | None = None,
) -> Path:
    """Atomically materialize all four exact Terraform WI bindings as private Helm values."""
    values = {workload: workload_identity_helm_values(bindings, workload) for workload in _WORKLOAD_KSAS}
    workspace = workspace.resolve()
    expected = workspace / "tmp" / "edai2-gcp" / "topic22-workload-identity-values.yaml"
    if destination.resolve() != expected.resolve():
        raise ValueError("private workload identity values destination is invalid")
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))
    if Path(validator(expected.parent, "workload_identity_values_dir")).resolve() != expected.parent.resolve():
        raise ValueError("private workload identity values destination is invalid")
    is_ignored = ignore_checker or (lambda candidate: subprocess.run(["git", "check-ignore", "--quiet", "--", str(candidate)], cwd=workspace, capture_output=True, check=False).returncode == 0)
    if not is_ignored(expected):
        raise ValueError("private workload identity values destination is invalid")
    destination = expected
    if destination.exists():
        raise FileExistsError("private workload identity values already exist")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=destination.parent, suffix=".tmp") as handle:
        yaml.safe_dump(values, handle, sort_keys=True)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def validate_private_wi_helm_consumers(
    bindings: dict[str, object], combined: Path, workspace: Path, *, runner: Callable[[list[str]], str] | None = None,
) -> None:
    """Render/lint all four private WI mappings; raw chart output and temporary values never escape."""
    if not isinstance(combined, Path) or not combined.is_file():
        raise ValueError("private workload identity values are invalid")
    work = {"retrieval": ("infra/helm/edai2/service-agent", "infra/helm/edai2/values/retrieval-agent.yaml"), "drift": ("infra/helm/edai2/service-agent", "infra/helm/edai2/values/drift-agent.yaml"), "coordinator": ("infra/helm/edai2/service-agent", "infra/helm/edai2/values/coordinator-agent.yaml"), "workers": ("infra/helm/edai2/worker", None)}
    execute = runner or (lambda argv: subprocess.run(argv, cwd=workspace, check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    private_root = combined.parent
    for workload, (chart, base) in work.items():
        values = workload_identity_helm_values(bindings, workload)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=private_root, suffix=".yaml") as handle:
            yaml.safe_dump(values, handle, sort_keys=True); temporary = Path(handle.name)
        try:
            inputs = ["-f", str(temporary)] if base is None else ["-f", base, "-f", str(temporary)]
            execute(["helm", "lint", chart, *inputs])
            rendered = execute(["helm", "template", workload, chart, *inputs])
            expected = values["serviceAccount"]
            annotation = expected["annotations"]["iam.gke.io/gcp-service-account"]
            documents = list(yaml.safe_load_all(rendered))
            service_accounts = [document for document in documents if isinstance(document, dict) and document.get("kind") == "ServiceAccount" and isinstance(document.get("metadata"), dict) and document["metadata"].get("name") == expected["name"]]
            if len(service_accounts) != 1 or not isinstance(service_accounts[0]["metadata"].get("annotations"), dict) or service_accounts[0]["metadata"]["annotations"].get("iam.gke.io/gcp-service-account") != annotation:
                raise ValueError("private workload identity Helm mapping is invalid")
        finally:
            temporary.unlink(missing_ok=True)


def _write(path: str | None, report: dict[str, Any], *, immutable: bool = False) -> None:
    if path:
        destination = Path(path)
        if immutable:
            write_immutable_json(destination, report)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")


def execute(
    args: argparse.Namespace,
    environment: dict[str, str] | None = None,
    adapter_factory: Callable[[], ExternalAdapter] | None = None,
    *,
    workspace: Path | None = None,
    private_path_validator: Callable[[Path, str], Path] | None = None,
) -> int:
    environment = os.environ if environment is None else environment
    workspace = Path.cwd() if workspace is None else workspace.resolve()
    destinations = [Path(path) for path in (args.preflight_output, args.output) if path]

    def failed(reason: str) -> int:
        for destination in destinations:
            if not destination.exists():
                write_immutable_json(destination, {"ok": False, "failures": [reason]})
        return 2

    if not args.live_external_preflight:
        try:
            if not all((args.envelope, args.requested_ttl, args.trial_expires_at, args.current_spend_usd is not None, args.output)):
                return 2
            now = datetime.now(UTC)
            trial_hours = (_parse_timestamp(args.trial_expires_at) - now).total_seconds() / 3600
            envelope = yaml.safe_load(Path(args.envelope).read_text(encoding="utf-8"))
            budget = evaluate_budget(envelope, current_spend_usd=args.current_spend_usd, requested_ttl_hours=parse_ttl(args.requested_ttl), trial_remaining_hours=trial_hours)
            _write(args.output, budget)
            return 0 if budget["ok"] else 2
        except (OSError, ValueError, TypeError, yaml.YAMLError):
            return 2

    required = ("operator_inputs", "required_permissions", "preflight_output", "output", "usage_ledger", "envelope", "requested_profile", "requested_ttl")
    raw_live_inputs = (
        "project", "billing_account_env", "budget_notification_target_env", "recovery_sink_env",
        "recovery_sink_attestation", "dns_probes", "required_url_envs", "trial_expires_at",
        "current_spend_usd", "spend_observed_at", "current_spend_vnd", "console_spend_vnd",
        "forecast_vnd", "trial_credit_vnd", "conversion_observed_at", "terraform_backend_config",
    )
    if any(not getattr(args, name) for name in required) or any(getattr(args, name) is not None for name in raw_live_inputs):
        return failed("required_input")
    if any(path.exists() for path in destinations):
        return 2
    try:
        operator = load_operator_inputs(args.operator_inputs, workspace, private_path_validator)
        paths = operator["resolved_paths"]
        ttl = parse_ttl(args.requested_ttl)
        envelope = yaml.safe_load(Path(args.envelope).read_text(encoding="utf-8"))
        budget = evaluate_live_budget(
            envelope,
            current_spend_vnd=float(operator["current_spend_vnd"]),
            console_spend_vnd=float(operator["console_spend_vnd"]),
            forecast_vnd=float(operator["forecast_vnd"]),
            trial_credit_vnd=float(operator["trial_credit_vnd"]),
            conversion_observed_at=operator["conversion_observed_at"],
            spend_observed_at=operator["spend_observed_at"],
            requested_ttl_hours=ttl,
            trial_expires_at=operator["trial_expires_at"],
        )
        append_usage_ledger(Path(args.usage_ledger), {
            key: budget[key] for key in (
                "budget_currency", "conversion_rate_vnd_per_usd", "conversion_rate_source",
                "conversion_observed_at_utc", "spend_observed_at_utc", "official_trial_credit_usd",
                "trial_credit_vnd", "trial_expires_at_utc", "trial_remaining_hours", "requested_ttl_hours",
                "current_spend_vnd", "console_spend_vnd", "forecast_vnd",
                "normalized_current_spend_usd", "normalized_console_spend_usd", "normalized_forecast_usd",
                "normalized_budget_usd", "budget_amount_vnd", "normalized_forecast_ceiling_usd", "forecast_ceiling_vnd",
            )
        } | {"monetary_gate_ok": budget["ok"], "monetary_failures": budget["failures"]})

        attestation = json.loads(paths["recovery_sink_attestation"].read_text(encoding="utf-8"))
        attestation_ok = recovery_attestation_ok(attestation, operator["recovery_sink"])
        backend_preexists, backend_binding = _bootstrap_backend_binding(operator, paths["tf_data_dir"])
        runtime = build_terraform_runtime_contract(
            backend_config=paths["terraform_backend_config"],
            tfvars=paths["terraform_tfvars"],
            tf_data_dir=paths["tf_data_dir"],
            workspace=workspace,
            backend_bucket_preexists=backend_preexists,
            backend_bucket_proof_sha256=backend_binding,
            path_validator=private_path_validator,
        )
        permissions = json.loads(Path(args.required_permissions).read_text(encoding="utf-8"))
        local_failures = list(budget["failures"])
        if not attestation_ok:
            local_failures.append("recovery_sink_attestation")
        if local_failures:
            report = {"ok": False, "failures": sorted(set(local_failures)), "budget_ok": budget["ok"], "external_gates_skipped": True}
        else:
            private_environment = dict(environment)
            private_environment.update({
                "CLOUDSDK_CONFIG": str(paths["gcloud_config_dir"]),
                "GOOGLE_APPLICATION_CREDENTIALS": str(paths["application_default_credentials"]),
            })
            adapter = adapter_factory() if adapter_factory is not None else GcloudRestExternalAdapter(
                project_id=operator["project_id"], billing_account=operator["billing_account_id"],
                token_supplier=lambda: _run_gcloud_private(["gcloud", "auth", "print-access-token"], private_environment),
            )
            report = run_external_preflight(
                adapter,
                required_permissions=permissions,
                notification_target=operator["budget_notification_target"],
                recovery_sink=operator["recovery_sink"],
                dns_probes=operator["dns_probes"],
                required_urls=[operator["billing_console_url"]],
            )
            report["budget_ok"] = budget["ok"]
            report["ok"] = report["ok"] and budget["ok"]
            report["failures"] = sorted(set(report["failures"] + budget["failures"]))
        report["operator_input_bundle_sha256"] = _hash(Path(args.operator_inputs).read_text(encoding="utf-8"))
        report["backend_bucket_proof_sha256"] = runtime["backend_bucket_proof_sha256"]
        report["private_tf_data_dir"] = True
        write_immutable_json(Path(args.preflight_output), report)
        write_immutable_json(Path(args.output), budget)
        if report["ok"]:
            write_terraform_runtime_contract(
                backend_config=paths["terraform_backend_config"], tfvars=paths["terraform_tfvars"], tf_data_dir=paths["tf_data_dir"],
                workspace=workspace, backend_bucket_proof_sha256=runtime["backend_bucket_proof_sha256"], path_validator=private_path_validator,
            )
            revision_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace, check=False, capture_output=True, text=True, encoding="utf-8")
            revision = revision_result.stdout.strip() if revision_result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", revision_result.stdout.strip()) else "0" * 40
            write_immutable_json(Path(paths["tf_data_dir"]) / "topic22-runtime-binding.json", {"forecast_sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(), "revision": revision})
        return 0 if report["ok"] else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError, subprocess.CalledProcessError, FileExistsError):
        return failed("preflight_error")


def main() -> int:
    try:
        args = parse_args()
        helper = dispatch_private_helper(args, Path.cwd())
        return execute(args) if helper is None else helper
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, yaml.YAMLError, subprocess.SubprocessError):
        print("TOPIC22_BUDGET_ERROR", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
