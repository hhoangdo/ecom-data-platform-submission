"""Shared private-input primitives for the standalone Topic 22 CLIs."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import stat
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


_OPERATOR_FIELDS = {
    "schema_version", "project_id", "billing_account_id", "budget_notification_target",
    "recovery_sink", "billing_console_url", "dns_probes", "trial_expires_at",
    "spend_observed_at", "conversion_observed_at", "current_spend_vnd",
    "console_spend_vnd", "forecast_vnd", "trial_credit_vnd",
    "backend_bucket_preexists", "backend_bucket_proof_sha256", "paths",
    "billing_required_markers", "billing_pii_selectors",
}
_OPERATOR_PATHS = {
    "recovery_sink_attestation": "file",
    "terraform_tfvars": "file",
    "terraform_backend_config": "file",
    "browser_storage_state": "file",
    "gcloud_config_dir": "dir",
    "application_default_credentials": "file",
    "tf_data_dir": "dir",
}
_PERSONAL_STUDY_OPERATOR_FIELDS = (_OPERATOR_FIELDS - {"recovery_sink"}) | {"project_purpose"}
_PERSONAL_STUDY_OPERATOR_PATHS = {
    name: path_type for name, path_type in _OPERATOR_PATHS.items()
    if name != "recovery_sink_attestation"
}
_MONETARY_FIELDS = {
    "schema_version", "billing_account_id", "trial_expires_at", "spend_observed_at",
    "conversion_observed_at", "current_spend_vnd", "console_spend_vnd", "forecast_vnd",
    "trial_credit_vnd", "paths",
}
_MONETARY_PATHS = {
    "gcloud_config_dir": "dir",
    "application_default_credentials": "file",
}
_BOOTSTRAP_FIELDS = {
    "schema_version", "project_id", "billing_account_id", "trial_expires_at",
    "spend_observed_at", "conversion_observed_at", "current_spend_vnd",
    "console_spend_vnd", "forecast_vnd", "trial_credit_vnd", "requested_ttl_hours",
    "backend_bucket_preexists", "backend_bucket_proof_sha256", "paths",
}
_BOOTSTRAP_PATHS = {
    "gcloud_config_dir": "dir",
    "application_default_credentials": "file",
    "tf_data_dir": "dir",
    "terraform_backend_config": "file",
    "bootstrap_authorization": "file",
}
_BILLING_SELECTOR = re.compile(r"\[(aria-label|data-field|data-testid)(\*=|=)'([A-Za-z][A-Za-z0-9 -]{0,47})'\]")
_BILLING_MARKER_VALUES = {"billing", "billing overview", "current spend", "current-spend", "budget", "cost overview"}
_BILLING_PII_VALUES = {"billing-account-id", "billing-account-name", "project-id", "email", "user-email"}


class PrivateBundleError(ValueError):
    """The private bundle or one of its local contents is unreadable or malformed."""


class PrivatePathPolicyError(ValueError):
    """A private path violates Topic 22 containment, type, symlink, or ignore policy."""


class PrivateAccessPolicyError(ValueError):
    """A private path's owner, ACL, or mode is too broad for Topic 22."""


