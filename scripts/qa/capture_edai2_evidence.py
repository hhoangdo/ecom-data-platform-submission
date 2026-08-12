"""Fail-closed local screenshot contracts; no browser, Kubernetes, or tunnel is started here."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote, urlencode

import yaml
from PIL import Image, ImageDraw

from vina_bim_shop.topic22_private import (
    load_operator_inputs as load_topic22_operator_inputs,
    resource_manager_project_number,
    rest_request as topic22_rest_request,
    validate_billing_selectors as validate_topic22_billing_selectors,
)


MANIFEST_FIELDS = ("path", "width", "height", "captured_at_utc", "url_or_source", "commit_or_revision", "visible_selectors", "linked_machine_evidence", "approved_plan_sha256", "sha256", "proves", "does_not_prove")
PRIVATE_ENDPOINT_KEYS = ("agentregistry_ui", "grafana_ui", "airflow_web", "datahub_frontend", "vault_status")
PRIVATE_ENDPOINT_FIELDS = {"namespace", "service_name", "service_uid", "service_port", "target_port", "selector_sha256", "ready_endpoint_uids"}
STABLE_LABELS = ("service", "route", "agent", "tool", "model_version", "agent_config", "index_version", "status", "safety_action", "log_scope")
ALERT_FIXTURES = {
    "EDAI2ApiToolFailureHigh": {"pending": {"failure_ratio": 0.06}, "firing": {"failure_ratio": 0.06, "for_seconds": 300}},
    "EDAI2RetrievalP95High": {"pending": {"p95_seconds": 0.76}, "firing": {"p95_seconds": 0.76, "for_seconds": 300}},
    "EDAI2ActiveIndexStale": {"pending": {"age_seconds": 86401}, "firing": {"age_seconds": 86401, "for_seconds": 300}},
    "EDAI2MemoryHigh": {"pending": {"usage_ratio": 0.91}, "firing": {"usage_ratio": 0.91, "for_seconds": 300}},
    "EDAI2DiskHigh": {"pending": {"usage_ratio": 0.81}, "firing": {"usage_ratio": 0.81, "for_seconds": 300}},
}
TRACE_FIXTURE = [
    {"span": "nginx/chat", "parent": None}, {"span": "facade", "parent": "nginx/chat"}, {"span": "agentgateway", "parent": "facade"},
    {"span": "coordinator", "parent": "agentgateway"}, {"span": "llm-d", "parent": "agentgateway"}, {"span": "specialist", "parent": "agentgateway"},
    {"span": "specialist-agentgateway", "parent": "specialist"}, {"span": "matching MCP", "parent": "specialist-agentgateway"},
    {"span": "retrieval/drift API", "parent": "matching MCP"}, {"span": "Feast/PostgreSQL", "parent": "retrieval/drift API"},
]
REQUIRED_VIEWS = {
    "airflow_rag_graph.png": ["Airflow title", "DAG ID rag_index_pipeline", "Graph view", "successful run state"],
    "datahub_rag_lineage.png": ["DataHub title", "RAG dataset identity", "Lineage view", "upstream and downstream nodes"],
    "kagent_retrieval_chat.png": ["kagent title", "resource support", "logical identity retrieval", "grounded answer and citation"],
    "kagent_drift_chat.png": ["kagent title", "agent drift", "population PSI/status", "feature name f_customer_order_frequency_7d"],
    "kagent_coordinator_chat.png": ["kagent title", "agent coordinator", "selected specialist route", "recorded tool call"],
    "agentregistry_agents.png": ["Agent Registry title", "retrieval", "drift", "coordinator"],
    "keda_scale.png": ["KEDA/ScaledObject context", "target name", "Ready/Active conditions", "observed replica transition"],
    "grafana_http.png": ["Grafana title", "dashboard EDAI2 HTTP", "RPS/count/failure panels", "time range"],
    "grafana_compute.png": ["Grafana title", "dashboard EDAI2 Compute", "CPU/RAM/disk/network panels", "time range"],
    "grafana_llm.png": ["Grafana title", "dashboard EDAI2 LLM", "token/RTT/TTFT/safety panels", "time range"],
    "grafana_agents.png": ["Grafana title", "dashboard EDAI2 Agents", "agent/tool call and failure panels"],
    "grafana_ab.png": ["Grafana title", "dashboard EDAI2 A-B", "both arms", "sample counts", "quality/latency panels"],
    "loki_app_logs.png": ["Loki/Grafana Explore context", "log_scope=application", "service filter", "redacted structured log rows"],
    "tempo_trace.png": ["Tempo trace context", "trace ID", "root chat span", "gateway/coordinator/specialist/MCP dependency chain"],
    "langfuse_trace.png": ["Langfuse title", "trace/session identity", "model version", "token/latency fields", "redacted input/output state"],
    "vault_status.png": ["Vault title", "initialized state", "unsealed/healthy state", "authentication context without secret values"],
    "nginx_tls.png": ["HTTPS origin", "valid certificate/security indicator", "ingress host", "application title"],
    "chat_auth_rate_limit.png": ["Chat route context", "explicit authentication rejection 401", "rate-limit response 429 evidence"],
    "coverage_and_api_fixtures.png": ["Coverage report title", "total at least 91%", "API contract/fixture suite identity", "passing state"],
    "ep_bva.png": ["EP/BVA report identity", "boundary case labels", "passing totals"],
    "mutation.png": ["Mutation report identity", "classified status counts", "strict score greater than 0.80"],
    "properties_crosshair.png": ["Hypothesis and CrossHair report identities", "bounded run details", "no counterexample/passing state"],
    "gcp_billing_spend.png": ["Google Cloud Billing", "Budget and spend context", "fresh observation time", "redacted project alias"],
    "terraform_apply.png": ["Terraform apply evidence title", "successful terminal state", "exact commit/revision", "linked machine record"],
    "design_patterns.png": ["Diagram title EDAI2 Design Patterns", "pattern names", "component relationships", "readable legend"],
    "whole_course_diagram.png": ["Whole-course architecture title", "Section 03/EDAI2 boundaries", "data/control/evidence flows", "readable legend"],
    "locust_report.png": ["Locust report title", "host/scenario", "request/failure totals", "p95 and run duration"],
    "jenkins_rag_index.png": ["Jenkins job edai2-rag-index", "build number", "SUCCESS", "common full commit SHA"],
    "jenkins_retrieval_agent.png": ["Jenkins job edai2-retrieval-agent", "build number", "SUCCESS", "common full commit SHA"],
    "jenkins_drift_agent.png": ["Jenkins job edai2-drift-agent", "build number", "SUCCESS", "common full commit SHA"],
    "jenkins_coordinator.png": ["Jenkins job edai2-coordinator", "build number", "SUCCESS", "common full commit SHA"],
    "jenkins_feast_offline.png": ["Jenkins job edai2-feast-offline-writer", "build number", "SUCCESS", "common full commit SHA"],
    "jenkins_feast_online.png": ["Jenkins job edai2-feast-online-writer", "build number", "SUCCESS", "common full commit SHA"],
}
LOCKED_FILENAMES = tuple(REQUIRED_VIEWS)
_PNG = b"\x89PNG\r\n\x1a\n"
_SECRET = re.compile(r"(?i)(password|token|secret|api[_-]?key|customer[_-]?id|bearer|authorization|[\w.+-]+@[\w.-]+\.[a-z]{2,})")
_SECRET_KEY = re.compile(r"(?i)(password|token|secret|api[_-]?key|customer[_-]?id|bearer|authorization)")
_SECRET_VALUE = re.compile(r"(?i)(password|token|api[_-]?key|customer[_-]?id|bearer|authorization|^secret$)")
_EMAIL_VALUE = re.compile(r"(?i)[\w.+-]+@[\w.-]+\.[a-z]{2,}")
_APPROVED_SERVICE_ACCOUNT_EMAIL = r"[a-z0-9-]+@[a-z0-9-]+\.iam\.gserviceaccount\.com"
_APPROVED_TERRAFORM_PRINCIPAL = re.compile(rf"(?:serviceAccount:)?(?:[a-z0-9-]+\.svc\.id\.goog\[edai2:edai2-[a-z-]+\]|{_APPROVED_SERVICE_ACCOUNT_EMAIL}|service-\d+@gs-project-accounts\.iam\.gserviceaccount\.com)", re.IGNORECASE)
_BAD_PAGE = re.compile(r"(?i)(loading|spinner|login|sign[ -]?in|error|generic|terminal)")
_TERRAFORM_ALLOWED_TYPES = {
    "google_artifact_registry_repository", "google_billing_budget", "google_container_cluster",
    "google_container_node_pool", "google_kms_crypto_key", "google_kms_crypto_key_iam_member",
    "google_kms_key_ring", "google_service_account", "google_service_account_iam_member",
    "google_storage_bucket", "google_storage_bucket_iam_member",
    "google_project_service",
}
_TERRAFORM_ALLOWED_DATA_TYPES = {"google_project", "google_storage_project_service_account"}
_TERRAFORM_GROUPS = {
    "gke": {"google_container_cluster"},
    "node-pools": {"google_container_node_pool"},
    "artifact-registry": {"google_artifact_registry_repository"},
    "gcs": {"google_storage_bucket"},
    "kms": {"google_kms_key_ring", "google_kms_crypto_key", "google_kms_crypto_key_iam_member"},
    "iam": {"google_service_account", "google_service_account_iam_member", "google_storage_bucket_iam_member"},
    "budget": {"google_billing_budget"},
    "project-services": {"google_project_service"},
}
_FORBIDDEN_RESOURCE_GROUPS = {
    "vm": {"google_compute_instance"}, "cloud-build": {"google_cloudbuild_trigger"},
    "load-balancer": {"google_compute_forwarding_rule", "google_compute_global_forwarding_rule"},
}


def validate_billing_selectors(markers: object, pii: object) -> tuple[list[str], list[str]]:
    """Delegate both standalone CLIs to the same selector policy."""
    return validate_topic22_billing_selectors(markers, pii)


def _canonical_inventory(inventory: dict[str, object]) -> bytes:
    return json.dumps(inventory, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def inventory_signature(inventory: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_inventory(inventory)).hexdigest()


def _has_secret(value: object) -> bool:
    if isinstance(value, dict):
        return any(_SECRET.search(str(key)) or _has_secret(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_secret(item) for item in value)
    return isinstance(value, str) and bool(_SECRET.search(value))


_TERRAFORM_PRINCIPAL_FIELDS = {
    "google_storage_bucket_iam_member": {"member"},
    "google_kms_crypto_key_iam_member": {"member"},
    "google_service_account_iam_member": {"member", "service_account_id"},
    "google_service_account": {"email"},
    "google_storage_project_service_account": {"email_address"},
}


def _approved_terraform_principal(resource_type: str | None, field: str, value: object) -> bool:
    if not isinstance(value, str) or resource_type not in _TERRAFORM_PRINCIPAL_FIELDS or field not in _TERRAFORM_PRINCIPAL_FIELDS[resource_type]:
        return False
    if resource_type == "google_service_account_iam_member" and field == "service_account_id":
        return bool(re.fullmatch(rf"projects/[a-z0-9-]+/serviceAccounts/{_APPROVED_SERVICE_ACCOUNT_EMAIL}", value, re.IGNORECASE))
    return bool(_APPROVED_TERRAFORM_PRINCIPAL.fullmatch(value))


def _has_unsafe_terraform_secret(value: object, *, resource_type: str | None = None) -> bool:
    """Reject secrets everywhere, permitting an email only in an IAM/WI principal leaf held in memory."""
    if isinstance(value, dict):
        nested_type = value.get("type") if isinstance(value.get("type"), str) else resource_type
        for key, item in value.items():
            if _SECRET_KEY.search(str(key)):
                return True
            if nested_type in _TERRAFORM_PRINCIPAL_FIELDS and key in _TERRAFORM_PRINCIPAL_FIELDS[nested_type]:
                if _approved_terraform_principal(nested_type, key, item):
                    continue
                if isinstance(item, dict) and set(item) == {"constant_value"} and _approved_terraform_principal(nested_type, key, item["constant_value"]):
                    continue
                return True
            if _has_unsafe_terraform_secret(item, resource_type=nested_type):
                return True
        return False
    if isinstance(value, list):
        return any(_has_unsafe_terraform_secret(item, resource_type=resource_type) for item in value)
    if not isinstance(value, str):
        return False
    return bool(_SECRET_VALUE.search(value) or _EMAIL_VALUE.search(value))


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paged_aggregated_forwarding_rules(
    requester: Callable[[str, str, dict[str, object] | None], dict[str, object]], url: str,
) -> list[dict[str, object]]:
    """Collect every Compute aggregated-forwarding-rules page before declaring no public rule."""
    token: str | None = None
    seen: set[str] = set()
    rules: list[dict[str, object]] = []
    for _ in range(20):
        suffix = "" if token is None else ("&" if "?" in url else "?") + urlencode({"pageToken": token})
        payload = requester("GET", url + suffix, None)
        items = payload.get("items")
        if not isinstance(items, dict):
            raise ValueError("paged forwarding-rule REST response is invalid")
        for scoped in items.values():
            values = scoped.get("forwardingRules", []) if isinstance(scoped, dict) else None
            if not isinstance(values, list) or any(not isinstance(rule, dict) for rule in values):
                raise ValueError("paged forwarding-rule REST response is invalid")
            rules.extend(values)
        next_token = payload.get("nextPageToken")
        if next_token is None:
            return rules
        if not isinstance(next_token, str) or not next_token or next_token in seen:
            raise ValueError("paged forwarding-rule REST response is invalid")
        seen.add(next_token)
        token = next_token
    raise ValueError("paged forwarding-rule REST response is invalid")


def paged_aggregated_instance_group_managers(
    requester: Callable[[str, str, dict[str, object] | None], dict[str, object]], url: str,
) -> list[dict[str, object]]:
    """Collect every Compute MIG page before treating GKE pool capacity as zero."""
    token: str | None = None
    seen: set[str] = set()
    managers: list[dict[str, object]] = []
    for _ in range(20):
        suffix = "" if token is None else ("&" if "?" in url else "?") + urlencode({"pageToken": token})
        payload = requester("GET", url + suffix, None)
        items = payload.get("items")
        if not isinstance(items, dict):
            raise ValueError("paged instance-group-manager REST response is invalid")
        for scoped in items.values():
            values = scoped.get("instanceGroupManagers", []) if isinstance(scoped, dict) else None
            if not isinstance(values, list) or any(not isinstance(manager, dict) for manager in values):
                raise ValueError("paged instance-group-manager REST response is invalid")
            managers.extend(values)
        next_token = payload.get("nextPageToken")
        if next_token is None:
            return managers
        if not isinstance(next_token, str) or not next_token or next_token in seen:
            raise ValueError("paged instance-group-manager REST response is invalid")
        seen.add(next_token)
        token = next_token
    raise ValueError("paged instance-group-manager REST response is invalid")


def _one(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise ValueError(f"Terraform {label} invariant is invalid")
    return value[0]


def _principal_fingerprint(value: object) -> str:
    if not isinstance(value, str) or not value or "@" not in value:
        raise ValueError("Terraform principal identity is invalid")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _service_account_fingerprint(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Terraform principal identity is invalid")
    match = re.fullmatch(r"projects/[a-z0-9-]+/serviceAccounts/(.+)", value, re.IGNORECASE)
    return _principal_fingerprint(match.group(1) if match else value)


def _terraform_invariants(resources: list[dict[str, object]], types: list[str], variables: object) -> tuple[dict[str, object], list[str]]:
    def by_type(kind: str) -> list[dict[str, object]]:
        return [item for item in resources if item["type"] == kind]

    services = by_type("google_project_service")
    required_services = {
        "artifactregistry.googleapis.com", "billingbudgets.googleapis.com", "cloudbilling.googleapis.com",
        "cloudkms.googleapis.com", "cloudresourcemanager.googleapis.com", "compute.googleapis.com",
        "container.googleapis.com", "iam.googleapis.com", "monitoring.googleapis.com",
        "serviceusage.googleapis.com", "storage.googleapis.com",
    }
    service_names: set[str] = set()
    for item in services:
        after = item["after"]
        if not isinstance(after, dict) or not isinstance(after.get("service"), str) or after.get("disable_on_destroy") is not False or not isinstance(after.get("project"), str) or not after.get("project"):
            raise ValueError("Terraform project service invariant is invalid")
        service_names.add(after["service"])
    if service_names != required_services or len(services) != len(required_services):
        raise ValueError("Terraform project service invariant is invalid")

    cluster_items = by_type("google_container_cluster")
    if len(cluster_items) != 1:
        raise ValueError("Terraform cluster invariant is invalid")
    cluster = cluster_items[0]["after"]
    if not isinstance(cluster, dict) or cluster.get("name") != "edai2" or cluster.get("location") != "us-central1-a" or not _one(cluster.get("workload_identity_config"), "workload identity").get("workload_pool"):
        raise ValueError("Terraform cluster invariant is invalid")

    pool_facts: list[dict[str, object]] = []
    expected_pools = {"platform": ("e2-highmem-4", False, 1), "spot": ("e2-standard-8", True, 2)}
    for item in by_type("google_container_node_pool"):
        after = item["after"]
        if not isinstance(after, dict) or after.get("name") not in expected_pools or after.get("location") != "us-central1-a" or after.get("node_count") != 0:
            raise ValueError("Terraform node pool invariant is invalid")
        name = str(after["name"])
        autoscaling, config = _one(after.get("autoscaling"), "node pool autoscaling"), _one(after.get("node_config"), "node pool config")
        machine, spot, maximum = expected_pools[name]
        if autoscaling.get("min_node_count") != 0 or autoscaling.get("max_node_count") != maximum or config.get("machine_type") != machine or config.get("spot", False) is not spot:
            raise ValueError("Terraform node pool invariant is invalid")
        pool_facts.append({"name": name, "machine_type": machine, "spot": spot, "min": 0, "max": maximum})
    if set(item["name"] for item in pool_facts) != set(expected_pools):
        raise ValueError("Terraform node pool invariant is invalid")

    buckets = by_type("google_storage_bucket")
    if len(buckets) != 1 or not isinstance(buckets[0]["after"], dict):
        raise ValueError("Terraform bucket invariant is invalid")
    bucket = buckets[0]["after"]
    encryption = _one(bucket.get("encryption"), "bucket CMEK")
    cmek = isinstance(encryption.get("default_kms_key_name"), str) and "/cryptoKeys/" in str(encryption["default_kms_key_name"])
    lifecycle: dict[str, list[str]] = {}
    for rule in bucket.get("lifecycle_rule", []):
        if not isinstance(rule, dict):
            raise ValueError("Terraform bucket lifecycle invariant is invalid")
        action, condition = _one(rule.get("action"), "bucket lifecycle action"), _one(rule.get("condition"), "bucket lifecycle condition")
        age, prefixes = condition.get("age"), condition.get("matches_prefix")
        if action.get("type") != "Delete" or age not in (7, 90) or not isinstance(prefixes, list) or not all(isinstance(prefix, str) for prefix in prefixes):
            raise ValueError("Terraform bucket lifecycle invariant is invalid")
        lifecycle[str(age)] = sorted(prefixes)
    expected_lifecycle = {"7": ["agent-substrate/", "langfuse-events/"], "90": ["airflow-logs/", "backups/", "model-cache/"]}
    if lifecycle != expected_lifecycle:
        raise ValueError("Terraform bucket lifecycle invariant is invalid")

    prefix_iam = by_type("google_storage_bucket_iam_member")
    prefix_fingerprints: list[str] = []
    for item in prefix_iam:
        after = item["after"]
        if not isinstance(after, dict) or after.get("role") != "roles/storage.objectUser":
            raise ValueError("Terraform prefix IAM invariant is invalid")
        condition = _one(after.get("condition"), "prefix IAM condition")
        expression = condition.get("expression")
        if not isinstance(expression, str) or not any(f"objects/{prefix}" in expression for prefixes in expected_lifecycle.values() for prefix in prefixes):
            raise ValueError("Terraform prefix IAM invariant is invalid")
        prefix_fingerprints.append(_principal_fingerprint(str(after.get("member", "")).removeprefix("serviceAccount:")))
    if len(prefix_iam) != 5:
        raise ValueError("Terraform prefix IAM invariant is invalid")

    wi = by_type("google_service_account_iam_member")
    wi_fingerprints: set[str] = set()
    ksa_names: set[str] = set()
    for item in wi:
        after = item["after"]
        if not isinstance(after, dict) or after.get("role") != "roles/iam.workloadIdentityUser":
            raise ValueError("Terraform workload identity invariant is invalid")
        member = after.get("member")
        if not isinstance(member, str):
            raise ValueError("Terraform workload identity invariant is invalid")
        match = re.fullmatch(r"serviceAccount:[^.]+\.svc\.id\.goog\[edai2:(edai2-[a-z-]+)\]", member)
        if not match:
            raise ValueError("Terraform workload identity invariant is invalid")
        ksa_names.add(match.group(1))
        wi_fingerprints.add(_service_account_fingerprint(after.get("service_account_id")))
    if ksa_names != {"edai2-retrieval-agent", "edai2-drift-agent", "edai2-coordinator", "edai2-worker"} or len(wi_fingerprints) != 4 or not set(prefix_fingerprints).issubset(wi_fingerprints):
        raise ValueError("Terraform workload identity invariant is invalid")

    kms_members = by_type("google_kms_crypto_key_iam_member")
    if len(kms_members) != 1 or not isinstance(kms_members[0]["after"], dict) or kms_members[0]["after"].get("role") != "roles/cloudkms.cryptoKeyEncrypterDecrypter":
        raise ValueError("Terraform KMS IAM invariant is invalid")
    gcs_fingerprint = _principal_fingerprint(str(kms_members[0]["after"].get("member", "")).removeprefix("serviceAccount:"))

    budgets = by_type("google_billing_budget")
    if len(budgets) != 1 or not isinstance(budgets[0]["after"], dict):
        raise ValueError("Terraform budget invariant is invalid")
    budget = budgets[0]["after"]
    amount = _one(_one(budget.get("amount"), "budget amount").get("specified_amount"), "budget specified amount")
    filters = _one(budget.get("budget_filter"), "budget filter").get("projects")
    thresholds = sorted(rule.get("threshold_percent") for rule in budget.get("threshold_rules", []) if isinstance(rule, dict))
    trial_credit = variables.get("trial_credit_vnd", {}).get("value") if isinstance(variables, dict) else None
    expected_amount = math.floor(trial_credit * 240 / 300) if isinstance(trial_credit, (int, float)) and not isinstance(trial_credit, bool) else None
    if amount.get("currency_code") != "VND" or amount.get("units") != str(expected_amount) or thresholds != [0.5, 0.75, 0.9, 1.0] or not isinstance(filters, list) or len(filters) != 1 or not re.fullmatch(r"projects/\d+", str(filters[0])):
        raise ValueError("Terraform budget invariant is invalid")
    return {
        "zone": "us-central1-a", "cluster": "edai2", "node_pools": sorted(pool_facts, key=lambda item: str(item["name"])),
        "cmek": cmek, "bucket_lifecycle": lifecycle, "prefix_iam_count": len(prefix_iam), "workload_identity_count": len(wi),
        "budget": {"currency": "VND", "amount_vnd": int(amount["units"]), "trial_credit_vnd": trial_credit, "normalized_usd": 240, "thresholds": thresholds, "project_number_filter": True},
        "project_services": sorted(service_names), "data_reads": sorted(kind for kind in types if kind in _TERRAFORM_ALLOWED_DATA_TYPES), "prohibited_resources": 0,
    }, sorted({*wi_fingerprints, gcs_fingerprint})


def sanitize_terraform_payload(payload: object, *, required_resources: set[str], forbidden_resources: set[str] | None = None, plan_sha256: str | None = None, forecast_sha256: str | None = None, revision: str | None = None) -> dict[str, object]:
    """Validate a Terraform plan in memory and return an invariant-bound authorization record."""
    if not isinstance(payload, dict):
        raise ValueError("Terraform plan schema is unsafe")
    allowed_top_level = {"format_version", "terraform_version", "variables", "planned_values", "resource_changes", "output_changes", "resource_drift", "configuration", "prior_state", "timestamp", "errored", "applyable", "complete", "proposed_unknown", "relevant_attributes", "checks"}
    if not set(payload).issubset(allowed_top_level):
        raise ValueError("Terraform plan schema is unsafe")
    format_version = payload.get("format_version")
    if not isinstance(format_version, str) or not re.fullmatch(r"1(?:\.\d+)*", format_version) or payload.get("applyable") is not True or payload.get("complete") is not True or payload.get("errored") is not False:
        raise ValueError("Terraform plan schema is unsafe")
    if any(_has_unsafe_terraform_secret(payload.get(key, {})) for key in ("variables", "planned_values", "output_changes", "resource_drift", "configuration", "prior_state", "resource_changes", "checks", "proposed_unknown", "relevant_attributes")):
        raise ValueError("Terraform plan contains secret-looking values")
    output_changes = payload.get("output_changes", {})
    if not isinstance(output_changes, dict) or any(not isinstance(value, dict) or value.get("after_sensitive") is True or value.get("before_sensitive") is True for value in output_changes.values()):
        raise ValueError("Terraform plan contains sensitive output")
    if not isinstance(payload.get("resource_changes"), list):
        raise ValueError("Terraform plan schema is unsafe")
    changes = payload.get("resource_changes")
    if not isinstance(changes, list) or not changes:
        raise ValueError("Terraform plan has no resource changes")
    resources: list[dict[str, object]] = []
    types: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("Terraform resource change is invalid")
        resource_type = change.get("type")
        address, name, mode = change.get("address"), change.get("name"), change.get("mode")
        details = change.get("change")
        forbidden_types = set().union(*(_FORBIDDEN_RESOURCE_GROUPS.get(group, set()) for group in (forbidden_resources or set())))
        if resource_type in forbidden_types:
            raise ValueError("forbidden Terraform resource")
        if resource_type not in _TERRAFORM_ALLOWED_TYPES | _TERRAFORM_ALLOWED_DATA_TYPES:
            raise ValueError("unexpected Terraform resource")
        if not all(isinstance(value, str) and value for value in (address, name)) or mode not in {"managed", "data"} or not isinstance(details, dict):
            raise ValueError("Terraform resource change is invalid")
        if mode == "data" and resource_type not in _TERRAFORM_ALLOWED_DATA_TYPES:
            raise ValueError("unexpected Terraform data resource")
        if mode == "managed" and resource_type not in _TERRAFORM_ALLOWED_TYPES:
            raise ValueError("unexpected Terraform managed resource")
        if details.get("after_sensitive") not in (None, {}, []):
            raise ValueError("Terraform plan contains sensitive values")
        actions = details.get("actions")
        if actions != (["read"] if mode == "data" else ["create"]):
            raise ValueError("Terraform actions are invalid")
        types.append(resource_type)
        resources.append({"address": address, "type": resource_type, "mode": mode, "after": details.get("after")})
    for requirement in required_resources:
        if requirement not in _TERRAFORM_GROUPS or not (_TERRAFORM_GROUPS[requirement] & set(types)):
            raise ValueError(f"required Terraform resource group missing: {requirement}")
    invariants, principal_fingerprints = _terraform_invariants(resources, types, payload.get("variables", {}))
    hashes = (plan_sha256, forecast_sha256)
    if plan_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        raise ValueError("Terraform authorization hashes are invalid")
    if forecast_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", forecast_sha256):
        raise ValueError("Terraform authorization hashes are invalid")
    if revision is not None and not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Terraform authorization hashes are invalid")
    return {"schema_version": 2, "result": "approved-for-operator-review", "managed_resource_count": sum(item["mode"] == "managed" for item in resources), "data_read_count": sum(item["mode"] == "data" for item in resources), "resource_types": sorted(set(types)), "invariants": invariants, "principal_fingerprints": principal_fingerprints, "plan_sha256": plan_sha256, "forecast_sha256": forecast_sha256, "revision": revision}


def _atomic_new_json(destination: Path, payload: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def sanitize_terraform_plan(
    plan_path: Path,
    output: Path,
    *,
    runner: Callable[[list[str]], str] | None = None,
    required_resources: set[str],
    forbidden_resources: set[str] | None = None,
    forecast_path: Path | None = None,
    revision: str | None = None,
) -> dict[str, object]:
    """Run terraform show without writing its raw JSON, then atomically publish only sanitized data."""
    if output.exists():
        raise FileExistsError(output)
    if (forecast_path is None) != (revision is None):
        raise ValueError("Terraform authorization binding is incomplete")
    forecast_sha256: str | None = None
    if forecast_path is not None:
        if not forecast_path.is_file() or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Terraform authorization inputs are invalid")
        forecast_sha256 = hash_file(forecast_path)
    command = ["terraform", "show", "-json", str(plan_path)]
    if runner is None:
        def runner(command: list[str]) -> str:
            return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    raw = runner(command)
    try:
        sanitized = sanitize_terraform_payload(
            json.loads(raw), required_resources=required_resources,
            forbidden_resources=forbidden_resources, plan_sha256=hash_file(plan_path),
            forecast_sha256=forecast_sha256, revision=revision,
        )
    finally:
        raw = ""
    _atomic_new_json(output, sanitized)
    return sanitized


def sanitize_private_terraform_plan(
    operator_inputs: Path,
    output: Path,
    *,
    workspace: Path,
    operator_loader: Callable[[str | Path, Path], dict[str, object]] = load_topic22_operator_inputs,
    runner: Callable[[list[str], dict[str, str]], str] | None = None,
    revision: str | None = None,
) -> dict[str, object]:
    """Sanitize only the fixed private Terraform plan named by the validated bundle; public argv never carries its path."""
    operator = operator_loader(operator_inputs, workspace)
    paths = operator.get("resolved_paths") if isinstance(operator, dict) else None
    if not isinstance(paths, dict) or not all(isinstance(paths.get(name), Path) for name in ("tf_data_dir", "gcloud_config_dir", "application_default_credentials")):
        raise ValueError("private Terraform plan bundle is invalid")
    plan = paths["tf_data_dir"] / "topic22.tfplan"
    if not plan.is_file():
        raise ValueError("private Terraform plan bundle is invalid")
    forecast = workspace / "evidence" / "04_2_llm_design" / "gke" / "cost_forecast_topic22.json"
    current_revision = _revision() if revision is None else revision
    environment = dict(os.environ)
    environment.update({"TF_DATA_DIR": str(paths["tf_data_dir"]), "CLOUDSDK_CONFIG": str(paths["gcloud_config_dir"]), "GOOGLE_APPLICATION_CREDENTIALS": str(paths["application_default_credentials"])})
    invoke = runner or (lambda command, env: subprocess.run(command, env=env, check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    return sanitize_terraform_plan(
        plan, output, runner=lambda command: invoke(command, environment),
        required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"},
        forbidden_resources={"vm", "cloud-build", "load-balancer"}, forecast_path=forecast, revision=current_revision,
    )


def _wrap(value: str, width: int = 92) -> list[str]:
    words, lines, current = value.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_topic22_png(machine_evidence: dict[str, object], output: Path, *, machine_path: Path | None = None) -> None:
    """Render a wrapped, hash-bound 1600x1000 Topic 22 apply panel."""
    if not isinstance(machine_evidence, dict) or machine_evidence.get("result") != "successful":
        raise ValueError("Terraform screenshot evidence is not successful")
    revision, plan_sha = machine_evidence.get("revision"), machine_evidence.get("plan_sha256")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision) or not isinstance(plan_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_sha):
        raise ValueError("Terraform screenshot evidence is not authorization-bound")
    linked_path = str(machine_path) if machine_path is not None else "<linked machine record>"
    linked_sha = hash_file(machine_path) if machine_path is not None else "<manifest SHA-256>"
    pools = machine_evidence.get("node_pools", [])
    pool_summary = ", ".join(f"{pool.get('name')} min={pool.get('min')} max={pool.get('max')}" for pool in pools if isinstance(pool, dict))
    lines = [
        "EDAI2 Topic 22 Terraform apply evidence", "Result: successful", f"Revision: {revision}",
        f"Approved plan SHA-256: {plan_sha}", f"Linked machine record: {linked_path}", f"Machine record SHA-256: {linked_sha}",
        f"Zone: {machine_evidence.get('zone')}", f"Node pools: {pool_summary}",
        f"Registries: {len(machine_evidence.get('registries', []))}", f"Workload Identity bindings: {len(machine_evidence.get('workload_identity', []))}",
        f"Forwarding rules: {machine_evidence.get('forwarding_rule_count')}",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 1000), color=(18, 34, 52))
    drawer = ImageDraw.Draw(image)
    drawer.rectangle((70, 70, 1530, 930), fill=(245, 247, 250), outline=(55, 110, 160), width=4)
    y = 110
    for line in lines:
        for wrapped in _wrap(line):
            drawer.text((120, y), wrapped, fill=(16, 44, 72))
            y += 42
        y += 7
    from PIL.PngImagePlugin import PngInfo
    metadata = PngInfo(); metadata.add_text("topic22_text", "\n".join(lines))
    image.save(output, "PNG", pnginfo=metadata)


def topic22_png_text(path: Path) -> str:
    with Image.open(path) as image:
        return str(image.info.get("topic22_text", ""))


def verify_topic22_screenshots(manifest_path: Path, root: Path, names: list[str], *, revision: str | None = None, workspace: Path | None = None) -> None:
    if names not in (["gcp_billing_spend.png", "terraform_apply.png"], ["terraform_apply.png"]):
        raise ValueError("Topic 22 screenshot set is invalid")
    entries = _validate_existing_manifest(manifest_path, root, revision or _manifest_revision(manifest_path), workspace=workspace)
    actual = {entry["path"] for entry in entries}
    if not set(names).issubset(actual):
        raise ValueError("Topic 22 screenshot is missing")


def _manifest_revision(manifest_path: Path) -> str:
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        raise ValueError("manifest is invalid")
    revision = entries[0].get("commit_or_revision")
    if not isinstance(revision, str):
        raise ValueError("manifest revision is invalid")
    return revision


def validate_private_endpoint(inventory: dict[str, object], key: str, signature: str, verifier: Callable[[bytes, str], bool] | None = None) -> dict[str, object]:
    if key not in PRIVATE_ENDPOINT_KEYS:
        raise ValueError("unknown private endpoint")
    if not isinstance(inventory, dict) or set(inventory) != {"private_endpoints"}:
        raise ValueError("private endpoint inventory keys are stale or incomplete")
    verify = verifier or (lambda payload, supplied: hashlib.sha256(payload).hexdigest() == supplied)
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature) or not verify(_canonical_inventory(inventory), signature):
        raise ValueError("private endpoint inventory signature is invalid")
    endpoints = inventory["private_endpoints"]
    if not isinstance(endpoints, dict) or set(endpoints) != set(PRIVATE_ENDPOINT_KEYS):
        raise ValueError("private endpoint inventory keys are stale or incomplete")
    selected: dict[str, object] | None = None
    for endpoint_key, entry in endpoints.items():
        _validate_private_endpoint_entry(entry)
        if endpoint_key == key:
            selected = entry
    if selected is None:
        raise ValueError("private endpoint inventory entry is invalid")
    return selected


def _validate_private_endpoint_entry(entry: object) -> None:
    if not isinstance(entry, dict) or set(entry) != PRIVATE_ENDPOINT_FIELDS:
        raise ValueError("private endpoint inventory entry is invalid")
    text_fields = ("namespace", "service_name", "service_uid")
    if any(not isinstance(entry[name], str) or not entry[name] or len(entry[name]) > 253 for name in text_fields):
        raise ValueError("private endpoint inventory entry is invalid")
    if any(type(entry[name]) is not int or not 1 <= entry[name] <= 65535 for name in ("service_port", "target_port")):
        raise ValueError("private endpoint inventory entry is invalid")
    if not isinstance(entry["selector_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["selector_sha256"]):
        raise ValueError("private endpoint inventory entry is invalid")
    ready = entry["ready_endpoint_uids"]
    if not isinstance(ready, list) or not ready or any(not isinstance(uid, str) or not uid for uid in ready) or len(set(ready)) != len(ready):
        raise ValueError("private endpoint inventory entry is invalid")


def validate_labels(labels: dict[str, str]) -> None:
    if set(labels) - set(STABLE_LABELS) or any(not isinstance(value, str) or not value or len(value) > 128 for value in labels.values()):
        raise ValueError("telemetry label is unknown, unsafe, or high-cardinality")
    if any(_SECRET.search(name) for name in labels):
        raise ValueError("telemetry label contains forbidden PII")


def validate_trace_fixture(spans: list[dict[str, str | None]]) -> None:
    roots = [span["span"] for span in spans if span.get("parent") is None]
    if roots != ["nginx/chat"]:
        raise ValueError("trace must contain exactly one nginx/chat root")
    if {span.get("span"): span.get("parent") for span in spans} != {span["span"]: span["parent"] for span in TRACE_FIXTURE}:
        raise ValueError("trace parent chain is incomplete or has a new root")


def validate_observability_contract(root: Path) -> None:
    """Check the local telemetry fixtures without contacting an observability backend."""
    expected_alerts = {
        "EDAI2ApiToolFailureHigh": {"pending": {"failure_ratio": 0.06}, "firing": {"failure_ratio": 0.06, "for_seconds": 300}},
        "EDAI2RetrievalP95High": {"pending": {"p95_seconds": 0.76}, "firing": {"p95_seconds": 0.76, "for_seconds": 300}},
        "EDAI2ActiveIndexStale": {"pending": {"age_seconds": 86401}, "firing": {"age_seconds": 86401, "for_seconds": 300}},
        "EDAI2MemoryHigh": {"pending": {"usage_ratio": 0.91}, "firing": {"usage_ratio": 0.91, "for_seconds": 300}},
        "EDAI2DiskHigh": {"pending": {"usage_ratio": 0.81}, "firing": {"usage_ratio": 0.81, "for_seconds": 300}},
    }
    if STABLE_LABELS != ("service", "route", "agent", "tool", "model_version", "agent_config", "index_version", "status", "safety_action", "log_scope") or ALERT_FIXTURES != expected_alerts:
        raise ValueError("telemetry fixture contract is invalid")
    validate_trace_fixture(TRACE_FIXTURE)
    dashboards = list((root / "infra/observability/grafana/dashboards").glob("*.json"))
    if {path.stem for path in dashboards} != {"http", "compute", "agents", "llm", "ab"}:
        raise ValueError("dashboard contract is invalid")
    alloy = (root / "infra/observability/alloy/config.alloy").read_text(encoding="utf-8")
    if 'log_scope = "application"' not in alloy or 'log_scope = "system"' not in alloy:
        raise ValueError("log scopes are not separated")
    for dashboard in dashboards:
        payload = json.loads(dashboard.read_text(encoding="utf-8"))
        for panel in payload.get("panels", []):
            for target in panel.get("targets", []):
                query = target.get("expr", "")
                if "log_scope=~" in query:
                    raise ValueError("dashboard merges log scopes")


def _validate_gke_target(kubeconfig: Path, context: str) -> None:
    if not kubeconfig.is_absolute() or not kubeconfig.is_file():
        raise ValueError("absolute readable kubeconfig is required")
    contexts = {item.get("name") for item in (yaml.safe_load(kubeconfig.read_text(encoding="utf-8")) or {}).get("contexts", []) if isinstance(item, dict)}
    if context not in contexts or not context.startswith("gke_"):
        raise ValueError("exact GKE context is required")


def _validate_tunnel_ttl(value: str) -> None:
    match = re.fullmatch(r"([1-9][0-9]*)(m|h)", value)
    if not match or int(match.group(1)) * (60 if match.group(2) == "h" else 1) > 60:
        raise ValueError("tunnel TTL must be a positive bounded duration")


def build_port_forward_command(kubeconfig: Path, context: str, namespace: str, service: str, local_port: int, service_port: int, address: str = "127.0.0.1") -> list[str]:
    if not kubeconfig.is_absolute() or not context.startswith("gke_") or address != "127.0.0.1" or type(local_port) is not int or not 1024 < local_port <= 65535 or type(service_port) is not int or not 1 <= service_port <= 65535:
        raise ValueError("private tunnels require explicit loopback ports and target")
    return ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context, "-n", namespace, "port-forward", "--address", address, f"service/{service}", f"{local_port}:{service_port}"]


def _cleanup_child(process: object) -> None:
    errors: list[BaseException] = []
    for method, args in (("terminate", ()), ("wait", (5,)), ("poll", ())):
        try:
            outcome = getattr(process, method)(*args)
            if method == "poll" and outcome is None:
                errors.append(RuntimeError("port-forward child leaked"))
        except BaseException as error:
            errors.append(error)
    if errors:
        raise errors[0]


def _remove_runtime(runtime_root: Path) -> None:
    for name in ("stdout.log", "stderr.log", "pid.txt"):
        (runtime_root / name).unlink(missing_ok=True)
    runtime_root.rmdir()


def run_private_capture(*, kubeconfig: Path, context: str, inventory: dict[str, object], inventory_signature: str, key: str, observed: dict[str, object], loopback_only: bool, tunnel_ttl: str, runtime_root: Path, reserve_port: Callable[[], int], process_factory: Callable[..., object], readiness: Callable[[], None], capture_callback: Callable[[dict[str, str]], object], verifier: Callable[[bytes, str], bool] | None = None) -> object:
    _validate_gke_target(kubeconfig, context)
    if not loopback_only:
        raise ValueError("--loopback-only is required")
    _validate_tunnel_ttl(tunnel_ttl)
    expected = validate_private_endpoint(inventory, key, inventory_signature, verifier)
    if observed != expected:
        raise ValueError("private endpoint readback mismatch")
    local_port = reserve_port()
    command = build_port_forward_command(kubeconfig, context, str(expected["namespace"]), str(expected["service_name"]), local_port, int(expected["service_port"]))
    if runtime_root.exists():
        raise ValueError("owned runtime root already exists")
    runtime_root.mkdir(parents=True)
    stdout_path, stderr_path, pid_path = runtime_root / "stdout.log", runtime_root / "stderr.log", runtime_root / "pid.txt"
    process: object | None = None
    try:
        process = process_factory(command, stdout_path, stderr_path)
        start = getattr(process, "start", None)
        if callable(start):
            start()
        pid = getattr(process, "pid", None)
        if type(pid) is not int or pid <= 0:
            raise ValueError("port-forward child has no PID")
        pid_path.write_text(str(pid), encoding="utf-8")
        stdout_path.touch()
        stderr_path.touch()
        readiness()
        return capture_callback({"private_endpoint_key": key, "service_uid": str(expected["service_uid"])})
    finally:
        cleanup_error: BaseException | None = None
        if process is not None:
            try:
                _cleanup_child(process)
            except BaseException as error:
                cleanup_error = error
        _remove_runtime(runtime_root)
        if cleanup_error is not None:
            raise cleanup_error


def _validate_png(path: Path) -> tuple[int, int]:
    if not path.is_file() or path.read_bytes()[:8] != _PNG:
        raise ValueError("PNG signature is invalid")
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        image.load()
        if image.format != "PNG" or image.size != (1600, 1000):
            raise ValueError("capture must be a 1600x1000 PNG")
        colors = image.convert("RGB").getcolors(maxcolors=2)
        if image.convert("RGB").getbbox() is None or colors is not None and len(colors) == 1:
            raise ValueError("capture is blank or near-uniform")
        return image.size


def _validate_existing_manifest(manifest_path: Path, root: Path, revision: str, *, workspace: Path | None = None) -> list[dict[str, object]]:
    if not manifest_path.exists():
        return []
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("manifest is not valid JSON") from error
    if not isinstance(entries, list) or any(not isinstance(item, dict) or set(item) != set(MANIFEST_FIELDS) for item in entries):
        raise ValueError("manifest schema is invalid")
    if len({item["path"] for item in entries}) != len(entries) or len({item["sha256"] for item in entries}) != len(entries):
        raise ValueError("manifest has duplicate paths or hashes")
    for entry in entries:
        _validate_existing_entry(entry, root, revision, workspace=workspace)
    return entries


def _validate_existing_entry(entry: dict[str, object], root: Path, revision: str, *, workspace: Path | None = None) -> None:
    relative = entry["path"]
    if not isinstance(relative, str) or relative not in REQUIRED_VIEWS:
        raise ValueError("manifest entry is invalid")
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("manifest entry is invalid")
    if type(entry["width"]) is not int or type(entry["height"]) is not int or (entry["width"], entry["height"]) != (1600, 1000):
        raise ValueError("manifest entry is invalid")
    captured = entry["captured_at_utc"]
    try:
        timestamp = datetime.fromisoformat(captured.replace("Z", "+00:00")) if isinstance(captured, str) else None
    except ValueError as error:
        raise ValueError("manifest entry is invalid") from error
    now = datetime.now(UTC)
    if timestamp is None or timestamp.tzinfo is None or timestamp < now.replace(hour=0, minute=0, second=0, microsecond=0) or timestamp > now:
        raise ValueError("manifest entry is invalid")
    source = entry["url_or_source"]
    if not isinstance(source, str) or not source.startswith("https://") or _BAD_PAGE.search(source) or _SECRET.search(source):
        raise ValueError("manifest entry is invalid")
    if entry["commit_or_revision"] != revision or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("manifest entry is invalid")
    if entry["visible_selectors"] != REQUIRED_VIEWS[relative]:
        raise ValueError("manifest entry is invalid")
    for field in ("visible_selectors", "linked_machine_evidence"):
        value = entry[field]
        if not isinstance(value, list) or not value:
            raise ValueError("manifest entry is invalid")
    workspace = (Path.cwd() if workspace is None else workspace).resolve()
    for linked in entry["linked_machine_evidence"]:
        if not isinstance(linked, dict) or set(linked) != {"path", "sha256"} or not isinstance(linked["path"], str) or not re.fullmatch(r"[0-9a-f]{64}", str(linked["sha256"])):
            raise ValueError("manifest machine evidence is invalid")
        linked_path = Path(linked["path"])
        if linked_path.is_absolute() or ".." in linked_path.parts:
            raise ValueError("manifest machine evidence is invalid")
        machine = (workspace / linked_path).resolve()
        if workspace not in machine.parents or not machine.is_file() or hash_file(machine) != linked["sha256"]:
            raise ValueError("manifest machine evidence hash mismatch")
        try:
            decoded = json.loads(machine.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("manifest machine evidence is invalid") from error
        if not isinstance(decoded, dict) or _has_secret(decoded) or decoded.get("revision") not in (None, revision):
            raise ValueError("manifest machine evidence is invalid")
        if relative == "terraform_apply.png":
            validate_sanitized_apply_evidence(decoded)
            text = topic22_png_text(path)
            required_text = (
                "EDAI2 Topic 22 Terraform apply evidence", "Result: successful", revision,
                str(decoded.get("plan_sha256", "")), str(linked["sha256"]), "Zone: us-central1-a",
            )
            if not all(value and value in text for value in required_text):
                raise ValueError("manifest Terraform PNG binding is invalid")
    approved_plan_sha = entry["approved_plan_sha256"]
    if approved_plan_sha is not None and (not isinstance(approved_plan_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", approved_plan_sha)):
        raise ValueError("manifest entry is invalid")
    for field in ("proves", "does_not_prove"):
        value = entry[field]
        if not isinstance(value, str) or not value or len(value) > 500 or _SECRET.search(value):
            raise ValueError("manifest entry is invalid")
    digest = entry["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("manifest entry is invalid")
    _validate_png(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("manifest entry is invalid")


def record_capture(*, final_path: Path, root: Path, writer: Callable[[Path], None], source: str, revision: str, visible_selectors: list[str], machine_evidence: list[str], proves: str, does_not_prove: str, manifest_path: Path, workspace: Path | None = None, replace: Callable[[Path, Path], None] = os.replace) -> dict[str, object]:
    root, final_path, manifest_path = root.resolve(), final_path.resolve(), manifest_path.resolve()
    workspace = (Path.cwd() if workspace is None else workspace).resolve()
    expected = REQUIRED_VIEWS.get(final_path.name)
    safe_source = source.startswith("https://") and not _BAD_PAGE.search(source) and not _SECRET.search(source)
    safe_lists = visible_selectors == expected and all(isinstance(item, str) and item for item in machine_evidence)
    if root not in final_path.parents or root not in manifest_path.parents or expected is None or not safe_source or not re.fullmatch(r"[0-9a-f]{40}", revision) or not safe_lists or not machine_evidence or not proves or not does_not_prove or len(proves) > 500 or len(does_not_prove) > 500 or _SECRET.search(proves + does_not_prove):
        raise ValueError("capture metadata is unsafe or incomplete")
    temporary, manifest_temp = final_path.with_name(f".{final_path.stem}.tmp.png"), manifest_path.with_name(f".{manifest_path.name}.tmp")
    rollback_png, rollback_manifest = final_path.with_name(f".{final_path.name}.rollback"), manifest_path.with_name(f".{manifest_path.name}.rollback")
    previous_final, previous_manifest = (final_path.read_bytes() if final_path.exists() else None), (manifest_path.read_bytes() if manifest_path.exists() else None)
    try:
        writer(temporary)
        width, height = _validate_png(temporary)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        linked = []
        approved_plan_sha: str | None = None
        for value in machine_evidence:
            machine = Path(value).resolve()
            if not machine.is_file():
                raise ValueError("linked machine evidence is missing")
            try:
                relative_machine = machine.relative_to(workspace).as_posix()
            except ValueError as error:
                raise ValueError("linked machine evidence is outside the workspace") from error
            linked.append({"path": relative_machine, "sha256": hash_file(machine)})
            decoded = json.loads(machine.read_text(encoding="utf-8"))
            if not isinstance(decoded, dict) or _has_secret(decoded):
                raise ValueError("linked machine evidence is unsafe")
            if final_path.name == "terraform_apply.png":
                candidate = decoded.get("plan_sha256")
                if not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate):
                    raise ValueError("linked machine evidence lacks an approved plan hash")
                approved_plan_sha = candidate
        entry = {"path": final_path.relative_to(root).as_posix(), "width": width, "height": height, "captured_at_utc": datetime.now(UTC).isoformat(), "url_or_source": source, "commit_or_revision": revision, "visible_selectors": visible_selectors, "linked_machine_evidence": linked, "approved_plan_sha256": approved_plan_sha, "sha256": digest, "proves": proves, "does_not_prove": does_not_prove}
        existing = _validate_existing_manifest(manifest_path, root, revision, workspace=workspace)
        if any(item["path"] == entry["path"] or item["sha256"] == digest for item in existing):
            raise ValueError("duplicate capture hash")
        manifest_temp.write_text(json.dumps([*existing, entry], indent=2) + "\n", encoding="utf-8")
        try:
            replace(temporary, final_path)
            replace(manifest_temp, manifest_path)
        except BaseException:
            if previous_final is None:
                final_path.unlink(missing_ok=True)
            else:
                rollback_png.write_bytes(previous_final); replace(rollback_png, final_path)
            if previous_manifest is None:
                manifest_path.unlink(missing_ok=True)
            else:
                rollback_manifest.write_bytes(previous_manifest); replace(rollback_manifest, manifest_path)
            raise
        return entry
    finally:
        for path in (temporary, manifest_temp, rollback_png, rollback_manifest):
            path.unlink(missing_ok=True)


def _revision() -> str:
    revision = subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("revision is invalid")
    return revision


def _browser_writer_with_state(url: str, selectors: list[str], storage_state: Path) -> Callable[[Path], None]:
    def writer(destination: Path) -> None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={"width": 1600, "height": 1000}, storage_state=str(storage_state))
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=60_000)
                visible_text = page.locator("body").inner_text(timeout=10_000)
                if _BAD_PAGE.search(visible_text) or _SECRET.search(visible_text) or re.search(r"\b\d{4,}[- ]\d{4,}[- ]\d{4,}\b", visible_text):
                    raise ValueError("authenticated billing page is unsafe")
                if any(selector.lower() not in visible_text.lower() for selector in selectors):
                    raise ValueError("required billing selectors are not visible")
                page.screenshot(path=str(destination), full_page=False)
            finally:
                context.close()
                browser.close()
    return writer


def _playwright_page_factory(storage_state: Path):
    from playwright.sync_api import sync_playwright

    manager = sync_playwright().start()
    browser = manager.chromium.launch()
    context = browser.new_context(viewport={"width": 1600, "height": 1000}, storage_state=str(storage_state))
    page = context.new_page()
    page._topic22_resources = (context, browser, manager)  # type: ignore[attr-defined]
    return page


def _billing_page_writer(
    url: str,
    storage_state: Path,
    *,
    project_alias_sha256: str,
    operator_project: str = "",
    raw_identifiers: tuple[str, ...] = (),
    observed_at: str,
    required_markers: list[str],
    pii_selectors: list[str],
    page_factory: Callable[[Path], object] = _playwright_page_factory,
) -> Callable[[Path], None]:
    """Capture an authenticated real Console page after masking PII and adding a sanitized observation banner."""
    required_markers, pii_selectors = validate_billing_selectors(required_markers, pii_selectors)
    if not re.fullmatch(r"[0-9a-f]{64}", project_alias_sha256) or not required_markers or not pii_selectors:
        raise ValueError("billing capture contract is incomplete")
    _parse_capture_time(observed_at)

    def writer(destination: Path) -> None:
        page = page_factory(storage_state)
        resources = getattr(page, "_topic22_resources", ())
        try:
            page.goto(url, wait_until="networkidle", timeout=60_000)
            if not str(page.url).startswith("https://console.cloud.google.com/billing"):
                raise ValueError("billing page redirected outside Billing Console")
            for marker in required_markers:
                page.wait_for_selector(marker, state="visible", timeout=10_000)
            body = page.locator("body").inner_text(timeout=10_000)
            if _BAD_PAGE.search(body):
                raise ValueError("authenticated billing page is not ready")
            for selector in pii_selectors:
                locator = page.locator(selector)
                if locator.count() < 1:
                    raise ValueError("required billing PII mask target is absent")
                locator.evaluate_all("nodes => nodes.forEach(node => { node.textContent = '[REDACTED]'; node.style.filter = 'blur(8px)'; })")
            post_mask = page.locator("body").inner_text(timeout=10_000)
            if (operator_project and operator_project in post_mask) or any(value and value in post_mask for value in raw_identifiers):
                raise ValueError("billing page redaction is incomplete")
            annotation = {"project_alias_sha256": project_alias_sha256, "observed_at_utc": observed_at}
            page.evaluate("annotation => { const banner=document.createElement('div'); banner.id='edai2-sanitized-observation'; banner.textContent=`EDAI2 sanitized observation | project alias ${annotation.project_alias_sha256} | observed ${annotation.observed_at_utc}`; Object.assign(banner.style,{position:'fixed',top:'0',left:'0',right:'0',zIndex:'2147483647',background:'#0b3558',color:'white',padding:'12px',font:'16px sans-serif'}); document.body.appendChild(banner); }", annotation)
            page.screenshot(path=str(destination), full_page=False)
        finally:
            for resource in resources:
                resource.close() if hasattr(resource, "close") else resource.stop()
    return writer


def billing_writer_from_operator(
    operator: dict[str, object],
    *,
    page_factory: Callable[[Path], object] = _playwright_page_factory,
) -> Callable[[Path], None]:
    """Construct the browser writer solely from an already validated private bundle."""
    resolved = operator.get("resolved_paths")
    if not isinstance(resolved, dict) or not isinstance(resolved.get("browser_storage_state"), Path):
        raise ValueError("private browser state is absent")
    project, url, observed = operator.get("project_id"), operator.get("billing_console_url"), operator.get("spend_observed_at")
    if not all(isinstance(value, str) and value for value in (project, url, observed)):
        raise ValueError("billing operator input is invalid")
    return _billing_page_writer(
        url, resolved["browser_storage_state"],
        project_alias_sha256=hashlib.sha256(project.encode()).hexdigest(),
        operator_project=project,
        raw_identifiers=tuple(str(operator.get(key, "")) for key in ("project_id", "billing_account_id", "recovery_sink", "budget_notification_target")),
        observed_at=observed,
        required_markers=operator.get("billing_required_markers"),
        pii_selectors=operator.get("billing_pii_selectors"),
        page_factory=page_factory,
    )


def _parse_capture_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("billing observation timestamp must include timezone")
    return parsed


def validate_private_browser_state(value: str | Path, workspace: Path) -> Path:
    path, root = Path(value).resolve(), (workspace / "tmp" / "edai2-gcp").resolve()
    if root not in path.parents or not path.is_file() or path.suffix.lower() != ".json":
        raise ValueError("private browser state is invalid")
    return path


class Topic22InventoryAdapter(Protocol):
    def read(self, operator_inputs: Path) -> dict[str, object]: ...


class GcloudRestTopic22InventoryAdapter:
    """Production read-only inventory boundary; the private bundle supplies all identifiers off-argv."""

    def __init__(
        self,
        *,
        workspace: Path | None = None,
        operator_loader: Callable[[Path, Path], dict[str, object]] | None = None,
        runner: Callable[[list[str], dict[str, str]], str] | None = None,
        token_supplier: Callable[[], str] | None = None,
        requester: Callable[[str, str, dict[str, str], dict[str, object] | None], dict[str, object]] | None = None,
    ) -> None:
        self._workspace = (Path.cwd() if workspace is None else workspace).resolve()
        if operator_loader is None:
            operator_loader = load_topic22_operator_inputs
        self._operator_loader = operator_loader
        self._runner = runner or self._run
        self._token_supplier = token_supplier
        if requester is None:
            requester = topic22_rest_request
        self._requester = requester

    @staticmethod
    def _run(command: list[str], environment: dict[str, str]) -> str:
        return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8", env=environment).stdout

    def _json_command(self, command: list[str], environment: dict[str, str]) -> object:
        raw = self._runner(command, environment)
        try:
            return json.loads(raw)
        finally:
            raw = ""

    def read(self, operator_inputs: Path) -> dict[str, object]:
        operator = self._operator_loader(operator_inputs, self._workspace)
        if not isinstance(operator, dict) or not isinstance(operator.get("resolved_paths"), dict):
            raise ValueError("private inventory input is invalid")
        paths = operator["resolved_paths"]
        project, billing = operator.get("project_id"), operator.get("billing_account_id")
        if not all(isinstance(value, str) and value for value in (project, billing)):
            raise ValueError("private inventory identifiers are invalid")
        environment = dict(os.environ)
        environment.update({
            "TF_DATA_DIR": str(paths["tf_data_dir"]),
            "CLOUDSDK_CONFIG": str(paths["gcloud_config_dir"]),
            "GOOGLE_APPLICATION_CREDENTIALS": str(paths["application_default_credentials"]),
        })
        outputs = self._json_command(["terraform", "-chdir=infra/terraform/edai2", "output", "-json"], environment)
        if not isinstance(outputs, dict):
            raise ValueError("Terraform output readback is invalid")

        def output(name: str) -> object:
            entry = outputs.get(name)
            if not isinstance(entry, dict) or "value" not in entry:
                raise ValueError(f"Terraform output is missing: {name}")
            return entry["value"]

        bucket_name, kms_key, wi_outputs = output("bucket_name"), output("kms_key_id"), output("workload_identity_bindings")
        if not all(isinstance(value, str) and value for value in (bucket_name, kms_key)) or not isinstance(wi_outputs, dict):
            raise ValueError("Terraform foundation outputs are invalid")
        backend_text = Path(paths["terraform_backend_config"]).read_text(encoding="utf-8")
        backend_values = dict(re.findall(r'^\s*(bucket|prefix)\s*=\s*"([^"\r\n]+)"\s*$', backend_text, flags=re.MULTILINE))
        if set(backend_values) != {"bucket", "prefix"}:
            raise ValueError("Terraform backend readback is invalid")

        token = self._token_supplier() if self._token_supplier is not None else self._runner(["gcloud", "auth", "print-access-token"], environment).strip()
        if not token:
            raise ValueError("inventory access token is empty")

        def rest(method: str, url: str, body: dict[str, object] | None = None) -> dict[str, object]:
            result = self._requester(method, url, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, body)
            if not isinstance(result, dict):
                raise ValueError("inventory REST response is invalid")
            return result

        def paged(url: str, item_key: str) -> list[dict[str, object]]:
            """Read bounded REST pages and reject cycles before a partial inventory can pass."""
            token: str | None = None
            seen: set[str] = set()
            results: list[dict[str, object]] = []
            for _ in range(20):
                suffix = "" if token is None else ("&" if "?" in url else "?") + urlencode({"pageToken": token})
                payload = rest("GET", url + suffix)
                values = payload.get(item_key, [])
                if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
                    raise ValueError("paged inventory REST response is invalid")
                results.extend(values)
                next_token = payload.get("nextPageToken")
                if next_token is None:
                    return results
                if not isinstance(next_token, str) or not next_token or next_token in seen:
                    raise ValueError("paged inventory REST response is invalid")
                seen.add(next_token)
                token = next_token
            raise ValueError("paged inventory REST response is invalid")

        try:
            encoded_project = quote(project, safe="")
            project_payload = rest("GET", f"https://cloudresourcemanager.googleapis.com/v3/projects/{encoded_project}")
            project_number = resource_manager_project_number(project_payload, project)
            cluster = rest("GET", f"https://container.googleapis.com/v1/projects/{encoded_project}/zones/us-central1-a/clusters/edai2")
            pools_payload = rest("GET", f"https://container.googleapis.com/v1/projects/{encoded_project}/zones/us-central1-a/clusters/edai2/nodePools")
            repositories = paged(f"https://artifactregistry.googleapis.com/v1/projects/{encoded_project}/locations/us-central1/repositories", "repositories")
            encoded_bucket = quote(bucket_name, safe="")
            bucket = rest("GET", f"https://storage.googleapis.com/storage/v1/b/{encoded_bucket}")
            bucket_iam = rest("GET", f"https://storage.googleapis.com/storage/v1/b/{encoded_bucket}/iam")
            storage_service_account = rest("GET", f"https://storage.googleapis.com/storage/v1/projects/{encoded_project}/serviceAccount")
            encoded_key = quote(kms_key, safe="/")
            kms = rest("GET", f"https://cloudkms.googleapis.com/v1/{encoded_key}")
            kms_iam = rest("POST", f"https://cloudkms.googleapis.com/v1/{encoded_key}:getIamPolicy", {})
            budget_items = paged(f"https://billingbudgets.googleapis.com/v1/billingAccounts/{quote(billing, safe='')}/budgets", "budgets")
            forwarding_rules = paged_aggregated_forwarding_rules(rest, f"https://compute.googleapis.com/compute/v1/projects/{encoded_project}/aggregated/forwardingRules")
            instance_group_managers = paged_aggregated_instance_group_managers(rest, f"https://compute.googleapis.com/compute/v1/projects/{encoded_project}/aggregated/instanceGroupManagers")
            backend_query = urlencode({"prefix": backend_values["prefix"]})
            backend_items = paged(f"https://storage.googleapis.com/storage/v1/b/{quote(backend_values['bucket'], safe='')}/o?{backend_query}", "items")

            pool_facts = []
            managers_by_link = {manager.get("selfLink"): manager for manager in instance_group_managers if isinstance(manager.get("selfLink"), str)}
            for pool in pools_payload.get("nodePools", []):
                if not isinstance(pool, dict):
                    raise ValueError("node pool REST response is invalid")
                autoscaling, config = pool.get("autoscaling"), pool.get("config")
                if not isinstance(autoscaling, dict) or not isinstance(config, dict):
                    raise ValueError("node pool REST response is invalid")
                groups = pool.get("instanceGroupUrls")
                if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], str) or groups[0] not in managers_by_link:
                    raise ValueError("node pool live capacity REST response is invalid")
                target_size = managers_by_link[groups[0]].get("targetSize")
                if not isinstance(target_size, int) or isinstance(target_size, bool) or target_size < 0:
                    raise ValueError("node pool live capacity REST response is invalid")
                pool_facts.append({"name": str(pool.get("name", "")).rsplit("/", 1)[-1], "machine_type": config.get("machineType"), "spot": config.get("spot", False), "min": autoscaling.get("minNodeCount"), "max": autoscaling.get("maxNodeCount"), "current": target_size})
            registries = [{"name": str(repo.get("name", "")).rsplit("/", 1)[-1], "format": repo.get("format"), "location": "us-central1"} for repo in repositories]
            rules: dict[str, list[str]] = {}
            lifecycle = bucket.get("lifecycle", {})
            for rule in lifecycle.get("rule", []) if isinstance(lifecycle, dict) else []:
                if not isinstance(rule, dict) or not isinstance(rule.get("condition"), dict):
                    raise ValueError("bucket lifecycle REST response is invalid")
                rules[str(rule["condition"].get("age"))] = sorted(rule["condition"].get("matchesPrefix", []))
            prefix_iam = []
            for binding in bucket_iam.get("bindings", []):
                if not isinstance(binding, dict) or binding.get("role") != "roles/storage.objectUser" or not isinstance(binding.get("condition"), dict):
                    continue
                expression = str(binding["condition"].get("expression", ""))
                prefix = next((candidate for candidate in ("model-cache/", "agent-substrate/", "langfuse-events/", "airflow-logs/", "backups/") if f"objects/{candidate}" in expression), "")
                members = binding.get("members", [])
                if not prefix or not isinstance(members, list) or len(members) != 1:
                    raise ValueError("prefix IAM REST response is invalid")
                prefix_iam.append({"prefix": prefix, "gsa_sha256": hashlib.sha256(str(members[0]).removeprefix("serviceAccount:").encode()).hexdigest(), "role": binding["role"]})
            workload_identity = []
            for workload, expected in wi_outputs.items():
                if not isinstance(expected, dict):
                    raise ValueError("workload identity output is invalid")
                gsa, ksa, prefixes = expected.get("gsa"), expected.get("ksa"), expected.get("prefixes")
                if not isinstance(gsa, str) or not isinstance(ksa, str) or not isinstance(prefixes, list):
                    raise ValueError("workload identity output is invalid")
                policy = rest("POST", f"https://iam.googleapis.com/v1/projects/-/serviceAccounts/{quote(gsa, safe='@.')}:getIamPolicy", {})
                wi_members = [member for binding in policy.get("bindings", []) if isinstance(binding, dict) and binding.get("role") == "roles/iam.workloadIdentityUser" for member in binding.get("members", [])]
                if wi_members != [ksa]:
                    raise ValueError("workload identity REST response is invalid")
                workload_identity.append({"workload": workload, "ksa": ksa.removesuffix("]").rsplit(":", 1)[-1], "ksa_member_sha256": hashlib.sha256(ksa.encode()).hexdigest(), "gsa_sha256": hashlib.sha256(gsa.encode()).hexdigest(), "prefixes": prefixes})
            kms_bindings = [binding for binding in kms_iam.get("bindings", []) if isinstance(binding, dict) and binding.get("role") == "roles/cloudkms.cryptoKeyEncrypterDecrypter"]
            if len(kms_bindings) != 1 or len(kms_bindings[0].get("members", [])) != 1:
                raise ValueError("KMS IAM REST response is invalid")
            authoritative_agent = storage_service_account.get("emailAddress")
            kms_agent = str(kms_bindings[0]["members"][0]).removeprefix("serviceAccount:")
            if not isinstance(authoritative_agent, str) or authoritative_agent != kms_agent:
                raise ValueError("Storage service agent REST response is invalid")
            if not isinstance(budget_items, list) or len(budget_items) != 1 or not isinstance(budget_items[0], dict):
                raise ValueError("budget REST response is invalid")
            budget = budget_items[0]
            amount, budget_filter = budget.get("amount", {}).get("specifiedAmount", {}), budget.get("budgetFilter", {})
            filter_projects = budget_filter.get("projects") if isinstance(budget_filter, dict) else None
            updates = budget.get("allUpdatesRule")
            notification_channels = updates.get("monitoringNotificationChannels") if isinstance(updates, dict) else None
            project_filter_matches = filter_projects == [f"projects/{project_number}"]
            notification_matches = notification_channels == [operator.get("budget_notification_target")]
            if not project_filter_matches or not notification_matches:
                raise ValueError("budget REST response is invalid")
            return {
                "project_alias_sha256": hashlib.sha256(project.encode()).hexdigest(), "project_number_sha256": hashlib.sha256(project_number.encode()).hexdigest(),
                "cluster": {"name": str(cluster.get("name", "")).rsplit("/", 1)[-1], "zone": cluster.get("location"), "workload_pool_sha256": hashlib.sha256(str(cluster.get("workloadIdentityConfig", {}).get("workloadPool", "")).encode()).hexdigest()},
                "node_pools": sorted(pool_facts, key=lambda item: str(item["name"])), "registries": registries,
                "bucket": {"name_sha256": hashlib.sha256(bucket_name.encode()).hexdigest(), "location": bucket.get("location"), "cmek_sha256": hashlib.sha256(str(bucket.get("encryption", {}).get("defaultKmsKeyName", "")).encode()).hexdigest(), "lifecycle": rules, "uniform_access": bucket.get("iamConfiguration", {}).get("uniformBucketLevelAccess", {}).get("enabled") is True},
                "kms": {"key_sha256": hashlib.sha256(str(kms.get("name", "")).encode()).hexdigest(), "rotation_seconds": int(str(kms.get("rotationPeriod", "0s")).removesuffix("s")), "gcs_service_agent_sha256": hashlib.sha256(authoritative_agent.encode()).hexdigest(), "gcs_role": kms_bindings[0]["role"]},
                "workload_identity": sorted(workload_identity, key=lambda item: str(item["workload"])), "prefix_iam": sorted(prefix_iam, key=lambda item: str(item["prefix"])),
                "budget": {"currency": amount.get("currencyCode"), "amount_vnd": int(amount.get("units", 0)), "trial_credit_vnd": int(operator["trial_credit_vnd"]), "normalized_usd": 240, "thresholds": sorted(rule.get("thresholdPercent") for rule in budget.get("thresholdRules", []) if isinstance(rule, dict)), "project_number_sha256": hashlib.sha256(project_number.encode()).hexdigest(), "project_number_filter_matches": True, "notification_channel_sha256": hashlib.sha256(str(operator["budget_notification_target"]).encode()).hexdigest(), "notification_channel_matches": True},
                "backend": {"bucket_sha256": hashlib.sha256(backend_values["bucket"].encode()).hexdigest(), "prefix_sha256": hashlib.sha256(backend_values["prefix"].encode()).hexdigest(), "remote_state_present": [item.get("name") for item in backend_items] == [f"{backend_values['prefix']}/default.tfstate"]},
                "forwarding_rules": forwarding_rules,
            }
        finally:
            token = ""
            outputs = {}


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"Topic 22 {label} fingerprint is invalid")
    return value


def sanitize_apply_inventory(payload: object, *, revision: str | None = None) -> dict[str, object]:
    """Validate exact typed live facts and emit only sanitized readback evidence."""
    if not isinstance(payload, dict):
        raise ValueError("apply inventory is unsafe")
    required_foundation = {"project_alias_sha256", "project_number_sha256", "cluster", "node_pools", "registries", "bucket", "kms", "workload_identity", "prefix_iam", "budget", "backend", "forwarding_rules"}
    if set(payload) != required_foundation:
        raise ValueError("foundation inventory is incomplete")
    revision = payload.get("revision") if revision is None else revision
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("apply inventory revision is invalid")
    project_alias = _digest(payload.get("project_alias_sha256"), "project alias")
    project_number = _digest(payload.get("project_number_sha256"), "project number")
    cluster = payload.get("cluster")
    if not isinstance(cluster, dict) or set(cluster) != {"name", "zone", "workload_pool_sha256"} or cluster.get("name") != "edai2" or cluster.get("zone") != "us-central1-a":
        raise ValueError("cluster inventory is invalid")
    workload_pool = _digest(cluster.get("workload_pool_sha256"), "workload pool")
    expected_pools = [{"name": "platform", "machine_type": "e2-highmem-4", "spot": False, "min": 0, "max": 1, "current": 0}, {"name": "spot", "machine_type": "e2-standard-8", "spot": True, "min": 0, "max": 2, "current": 0}]
    if payload.get("node_pools") != expected_pools or any(set(item) != {"name", "machine_type", "spot", "min", "max", "current"} for item in payload["node_pools"]):
        raise ValueError("node pool inventory is invalid")
    expected_registries = {"edai2-rag-index", "edai2-retrieval-agent", "edai2-drift-agent", "edai2-coordinator", "edai2-feast-offline-writer", "edai2-feast-online-writer"}
    registries = payload.get("registries")
    if not isinstance(registries, list) or len(registries) != len(expected_registries) or any(not isinstance(item, dict) or set(item) != {"name", "format", "location"} for item in registries) or {item["name"] for item in registries} != expected_registries or any(item["format"] != "DOCKER" or item["location"] != "us-central1" for item in registries):
        raise ValueError("registry inventory is invalid")
    bucket = payload.get("bucket")
    lifecycle = {"7": ["agent-substrate/", "langfuse-events/"], "90": ["airflow-logs/", "backups/", "model-cache/"]}
    if not isinstance(bucket, dict) or set(bucket) != {"name_sha256", "location", "cmek_sha256", "lifecycle", "uniform_access"} or bucket.get("location") != "US-CENTRAL1" or bucket.get("uniform_access") is not True or bucket.get("lifecycle") != lifecycle:
        raise ValueError("bucket inventory is invalid")
    bucket_name, cmek = _digest(bucket.get("name_sha256"), "bucket"), _digest(bucket.get("cmek_sha256"), "CMEK")
    kms = payload.get("kms")
    if not isinstance(kms, dict) or set(kms) != {"key_sha256", "rotation_seconds", "gcs_service_agent_sha256", "gcs_role"} or _digest(kms.get("key_sha256"), "KMS key") != cmek or kms.get("rotation_seconds") != 7_776_000 or kms.get("gcs_role") != "roles/cloudkms.cryptoKeyEncrypterDecrypter":
        raise ValueError("KMS inventory is invalid")
    _digest(kms.get("gcs_service_agent_sha256"), "GCS service agent")
    wi = payload.get("workload_identity")
    expected_ksas = {"retrieval": ("edai2-retrieval-agent", ["model-cache/"]), "drift": ("edai2-drift-agent", ["langfuse-events/"]), "coordinator": ("edai2-coordinator", ["agent-substrate/", "backups/"]), "workers": ("edai2-worker", ["airflow-logs/"])}
    if not isinstance(wi, list) or len(wi) != 4:
        raise ValueError("workload identity inventory is invalid")
    gsa_by_workload: dict[str, str] = {}
    for binding in wi:
        if not isinstance(binding, dict) or set(binding) != {"workload", "ksa", "ksa_member_sha256", "gsa_sha256", "prefixes"}:
            raise ValueError("workload identity inventory is invalid")
        workload = binding.get("workload")
        if workload not in expected_ksas or (binding.get("ksa"), binding.get("prefixes")) != expected_ksas[workload]:
            raise ValueError("workload identity inventory is invalid")
        _digest(binding.get("ksa_member_sha256"), "KSA member")
        gsa_by_workload[str(workload)] = _digest(binding.get("gsa_sha256"), "GSA")
    prefix_iam = payload.get("prefix_iam")
    expected_prefix_gsa = {prefix: gsa_by_workload[workload] for workload, (_ksa, prefixes) in expected_ksas.items() for prefix in prefixes}
    if not isinstance(prefix_iam, list) or len(prefix_iam) != 5:
        raise ValueError("prefix IAM inventory is invalid")
    for entry in prefix_iam:
        if not isinstance(entry, dict) or set(entry) != {"prefix", "gsa_sha256", "role"} or entry.get("role") != "roles/storage.objectUser" or expected_prefix_gsa.get(entry.get("prefix")) != entry.get("gsa_sha256"):
            raise ValueError("prefix IAM inventory is invalid")
    if {entry["prefix"] for entry in prefix_iam} != set(expected_prefix_gsa):
        raise ValueError("prefix IAM inventory is invalid")
    budget = payload.get("budget")
    if not isinstance(budget, dict) or set(budget) != {"currency", "amount_vnd", "trial_credit_vnd", "normalized_usd", "thresholds", "project_number_sha256", "project_number_filter_matches", "notification_channel_sha256", "notification_channel_matches"} or budget.get("currency") != "VND" or budget.get("amount_vnd") != math.floor(budget.get("trial_credit_vnd", 0) * 240 / 300) or budget.get("normalized_usd") != 240 or budget.get("thresholds") != [0.5, 0.75, 0.9, 1.0] or budget.get("project_number_sha256") != project_number or budget.get("project_number_filter_matches") is not True or budget.get("notification_channel_matches") is not True:
        raise ValueError("budget inventory is invalid")
    _digest(budget.get("notification_channel_sha256"), "budget notification channel")
    backend = payload.get("backend")
    if not isinstance(backend, dict) or set(backend) != {"bucket_sha256", "prefix_sha256", "remote_state_present"} or backend.get("remote_state_present") is not True:
        raise ValueError("backend inventory is invalid")
    _digest(backend.get("bucket_sha256"), "backend bucket")
    _digest(backend.get("prefix_sha256"), "backend prefix")
    forwarding_rules = payload.get("forwarding_rules")
    if not isinstance(forwarding_rules, list) or forwarding_rules:
        raise ValueError("Topic 22 inventory must contain zero forwarding rules")
    return {
        "schema_version": 2, "result": "successful", "revision": revision,
        "zone": "us-central1-a", "project_alias_sha256": project_alias,
        "project_number_sha256": project_number,
        "cluster": {"name": "edai2", "zone": "us-central1-a", "workload_pool_sha256": workload_pool},
        "node_pools": expected_pools,
        "registries": sorted(registries, key=lambda item: str(item["name"])),
        "bucket": dict(bucket), "kms": dict(kms),
        "workload_identity": sorted(wi, key=lambda item: str(item["workload"])),
        "prefix_iam": sorted(prefix_iam, key=lambda item: str(item["prefix"])),
        "budget": dict(budget), "backend": dict(backend), "forwarding_rule_count": 0,
    }


def reduce_topic22_readbacks(readbacks: object, *, revision: str | None = None) -> dict[str, object]:
    """Reduce only the production adapter's exact typed/fingerprinted schema."""
    return sanitize_apply_inventory(readbacks, revision=revision)


