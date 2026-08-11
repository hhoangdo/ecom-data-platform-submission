from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import pytest
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]


def _load_capture_module():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location("capture_edai2_evidence", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_required_views_are_exactly_the_locked_inventory() -> None:
    """Renaming, dropping, or adding a required capture breaks later evidence binding."""
    capture = _load_capture_module()
    assert len(capture.REQUIRED_VIEWS) == 32
    assert set(capture.REQUIRED_VIEWS) == set(capture.LOCKED_FILENAMES)
    assert capture.REQUIRED_VIEWS["grafana_http.png"] == ["Grafana title", "dashboard EDAI2 HTTP", "RPS/count/failure panels", "time range"]
    assert capture.REQUIRED_VIEWS["tempo_trace.png"][-1] == "gateway/coordinator/specialist/MCP dependency chain"


def test_record_capture_validates_decodes_and_atomically_replaces(tmp_path: Path) -> None:
    """A truncated or wrong-size capture must never replace the final evidence path."""
    capture = _load_capture_module()
    final = tmp_path / "grafana_http.png"
    manifest = tmp_path / "ui_manifest.json"

    def writer(path: Path) -> None:
        image = Image.new("RGB", (1600, 1000), color=(24, 80, 160))
        ImageDraw.Draw(image).rectangle((100, 100, 500, 300), fill=(240, 180, 40))
        image.save(path, "PNG")

    entry = capture.record_capture(
        final_path=final, root=tmp_path, writer=writer, source="https://grafana.example.test",
        revision="a" * 40, visible_selectors=capture.REQUIRED_VIEWS["grafana_http.png"],
        machine_evidence=["evidence/telemetry.json"], proves="Grafana HTTP dashboard context is visible.",
        does_not_prove="It does not prove live alert firing.", manifest_path=manifest,
    )
    assert final.is_file() and entry["sha256"] == hashlib.sha256(final.read_bytes()).hexdigest()
    assert set(entry) == set(capture.MANIFEST_FIELDS)
    assert json.loads(manifest.read_text(encoding="utf-8"))[0]["path"] == "grafana_http.png"


def test_private_endpoint_validation_rejects_unknown_key_and_non_loopback(tmp_path: Path) -> None:
    """A stale inventory or non-loopback tunnel could expose a private UI."""
    capture = _load_capture_module()
    inventory = {"private_endpoints": {key: {"namespace": "edai2", "service_name": key, "service_uid": key + "-uid", "service_port": 80, "target_port": 8080, "selector_sha256": "a" * 64, "ready_endpoint_uids": [key + "-endpoint"]} for key in capture.PRIVATE_ENDPOINT_KEYS}}
    signature = capture.inventory_signature(inventory)
    with pytest.raises(ValueError, match="unknown private endpoint"):
        capture.validate_private_endpoint(inventory, "unknown", signature)
    with pytest.raises(ValueError, match="loopback"):
        capture.build_port_forward_command(Path("C:/absolute/kubeconfig"), "gke_expected", "edai2", "grafana", 3000, 80, "0.0.0.0")
    assert capture.validate_private_endpoint(inventory, "grafana_ui", signature)["service_uid"] == "grafana_ui-uid"


def test_private_lifecycle_uses_exact_child_and_cleans_owned_runtime_files(tmp_path: Path) -> None:
    """A capture child must be cleaned after success and never start before readback passes."""
    capture = _load_capture_module()
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    entry = {"namespace": "edai2", "service_name": "grafana", "service_uid": "service-uid", "service_port": 80, "target_port": 3000, "selector_sha256": "a" * 64, "ready_endpoint_uids": ["endpoint-uid"]}
    inventory = {"private_endpoints": {key: entry | {"service_name": key} for key in capture.PRIVATE_ENDPOINT_KEYS}}
    signature = capture.inventory_signature(inventory)
    observed = entry | {"service_name": "grafana_ui"}

    class Process:
        pid = 4242
        terminated = False
        def terminate(self): self.terminated = True
        def wait(self, timeout): assert timeout == 5
        def poll(self): return 0 if self.terminated else None

    process = Process()
    result = capture.run_private_capture(
        kubeconfig=kubeconfig, context="gke_expected", inventory=inventory, key="grafana_ui",
        inventory_signature=signature, observed=observed, loopback_only=True, tunnel_ttl="10m", runtime_root=tmp_path / "runtime",
        reserve_port=lambda: 40123, process_factory=lambda command, stdout, stderr: process, readiness=lambda: None, capture_callback=lambda _: "ok",
    )
    assert result == "ok" and process.terminated
    assert not (tmp_path / "runtime").exists()
    with pytest.raises(ValueError, match="readback"):
        capture.run_private_capture(
            kubeconfig=kubeconfig, context="gke_expected", inventory=inventory, key="grafana_ui",
            inventory_signature=signature, observed=observed | {"service_uid": "wrong"}, loopback_only=True, tunnel_ttl="10m",
            runtime_root=tmp_path / "blocked", reserve_port=lambda: 40123, process_factory=lambda *_: pytest.fail("child started"),
            readiness=lambda: None, capture_callback=lambda _: "never",
        )


def test_failed_manifest_validation_preserves_existing_final_and_manifest(tmp_path: Path) -> None:
    """A duplicate hash must not publish a replacement PNG before manifest validation succeeds."""
    capture = _load_capture_module()
    final = tmp_path / "grafana_http.png"
    final.write_bytes(b"old-final")
    manifest = tmp_path / "ui_manifest.json"
    manifest.write_text(json.dumps([{"path": "other.png", "sha256": "x" * 64}]), encoding="utf-8")
    before_final, before_manifest = final.read_bytes(), manifest.read_bytes()
    with pytest.raises(ValueError, match="manifest"):
        capture.record_capture(
            final_path=final, root=tmp_path, writer=lambda path: Image.effect_noise((1600, 1000), 100).save(path, "PNG"),
            source="https://grafana.example.test", revision="a" * 40,
            visible_selectors=capture.REQUIRED_VIEWS["grafana_http.png"], machine_evidence=["evidence/telemetry.json"],
            proves="Grafana context is visible.", does_not_prove="No live alert proof.", manifest_path=manifest,
        )
    assert final.read_bytes() == before_final and manifest.read_bytes() == before_manifest
    assert not list(tmp_path.glob(".*.tmp*"))


def test_live_capture_is_skipped_without_an_authorized_route(pytestconfig: pytest.Config) -> None:
    """A local test run must not invent a browser capture when no GKE route is authorized."""
    if not pytestconfig.getoption("live_gke"):
        pytest.skip("missing authorized live GKE base URL")


def _signed_inventory(capture, entry: dict[str, object]) -> tuple[dict[str, object], str]:
    inventory = {"private_endpoints": {key: entry | {"service_name": key} for key in capture.PRIVATE_ENDPOINT_KEYS}}
    return inventory, capture.inventory_signature(inventory)


def test_locked_view_anchor_table_is_literal_and_complete() -> None:
    """Any abbreviated anchor permits a context-free substitute screenshot."""
    capture = _load_capture_module()
    assert capture.REQUIRED_VIEWS == {
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


def test_signed_inventory_rejections_happen_before_private_child_creation(tmp_path: Path) -> None:
    """Tampering inventory identity or readback metadata must not open a tunnel."""
    capture = _load_capture_module()
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    entry = {"namespace": "edai2", "service_name": "grafana", "service_uid": "service-uid", "service_port": 8080, "target_port": 3000, "selector_sha256": "a" * 64, "ready_endpoint_uids": ["endpoint-uid"]}
    inventory, signature = _signed_inventory(capture, entry)
    observed = entry | {"service_name": "grafana_ui"}
    bad_cases = [
        (inventory | {"extra": True}, signature),
        (inventory, "0" * 64),
        ({"private_endpoints": {key: value for key, value in inventory["private_endpoints"].items() if key != "vault_status"}}, signature),
        ({"private_endpoints": {key: value | ({"service_uid": ""} if key == "grafana_ui" else {}) for key, value in inventory["private_endpoints"].items()}}, signature),
    ]
    for bad_inventory, bad_signature in bad_cases:
        with pytest.raises(ValueError):
            capture.run_private_capture(kubeconfig=kubeconfig, context="gke_expected", inventory=bad_inventory,
                inventory_signature=bad_signature, key="grafana_ui", observed=observed, loopback_only=True,
                tunnel_ttl="10m", runtime_root=tmp_path / f"blocked-{len(str(bad_inventory))}",
                reserve_port=lambda: 40123, process_factory=lambda *_: pytest.fail("child started"),
                readiness=lambda: None, capture_callback=lambda _: "never")
    for field, wrong in [("service_uid", "wrong"), ("service_port", 81), ("target_port", 81), ("selector_sha256", "b" * 64), ("ready_endpoint_uids", ["wrong"])]:
        with pytest.raises(ValueError, match="readback"):
            capture.run_private_capture(kubeconfig=kubeconfig, context="gke_expected", inventory=inventory,
                inventory_signature=signature, key="grafana_ui", observed=observed | {field: wrong}, loopback_only=True,
                tunnel_ttl="10m", runtime_root=tmp_path / f"bad-{field}", reserve_port=lambda: 40123,
                process_factory=lambda *_: pytest.fail("child started"), readiness=lambda: None, capture_callback=lambda _: "never")


def test_every_signed_inventory_entry_is_validated_before_port_reservation(tmp_path: Path) -> None:
    """A malformed non-selected endpoint must not be smuggled through a valid selected entry."""
    capture = _load_capture_module()
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    entry = {"namespace": "edai2", "service_name": "grafana", "service_uid": "service-uid", "service_port": 8080, "target_port": 3000, "selector_sha256": "a" * 64, "ready_endpoint_uids": ["endpoint-uid"]}
    inventory, _ = _signed_inventory(capture, entry)
    observed = entry | {"service_name": "grafana_ui"}
    mutations = [
        {"service_uid": ""}, {"service_port": 0}, {"selector_sha256": "not-a-hash"}, {"ready_endpoint_uids": []},
    ]
    for mutation in mutations:
        altered = {"private_endpoints": {key: value | (mutation if key == "vault_status" else {}) for key, value in inventory["private_endpoints"].items()}}
        reserve_calls: list[bool] = []
        with pytest.raises(ValueError, match="inventory entry"):
            capture.run_private_capture(kubeconfig=kubeconfig, context="gke_expected", inventory=altered,
                inventory_signature=capture.inventory_signature(altered), key="grafana_ui", observed=observed,
                loopback_only=True, tunnel_ttl="10m", runtime_root=tmp_path / "blocked-all-entry",
                reserve_port=lambda: reserve_calls.append(True) or 40123,
                process_factory=lambda *_: pytest.fail("child started"), readiness=lambda: None, capture_callback=lambda _: "never")
        assert reserve_calls == []


def test_private_lifecycle_matrix_always_releases_the_exact_child(tmp_path: Path) -> None:
    """Every post-start failure must terminate, wait, poll, and remove only owned runtime files."""
    capture = _load_capture_module()
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    entry = {"namespace": "edai2", "service_name": "grafana", "service_uid": "service-uid", "service_port": 8080, "target_port": 3000, "selector_sha256": "a" * 64, "ready_endpoint_uids": ["endpoint-uid"]}
    inventory, signature = _signed_inventory(capture, entry)
    observed = entry | {"service_name": "grafana_ui"}

    class Process:
        pid = 4242
        def __init__(self, start_error: Exception | None = None, cleanup_error: Exception | None = None, wait_error: Exception | None = None, leaked: bool = False):
            self.calls: list[str] = []
            self.start_error, self.cleanup_error, self.wait_error, self.leaked = start_error, cleanup_error, wait_error, leaked
        def start(self):
            self.calls.append("start")
            if self.start_error: raise self.start_error
        def terminate(self):
            self.calls.append("terminate")
            if self.cleanup_error: raise self.cleanup_error
        def wait(self, timeout):
            assert timeout == 5; self.calls.append("wait")
            if self.wait_error: raise self.wait_error
        def poll(self):
            self.calls.append("poll"); return None if self.leaked else 0

    failures: list[tuple[str, Callable[[], object], Callable[[], object], Process | None]] = [
        ("readiness", lambda: (_ for _ in ()).throw(TimeoutError("timeout")), lambda: "never", Process()),
        ("capture", lambda: None, lambda: (_ for _ in ()).throw(RuntimeError("browser")), Process()),
        ("interrupt", lambda: (_ for _ in ()).throw(KeyboardInterrupt()), lambda: "never", Process()),
        ("start", lambda: None, lambda: "never", Process(start_error=RuntimeError("start"))),
        ("wait", lambda: None, lambda: "ok", Process(wait_error=RuntimeError("wait"))),
        ("terminate", lambda: None, lambda: "ok", Process(cleanup_error=RuntimeError("terminate"))),
        ("leak", lambda: None, lambda: "ok", Process(leaked=True)),
    ]
    for name, readiness, callback, process in failures:
        runtime = tmp_path / name
        with pytest.raises(BaseException):
            capture.run_private_capture(kubeconfig=kubeconfig, context="gke_expected", inventory=inventory,
                inventory_signature=signature, key="grafana_ui", observed=observed, loopback_only=True,
                tunnel_ttl="10m", runtime_root=runtime, reserve_port=lambda: 40123,
                process_factory=lambda *_args, p=process: p, readiness=readiness, capture_callback=lambda _: callback())
        assert not runtime.exists()
        assert process is not None and process.calls[-1] == "poll"
        assert "terminate" in process.calls and "wait" in process.calls

    factory_runtime = tmp_path / "factory"
    with pytest.raises(RuntimeError, match="factory"):
        capture.run_private_capture(kubeconfig=kubeconfig, context="gke_expected", inventory=inventory,
            inventory_signature=signature, key="grafana_ui", observed=observed, loopback_only=True,
            tunnel_ttl="10m", runtime_root=factory_runtime, reserve_port=lambda: 40123,
            process_factory=lambda *_: (_ for _ in ()).throw(RuntimeError("factory")), readiness=lambda: None,
            capture_callback=lambda _: "never")
    assert not factory_runtime.exists()


def test_capture_rejection_matrix_preserves_existing_published_bytes(tmp_path: Path) -> None:
    """Invalid metadata, image, manifest, and publish failures cannot replace prior evidence."""
    capture = _load_capture_module()
    final, manifest = tmp_path / "grafana_http.png", tmp_path / "ui_manifest.json"
    final.write_bytes(b"prior-final")
    manifest.write_text("[]", encoding="utf-8")
    before = (final.read_bytes(), manifest.read_bytes())
    def valid_writer(path: Path) -> None:
        image = Image.effect_noise((1600, 1000), 100); image.save(path, "PNG")
    cases = [
        {"source": "http://grafana.example.test"}, {"source": "https://loading.example.test"},
        {"revision": "stale"}, {"visible_selectors": []}, {"machine_evidence": []},
        {"proves": "token=secret"}, {"does_not_prove": "customer_id=1"},
        {"writer": lambda path: path.write_bytes(b"")}, {"writer": lambda path: path.write_bytes(b"not-a-png")},
        {"writer": lambda path: Image.new("RGB", (100, 100)).save(path, "PNG")},
        {"writer": lambda path: Image.new("RGB", (1600, 1000)).save(path, "PNG")},
    ]
    for overrides in cases:
        kwargs = {"final_path": final, "root": tmp_path, "writer": valid_writer, "source": "https://grafana.example.test",
            "revision": "a" * 40, "visible_selectors": capture.REQUIRED_VIEWS["grafana_http.png"],
            "machine_evidence": ["evidence/telemetry.json"], "proves": "Dashboard context is visible.",
            "does_not_prove": "Live alert firing is deferred.", "manifest_path": manifest} | overrides
        with pytest.raises((ValueError, OSError)):
            capture.record_capture(**kwargs)
        assert (final.read_bytes(), manifest.read_bytes()) == before
        assert not list(tmp_path.glob(".*.tmp*")) and not list(tmp_path.glob(".*.rollback"))


def test_existing_manifest_entries_are_fully_checked_before_publish(tmp_path: Path) -> None:
    """A valid-looking old manifest entry cannot bypass hash, freshness, revision, path, or anchor checks."""
    capture = _load_capture_module()
    final, manifest, old_png = tmp_path / "grafana_http.png", tmp_path / "ui_manifest.json", tmp_path / "airflow_rag_graph.png"
    final.write_bytes(b"prior-final")
    def writer(path: Path) -> None:
        Image.effect_noise((1600, 1000), 100).save(path, "PNG")
    writer(old_png)
    old_entry = {"path": "airflow_rag_graph.png", "width": 1600, "height": 1000, "captured_at_utc": datetime.now(UTC).isoformat(),
        "url_or_source": "https://airflow.example.test", "commit_or_revision": "a" * 40,
        "visible_selectors": capture.REQUIRED_VIEWS["airflow_rag_graph.png"], "linked_machine_evidence": ["evidence/airflow.json"],
        "sha256": hashlib.sha256(old_png.read_bytes()).hexdigest(), "proves": "Airflow context is visible.", "does_not_prove": "Deployment proof is deferred."}
    mutations = [
        {"sha256": "0" * 64}, {"captured_at_utc": "2000-01-01T00:00:00+00:00"}, {"commit_or_revision": "b" * 40},
        {"path": "missing.png"}, {"visible_selectors": ["wrong"]},
    ]
    for mutation in mutations:
        manifest.write_text(json.dumps([old_entry | mutation]), encoding="utf-8")
        before = (final.read_bytes(), manifest.read_bytes())
        with pytest.raises(ValueError, match="manifest"):
            capture.record_capture(final_path=final, root=tmp_path, writer=writer, source="https://grafana.example.test",
                revision="a" * 40, visible_selectors=capture.REQUIRED_VIEWS["grafana_http.png"],
                machine_evidence=["evidence/grafana.json"], proves="Dashboard context is visible.",
                does_not_prove="Alert proof is deferred.", manifest_path=manifest)
        assert (final.read_bytes(), manifest.read_bytes()) == before
        assert not list(tmp_path.glob(".*.tmp*")) and not list(tmp_path.glob(".*.rollback"))