def rest_request(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object] | None,
) -> dict[str, Any]:
    """Decode one JSON object while keeping authentication material in memory."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:  # nosec B310 -- callers use fixed Google endpoints
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("REST response must be an object")
    return result


def resource_manager_project_number(payload: object, expected_project_id: str) -> str:
    """Return the numeric segment of the canonical Resource Manager v3 project name."""
    if not isinstance(payload, dict):
        raise ValueError("Resource Manager project response is invalid")
    name = payload.get("name")
    match = re.fullmatch(r"projects/([1-9][0-9]*)", name) if isinstance(name, str) else None
    returned_project_id = payload.get("projectId")
    if not match or (returned_project_id is not None and returned_project_id != expected_project_id):
        raise ValueError("Resource Manager project response is invalid")
    return match.group(1)


def validate_billing_selectors(markers: object, pii: object) -> tuple[list[str], list[str]]:
    """Allow only bounded field-oriented CSS selectors; never arbitrary browser code."""
    def validate(values: object, allowed: set[str]) -> list[str]:
        if not isinstance(values, list) or not 1 <= len(values) <= 6 or len(values) != len(set(values)):
            raise ValueError("billing selector list is invalid")
        checked: list[str] = []
        for value in values:
            if not isinstance(value, str) or not 8 <= len(value) <= 96:
                raise ValueError("billing selector is invalid")
            match = _BILLING_SELECTOR.fullmatch(value)
            if not match or match.group(3).lower() not in allowed:
                raise ValueError("billing selector is invalid")
            checked.append(value)
        return checked

    return validate(markers, _BILLING_MARKER_VALUES), validate(pii, _BILLING_PII_VALUES)


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


def _private_topic22_path(value: str | Path, workspace: Path, *, directory: bool = False) -> Path:
    candidate = Path(value)
    absolute = candidate if candidate.is_absolute() else (workspace / candidate)
    root = (workspace / "tmp" / "edai2-gcp").resolve()
    try:
        relative = absolute.relative_to(workspace)
    except ValueError as error:
        raise PrivatePathPolicyError("private Topic 22 path is invalid") from error
    cursor = workspace
    for component in relative.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise PrivatePathPolicyError("private Topic 22 path is invalid")
    resolved = absolute.resolve()
    if (resolved != root and root not in resolved.parents) or (resolved == root and not directory):
        raise PrivatePathPolicyError("private Topic 22 path is invalid")
    if not resolved.exists():
        raise PrivateBundleError("private Topic 22 path is missing")
    expected_type = resolved.is_dir() if directory else resolved.is_file()
    if not expected_type:
        raise PrivatePathPolicyError("private Topic 22 path type is invalid")
    return resolved


def windows_private_acl_ok(acl: str, current_user: str) -> bool:
    """Accept only an icacls listing whose effective grants remain private to its current owner."""
    if not isinstance(acl, str) or not isinstance(current_user, str) or not current_user:
        return False
    owner_has_full_control = False
    trusted = {"nt authority\\system", "builtin\\administrators"}
    broad = {"everyone", "builtin\\users", "authenticated users", "guests", "builtin\\guests"}
    for line in acl.splitlines():
        rights_match = re.search(r":((?:\([^)\r\n]+\))+)", line)
        if not rights_match:
            continue
        rights = rights_match.group(1)
        grants_access = bool(re.search(r"\((?:F|M|RX|R|W|X)\)", rights, re.IGNORECASE))
        if not grants_access:
            continue
        normalized = line.casefold()
        if any(re.search(rf"(?<![a-z0-9]){re.escape(name)}(?=[:\s])", normalized) for name in broad):
            return False
        if f"{current_user.casefold()}:" in normalized:
            if not re.search(r"\(F\)", rights, re.IGNORECASE):
                return False
            owner_has_full_control = True
            continue
        if any(f"{name}:" in normalized for name in trusted):
            if not re.search(r"\(F\)", rights, re.IGNORECASE):
                return False
            continue
        # Every access ACE must be current user or a narrowly trusted Windows administrator.
        if re.search(r"(?:^|\s)[^:\r\n]+:", line):
            return False
    return owner_has_full_control


def windows_owner_for_path(
    path: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    """Read a Windows ACL owner without treating the private path as PowerShell source text."""
    environment = dict(os.environ)
    environment["TOPIC22_OWNER_PATH"] = str(path)
    try:
        result = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "try { (Get-Acl -LiteralPath $env:TOPIC22_OWNER_PATH).Owner } catch { (Get-Item -LiteralPath $env:TOPIC22_OWNER_PATH).GetAccessControl().Owner }"],
            env=environment, capture_output=True, text=True, encoding="utf-8", check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise PrivateAccessPolicyError("private Topic 22 path owner is unavailable") from error
    owner = result.stdout.strip()
    if not owner:
        raise PrivateAccessPolicyError("private Topic 22 path owner is invalid")
    return owner


def private_unix_tree_modes_ok(
    path: Path,
    root: Path,
    *,
    mode_reader: Callable[[Path], int] = lambda candidate: stat.S_IMODE(candidate.stat().st_mode),
) -> bool:
    """Require a 0700 private tree and a 0600 leaf file through the designated root."""
    leaf, root = path.resolve(), root.resolve()
    if root != leaf and root not in leaf.parents:
        return False
    components = [leaf, *leaf.parents]
    for component in components:
        mode = mode_reader(component)
        expected = 0o600 if component == leaf and component.is_file() else 0o700
        if mode != expected:
            return False
        if component == root:
            return True
    return False


def validate_private_operator_path(path: Path, kind: str, workspace: Path) -> Path:
    """Require a real ignored path whose ACL/mode does not grant broad access."""
    resolved = _private_topic22_path(path, workspace, directory=kind.endswith("_dir"))
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(resolved)],
            cwd=workspace,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise PrivatePathPolicyError(
            "private Topic 22 path ignore check is unavailable"
        ) from error
    if ignored.returncode != 0:
        raise PrivatePathPolicyError("private Topic 22 path is not ignored")
    if os.name == "nt":
        try:
            current_user = subprocess.run(["whoami"], capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            raise PrivateAccessPolicyError("private Topic 22 path owner is unavailable") from error
        if not current_user:
            raise PrivateAccessPolicyError("private Topic 22 path owner is invalid")
        components = [resolved, *resolved.parents]
        root = (workspace / "tmp" / "edai2-gcp").resolve()
        for component in components:
            try:
                owner = windows_owner_for_path(component)
                acl = subprocess.run(["icacls", str(component)], capture_output=True, text=True, encoding="utf-8", check=True).stdout
            except PrivateAccessPolicyError:
                raise
            except (OSError, subprocess.SubprocessError) as error:
                raise PrivateAccessPolicyError("private Topic 22 path access is unavailable") from error
            if owner.casefold() != current_user.casefold():
                raise PrivateAccessPolicyError("private Topic 22 path owner is invalid")
            if not windows_private_acl_ok(acl, current_user):
                raise PrivateAccessPolicyError("private Topic 22 path ACL is too broad")
            if component == root:
                break
    else:
        try:
            modes_ok = private_unix_tree_modes_ok(resolved, (workspace / "tmp" / "edai2-gcp"))
        except (OSError, ValueError) as error:
            raise PrivateAccessPolicyError("private Topic 22 path mode is unavailable") from error
        if not modes_ok:
            raise PrivateAccessPolicyError("private Topic 22 path mode is too broad")
    return resolved


def backend_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r'(bucket|prefix)\s*=\s*"([A-Za-z0-9][A-Za-z0-9._/-]*)"', line)
        if not match or match.group(1) in values:
            raise ValueError("backend config is invalid")
        values[match.group(1)] = match.group(2)
    bucket, prefix = values.get("bucket", ""), values.get("prefix", "")
    if set(values) != {"bucket", "prefix"} or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]", bucket) or prefix.startswith("/") or prefix.endswith("/") or ".." in prefix:
        raise ValueError("backend config is invalid")
    return values


def _load_operator_inputs(
    value: str | Path,
    workspace: Path,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, Any]:
    """Load the sole live private-input interface without emitting its raw values."""
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))

    def validate(candidate: Path, kind: str, *, directory: bool = False) -> Path:
        resolved = _private_topic22_path(candidate, workspace, directory=directory)
        checked = Path(validator(resolved, f"{kind}_dir" if directory else kind)).resolve()
        if checked != resolved:
            raise ValueError("private path validator changed the target")
        return checked

    bundle_path = validate(Path(value), "operator_inputs")
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    personal_study = isinstance(payload, dict) and payload.get("project_purpose") == "personal-study"
    operator_fields = _PERSONAL_STUDY_OPERATOR_FIELDS if personal_study else _OPERATOR_FIELDS
    operator_paths = _PERSONAL_STUDY_OPERATOR_PATHS if personal_study else _OPERATOR_PATHS
    if not isinstance(payload, dict) or set(payload) != operator_fields or payload.get("schema_version") != 1:
        raise ValueError("operator input bundle schema is invalid")
    paths = payload.get("paths")
    optional_paths = {"bootstrap_authorization": "file"}
    if not isinstance(paths, dict) or set(paths) not in (set(operator_paths), set(operator_paths) | set(optional_paths)):
        raise ValueError("operator input path schema is invalid")
    resolved_paths: dict[str, Path] = {}
    for name, path_type in {**operator_paths, **({"bootstrap_authorization": "file"} if "bootstrap_authorization" in paths else {})}.items():
        relative = paths.get(name)
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("operator input path is invalid")
        resolved_paths[name] = validate(bundle_path.parent / relative, name, directory=path_type == "dir")

    strings = ("project_id", "billing_account_id", "trial_expires_at", "spend_observed_at", "conversion_observed_at")
    if not personal_study:
        strings += ("recovery_sink",)
    if any(not isinstance(payload.get(name), str) or not payload[name] for name in strings):
        raise ValueError("operator input value is invalid")
    notification = payload.get("budget_notification_target")
    if not isinstance(notification, str) or not _is_notification_target(notification) or notification.split("/")[1] != payload["project_id"]:
        raise ValueError("operator notification target is invalid")
    if not isinstance(payload.get("billing_console_url"), str) or not payload["billing_console_url"].startswith("https://console.cloud.google.com/billing") or not _public_https_url(payload["billing_console_url"]):
        raise ValueError("operator billing URL is invalid")
    probes = payload.get("dns_probes")
    if not isinstance(probes, list) or not probes or len(probes) != len(set(probes)) or not all(_public_hostname(host) for host in probes):
        raise ValueError("operator DNS probes are invalid")
    markers, pii = validate_billing_selectors(payload.get("billing_required_markers"), payload.get("billing_pii_selectors"))
    payload["billing_required_markers"], payload["billing_pii_selectors"] = markers, pii
    money = ("current_spend_vnd", "console_spend_vnd", "forecast_vnd", "trial_credit_vnd")
    if any(isinstance(payload.get(name), bool) or not isinstance(payload.get(name), (int, float)) for name in money):
        raise ValueError("operator monetary inputs are invalid")
    if not isinstance(payload.get("backend_bucket_preexists"), bool) or (payload["backend_bucket_preexists"] is True and not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("backend_bucket_proof_sha256", "")))) or (payload["backend_bucket_preexists"] is False and payload.get("backend_bucket_proof_sha256") != ""):
        raise ValueError("operator backend bootstrap proof is invalid")
    backend_values(resolved_paths["terraform_backend_config"])
    for json_name in ("browser_storage_state", "application_default_credentials", *(("bootstrap_authorization",) if "bootstrap_authorization" in resolved_paths else ())):
        decoded = json.loads(resolved_paths[json_name].read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(f"operator {json_name} is invalid")
        decoded = None
    return {**payload, "resolved_paths": resolved_paths}


def load_operator_inputs(
    value: str | Path,
    workspace: Path,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, Any]:
    """Load the full operator bundle with typed errors for the local-only pre-cloud gate."""
    try:
        return _load_operator_inputs(value, workspace, path_validator)
    except (PrivatePathPolicyError, PrivateAccessPolicyError):
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise PrivateBundleError("operator input bundle is invalid") from error


def load_monetary_inputs(
    value: str | Path,
    workspace: Path,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, Any]:
    """Load the separate minimal private bundle for the read-only bootstrap monetary phase."""
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))

    def validate(candidate: Path, kind: str, *, directory: bool = False) -> Path:
        resolved = _private_topic22_path(candidate, workspace, directory=directory)
        checked = Path(validator(resolved, f"{kind}_dir" if directory else kind)).resolve()
        if checked != resolved:
            raise ValueError("private path validator changed the target")
        return checked

    bundle_path = validate(Path(value), "monetary_inputs")
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != _MONETARY_FIELDS or payload.get("schema_version") != 1:
        raise ValueError("monetary input bundle schema is invalid")
    paths = payload.get("paths")
    if not isinstance(paths, dict) or set(paths) != set(_MONETARY_PATHS):
        raise ValueError("monetary input path schema is invalid")
    resolved_paths: dict[str, Path] = {}
    for name, path_type in _MONETARY_PATHS.items():
        relative = paths.get(name)
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("monetary input path is invalid")
        resolved_paths[name] = validate(bundle_path.parent / relative, name, directory=path_type == "dir")
    strings = ("billing_account_id", "trial_expires_at", "spend_observed_at", "conversion_observed_at")
    if any(not isinstance(payload.get(name), str) or not payload[name] for name in strings):
        raise ValueError("monetary input value is invalid")
    money = ("current_spend_vnd", "console_spend_vnd", "forecast_vnd", "trial_credit_vnd")
    if any(isinstance(payload.get(name), bool) or not isinstance(payload.get(name), (int, float)) for name in money):
        raise ValueError("monetary inputs are invalid")
    decoded = json.loads(resolved_paths["application_default_credentials"].read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("monetary application_default_credentials is invalid")
    return {**payload, "resolved_paths": resolved_paths}


def load_bootstrap_inputs(
    value: str | Path,
    workspace: Path,
    path_validator: Callable[[Path, str], Path] | None = None,
) -> dict[str, Any]:
    """Load the private fresh/reuse bootstrap contract before notification creation is possible."""
    validator = path_validator or (lambda candidate, kind: validate_private_operator_path(candidate, kind, workspace))

    def validate(candidate: Path, kind: str, *, directory: bool = False) -> Path:
        resolved = _private_topic22_path(candidate, workspace, directory=directory)
        checked = Path(validator(resolved, f"{kind}_dir" if directory else kind)).resolve()
        if checked != resolved:
            raise ValueError("private path validator changed the target")
        return checked

    bundle_path = validate(Path(value), "bootstrap_inputs")
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != _BOOTSTRAP_FIELDS or payload.get("schema_version") != 1:
        raise ValueError("bootstrap input bundle schema is invalid")
    paths = payload.get("paths")
    if not isinstance(paths, dict) or set(paths) != set(_BOOTSTRAP_PATHS):
        raise ValueError("bootstrap input path schema is invalid")
    resolved_paths: dict[str, Path] = {}
    for name, path_type in _BOOTSTRAP_PATHS.items():
        relative = paths.get(name)
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("bootstrap input path is invalid")
        resolved_paths[name] = validate(bundle_path.parent / relative, name, directory=path_type == "dir")
    strings = ("project_id", "billing_account_id", "trial_expires_at", "spend_observed_at", "conversion_observed_at")
    if any(not isinstance(payload.get(name), str) or not payload[name] for name in strings):
        raise ValueError("bootstrap input value is invalid")
    money = ("current_spend_vnd", "console_spend_vnd", "forecast_vnd", "trial_credit_vnd", "requested_ttl_hours")
    if any(isinstance(payload.get(name), bool) or not isinstance(payload.get(name), (int, float)) for name in money):
        raise ValueError("bootstrap monetary inputs are invalid")
    if not isinstance(payload.get("backend_bucket_preexists"), bool) or (payload["backend_bucket_preexists"] is True and not re.fullmatch(r"[0-9a-f]{64}", str(payload.get("backend_bucket_proof_sha256", "")))) or (payload["backend_bucket_preexists"] is False and payload.get("backend_bucket_proof_sha256") != ""):
        raise ValueError("bootstrap backend proof is invalid")
    backend_values(resolved_paths["terraform_backend_config"])
    for json_name in ("application_default_credentials", "bootstrap_authorization"):
        decoded = json.loads(resolved_paths[json_name].read_text(encoding="utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError(f"bootstrap {json_name} is invalid")
    return {**payload, "resolved_paths": resolved_paths}