_SANITIZED_APPLY_BINDINGS = {"plan_sha256", "forecast_sha256", "approval_record_sha256"}


def validate_sanitized_apply_evidence(payload: object) -> dict[str, object]:
    """Validate the single machine-evidence schema consumed by rendering and verification."""
    if not isinstance(payload, dict) or not _SANITIZED_APPLY_BINDINGS.issubset(payload):
        raise ValueError("sanitized apply evidence is incomplete")
    for name in _SANITIZED_APPLY_BINDINGS:
        _digest(payload.get(name), name.replace("_", " "))
    base = {key: value for key, value in payload.items() if key not in _SANITIZED_APPLY_BINDINGS}
    expected_keys = {
        "schema_version", "result", "revision", "zone", "project_alias_sha256",
        "project_number_sha256", "cluster", "node_pools", "registries", "bucket", "kms",
        "workload_identity", "prefix_iam", "budget", "backend", "forwarding_rule_count",
    }
    if set(base) != expected_keys or base.get("schema_version") != 2 or base.get("result") != "successful" or base.get("forwarding_rule_count") != 0:
        raise ValueError("sanitized apply evidence schema is invalid")
    raw = {key: base[key] for key in ("project_alias_sha256", "project_number_sha256", "cluster", "node_pools", "registries", "bucket", "kms", "workload_identity", "prefix_iam", "budget", "backend")}
    raw["forwarding_rules"] = []
    if sanitize_apply_inventory(raw, revision=str(base["revision"])) != base:
        raise ValueError("sanitized apply evidence facts are invalid")
    return payload


