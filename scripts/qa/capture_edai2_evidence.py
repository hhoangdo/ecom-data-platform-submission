"""Fail-closed local screenshot contracts; no browser, Kubernetes, or tunnel is started here."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import yaml
from PIL import Image


MANIFEST_FIELDS = ("path", "width", "height", "captured_at_utc", "url_or_source", "commit_or_revision", "visible_selectors", "linked_machine_evidence", "sha256", "proves", "does_not_prove")
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
_BAD_PAGE = re.compile(r"(?i)(loading|spinner|login|sign[ -]?in|error|generic|terminal)")


def _canonical_inventory(inventory: dict[str, object]) -> bytes:
    return json.dumps(inventory, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def inventory_signature(inventory: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_inventory(inventory)).hexdigest()


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


def _validate_existing_manifest(manifest_path: Path, root: Path, revision: str) -> list[dict[str, object]]:
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
        _validate_existing_entry(entry, root, revision)
    return entries


def _validate_existing_entry(entry: dict[str, object], root: Path, revision: str) -> None:
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
        if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
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


def record_capture(*, final_path: Path, root: Path, writer: Callable[[Path], None], source: str, revision: str, visible_selectors: list[str], machine_evidence: list[str], proves: str, does_not_prove: str, manifest_path: Path, replace: Callable[[Path, Path], None] = os.replace) -> dict[str, object]:
    root, final_path, manifest_path = root.resolve(), final_path.resolve(), manifest_path.resolve()
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
        entry = {"path": final_path.relative_to(root).as_posix(), "width": width, "height": height, "captured_at_utc": datetime.now(UTC).isoformat(), "url_or_source": source, "commit_or_revision": revision, "visible_selectors": visible_selectors, "linked_machine_evidence": machine_evidence, "sha256": digest, "proves": proves, "does_not_prove": does_not_prove}
        existing = _validate_existing_manifest(manifest_path, root, revision)
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


def main() -> int:
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