def _authorization_bindings(path: Path, revision: str, *, operator: dict[str, object] | None = None, workspace: Path | None = None) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {"schema_version", "result", "managed_resource_count", "data_read_count", "resource_types", "invariants", "principal_fingerprints", "plan_sha256", "forecast_sha256", "revision"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != 2 or payload.get("result") != "approved-for-operator-review" or payload.get("revision") != revision or _has_secret(payload):
        raise ValueError("Terraform authorization evidence is invalid")
    bindings = {
        "plan_sha256": _digest(payload.get("plan_sha256"), "approved plan"),
        "forecast_sha256": _digest(payload.get("forecast_sha256"), "forecast evidence"),
    }
    if operator is None or workspace is None:
        return {**bindings, "approval_record_sha256": hash_file(path)}
    paths = operator.get("resolved_paths") if isinstance(operator, dict) else None
    data_dir = paths.get("tf_data_dir") if isinstance(paths, dict) else None
    if not isinstance(data_dir, Path):
        raise ValueError("private Terraform approval is invalid")
    try:
        approval = json.loads((data_dir / "topic22-approval.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("private Terraform approval is invalid") from error
    forecast = workspace / "evidence" / "04_2_llm_design" / "gke" / "cost_forecast_topic22.json"
    plan = data_dir / "topic22.tfplan"
    if not isinstance(approval, dict) or set(approval) != {"operator_approved", "plan_sha256", "forecast_sha256", "revision"} or approval.get("operator_approved") is not True or not plan.is_file() or not forecast.is_file() or approval.get("revision") != revision or approval.get("plan_sha256") != bindings["plan_sha256"] or approval.get("forecast_sha256") != bindings["forecast_sha256"] or hash_file(plan) != bindings["plan_sha256"] or hash_file(forecast) != bindings["forecast_sha256"]:
        raise ValueError("private Terraform approval is invalid")
    return {**bindings, "approval_record_sha256": hash_file(data_dir / "topic22-approval.json")}


def run_topic22_cli(
    arguments: list[str] | None = None,
    *,
    terraform_runner: Callable[[list[str]], str] | None = None,
    inventory_adapter_factory: Callable[[], Topic22InventoryAdapter] | None = None,
    revision: str | None = None,
    operator_loader: Callable[[str | Path, Path], dict[str, object]] | None = None,
    billing_writer_factory: Callable[[dict[str, object]], Callable[[Path], None]] | None = None,
    workspace: Path | None = None,
) -> int:
    """Run Topic 22 evidence operations; every durable result is sanitized and atomic."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", choices=("billing", "terraform-apply"))
    parser.add_argument("--url")
    parser.add_argument("--viewport")
    parser.add_argument("--output")
    parser.add_argument("--manifest")
    parser.add_argument("--machine-evidence")
    parser.add_argument("--private-plan-sanitize", action="store_true")
    parser.add_argument("--forecast-evidence")
    parser.add_argument("--revision")
    parser.add_argument("--require-resources")
    parser.add_argument("--forbid-resources")
    parser.add_argument("--browser-storage-state")
    parser.add_argument("--terraform-inventory", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--zone")
    parser.add_argument("--operator-inputs")
    parser.add_argument("--authorization-evidence")
    parser.add_argument("--render-sanitized-terraform")
    parser.add_argument("--verify-screenshots")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(arguments)
    if not args.strict:
        raise ValueError("Topic 22 evidence requires --strict")
    if args.private_plan_sanitize:
        if not args.operator_inputs or not args.output or any((args.forecast_evidence, args.revision, args.require_resources, args.forbid_resources)):
            raise ValueError("private Terraform sanitizer requires only private bundle and output")
        sanitize_private_terraform_plan(Path(args.operator_inputs), Path(args.output), workspace=workspace or Path.cwd(), operator_loader=operator_loader or load_topic22_operator_inputs, revision=revision)
        return 0
    if args.terraform_inventory:
        if not all((args.operator_inputs, args.authorization_evidence, args.output)) or any((args.project, args.zone)):
            raise ValueError("private inventory inputs, authorization evidence, and output are mandatory")
        adapter = inventory_adapter_factory() if inventory_adapter_factory is not None else GcloudRestTopic22InventoryAdapter()
        operator = (operator_loader or load_topic22_operator_inputs)(args.operator_inputs, workspace or Path.cwd())
        raw_readback = adapter.read(Path(args.operator_inputs))
        try:
            current_revision = revision or _revision()
            sanitized = reduce_topic22_readbacks(raw_readback, revision=current_revision)
            sanitized.update(_authorization_bindings(Path(args.authorization_evidence), current_revision, operator=operator, workspace=workspace or Path.cwd()))
            validate_sanitized_apply_evidence(sanitized)
        finally:
            raw_readback = {}
        _atomic_new_json(Path(args.output), sanitized)
        return 0
    if args.verify_screenshots:
        if not args.manifest:
            raise ValueError("screenshot manifest is mandatory")
        root = Path(args.manifest).parent
        verify_topic22_screenshots(Path(args.manifest), root, args.verify_screenshots.split(","), workspace=workspace)
        return 0
    if args.capture or args.render_sanitized_terraform:
        if not all((args.output, args.manifest, args.machine_evidence)):
            raise ValueError("capture output, manifest, and machine evidence are mandatory")
        if args.viewport and args.viewport != "1600x1000":
            raise ValueError("Topic 22 capture viewport must be 1600x1000")
        machine_path = Path(args.machine_evidence)
        payload = json.loads(machine_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or _has_secret(payload):
            raise ValueError("machine evidence is unsafe")
        if args.render_sanitized_terraform:
            if Path(args.render_sanitized_terraform).resolve() != machine_path.resolve():
                raise ValueError("rendered Terraform source must match linked machine evidence")
            validate_sanitized_apply_evidence(payload)
        final_path = Path(args.output)
        root = Path(args.manifest).parent
        current_revision = revision or (payload.get("revision") if args.render_sanitized_terraform else _revision())
        if not isinstance(current_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", current_revision):
            raise ValueError("capture revision is invalid")
        if args.capture == "billing":
            if args.url:
                raise ValueError("raw billing URL is forbidden on argv; use the private operator bundle")
            if not args.operator_inputs:
                raise ValueError("private billing operator inputs are mandatory")
            operator = (operator_loader or load_topic22_operator_inputs)(args.operator_inputs, Path.cwd())
            writer = (billing_writer_factory or billing_writer_from_operator)(operator)
            source, filename = f"https://console.google.com/url-sha256/{hashlib.sha256(operator['billing_console_url'].encode()).hexdigest()}", "gcp_billing_spend.png"
            proves, limitation = "A fresh redacted billing spend observation is visible.", "It does not prove future spend remains within the cap."
        else:
            writer = lambda destination: render_topic22_png(payload, destination, machine_path=machine_path)
            source, filename = "https://evidence.local/terraform-apply", "terraform_apply.png"
            proves, limitation = "A sanitized successful Terraform apply inventory is visible.", "It does not prove Kubernetes workloads are ready."
        if final_path.name != filename:
            raise ValueError("capture output filename is invalid")
        record_capture(final_path=final_path, root=root, writer=writer, source=source, revision=current_revision, visible_selectors=REQUIRED_VIEWS[filename], machine_evidence=[args.machine_evidence], proves=proves, does_not_prove=limitation, manifest_path=Path(args.manifest), workspace=workspace)
        return 0
    raise ValueError("one Topic 22 operation is required")


def main() -> int:
    topic22_flags = {
        "--capture", "--private-plan-sanitize", "--terraform-inventory",
        "--render-sanitized-terraform", "--verify-screenshots",
    }
    if topic22_flags & set(sys.argv[1:]):
        try:
            return run_topic22_cli(sys.argv[1:])
        except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError):
            raise SystemExit("TOPIC22_EVIDENCE_ERROR") from None
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-observability-contract", action="store_true")
    parser.add_argument("--kubeconfig")
    parser.add_argument("--context")
    parser.add_argument("--platform-inventory")
    parser.add_argument("--inventory-signature")
    parser.add_argument("--private-endpoint-key")
    parser.add_argument("--loopback-only", action="store_true")
    parser.add_argument("--tunnel-ttl")
    parser.add_argument("--local-port", type=int)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if not args.verify_observability_contract or not args.strict:
        parser.error("local verification requires --verify-observability-contract --strict; live capture is GCP-owned")
    supplied = (args.kubeconfig, args.context, args.platform_inventory, args.inventory_signature, args.private_endpoint_key, args.tunnel_ttl, args.local_port)
    if any(value is not None for value in supplied) or args.loopback_only:
        if not all(value is not None for value in supplied) or not args.loopback_only:
            parser.error("private capture inputs must be complete and loopback-only")
        _validate_gke_target(Path(args.kubeconfig), args.context)
        _validate_tunnel_ttl(args.tunnel_ttl)
        if not 1024 < args.local_port <= 65535:
            parser.error("--local-port must be an ephemeral non-privileged port")
        try:
            validate_private_endpoint(json.loads(Path(args.platform_inventory).read_text(encoding="utf-8")), args.private_endpoint_key, args.inventory_signature)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            parser.error(str(error))
    print(json.dumps({"locked_views": len(REQUIRED_VIEWS), "manifest_fields": list(MANIFEST_FIELDS), "live_capture": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
