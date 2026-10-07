from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load(name: str, relative: str):
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"missing module file: {relative}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_gke_target_accepts_dedicated_renamed_context(tmp_path: Path) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text(
        "contexts: [{name: edai2-gke, context: {cluster: edai2-gke, user: edai2-gke}}]\n",
        encoding="utf-8",
    )
    module._validate_gke_target(kubeconfig, "edai2-gke")  # must not raise


def test_validate_gke_target_still_accepts_native_gke_form(tmp_path: Path) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text(
        "contexts: [{name: gke_test-proj_us-central1-a_edai2, context: {cluster: gke_test-proj_us-central1-a_edai2, user: gke_test-proj_us-central1-a_edai2}}]\n",
        encoding="utf-8",
    )
    module._validate_gke_target(kubeconfig, "gke_test-proj_us-central1-a_edai2")  # must not raise


def test_validate_gke_target_still_rejects_foreign_context(tmp_path: Path) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text(
        "contexts: [{name: corp-prod, context: {cluster: c, user: u}}]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        module._validate_gke_target(kubeconfig, "corp-prod")
    with pytest.raises(ValueError):
        module._validate_gke_target(kubeconfig, "")
    evil = tmp_path / "kubeconfig-evil"
    evil.write_text(
        "contexts: [{name: edai2-gke-evil, context: {cluster: edai2-gke-evil, user: edai2-gke-evil}}]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        module._validate_gke_target(evil, "edai2-gke-evil")


def test_selector_sha256_pins_canonical_form() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    assert module.selector_sha256({"b": "2", "a": "1"}) == module.selector_sha256({"a": "1", "b": "2"})
    assert len(module.selector_sha256({"app": "grafana"})) == 64


def test_load_service_bindings_requires_exact_five_keys(tmp_path: Path) -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    bindings = tmp_path / "bindings.json"
    bindings.write_text(json.dumps({"schema_version": 1, "bindings": {k: {"namespace": "edai2", "service": "svc-" + k} for k in ("agentregistry_ui", "grafana_ui", "airflow_web", "datahub_frontend", "vault_status")}}), encoding="utf-8")
    loaded = module.load_service_bindings(bindings)
    assert set(loaded) == set(module.PRIVATE_ENDPOINT_KEYS)
    bindings.write_text(json.dumps({"schema_version": 1, "bindings": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        module.load_service_bindings(bindings)


def test_build_inventory_reads_service_and_endpointslices() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    service = {"metadata": {"uid": "svc-uid"}, "spec": {"ports": [{"port": 80, "targetPort": 8080}], "selector": {"app": "grafana"}}}
    slices = {"items": [{"ports": [{"name": "http", "port": 8080}], "endpoints": [{"conditions": {"ready": True}, "targetRef": {"uid": "pod-uid-1"}}]}]}
    calls = {"n": 0}
    def runner(args: list[str]) -> dict:
        calls["n"] += 1
        return slices if "endpointslices" in args else service
    inventory = module.build_private_endpoint_inventory({"grafana_ui": {"namespace": "edai2", "service": "edai2-grafana"}}, runner=runner)
    module.verify_private_endpoint_inventory(inventory, ["grafana_ui"])
    entry = inventory["private_endpoints"]["grafana_ui"]
    assert (entry["service_uid"], entry["service_port"], entry["target_port"], entry["ready_endpoint_uids"]) == ("svc-uid", 80, 8080, ["pod-uid-1"])
    assert calls["n"] == 2


def test_build_inventory_fails_closed_on_absent_service() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    def runner(args: list[str]) -> dict:
        raise ValueError("service not found")
    with pytest.raises(ValueError):
        module.build_private_endpoint_inventory({"grafana_ui": {"namespace": "edai2", "service": "missing"}}, runner=runner)


def test_build_inventory_resolves_named_target_port() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    service = {"metadata": {"uid": "svc-uid"}, "spec": {"ports": [{"port": 80, "targetPort": "http"}], "selector": {"app": "grafana"}}}
    slices = {"items": [{"ports": [{"name": "http", "port": 8080}], "endpoints": [{"conditions": {"ready": True}, "targetRef": {"uid": "pod-uid-1"}}]}]}
    def runner(args: list[str]) -> dict:
        return slices if "endpointslices" in args else service
    inventory = module.build_private_endpoint_inventory({"grafana_ui": {"namespace": "edai2", "service": "edai2-grafana"}}, runner=runner)
    module.verify_private_endpoint_inventory(inventory, ["grafana_ui"])
    entry = inventory["private_endpoints"]["grafana_ui"]
    assert entry["target_port"] == 8080


def test_build_inventory_fails_closed_on_unresolvable_named_port() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    service = {"metadata": {"uid": "svc-uid"}, "spec": {"ports": [{"port": 80, "targetPort": "http"}], "selector": {"app": "grafana"}}}
    def runner_empty(args: list[str]) -> dict:
        return {"items": []} if "endpointslices" in args else service
    with pytest.raises(ValueError):
        module.build_private_endpoint_inventory({"grafana_ui": {"namespace": "edai2", "service": "edai2-grafana"}}, runner=runner_empty)
    slices_mismatch = {"items": [{"ports": [{"name": "other", "port": 8080}], "endpoints": [{"conditions": {"ready": True}, "targetRef": {"uid": "pod-uid-1"}}]}]}
    def runner_mismatch(args: list[str]) -> dict:
        return slices_mismatch if "endpointslices" in args else service
    with pytest.raises(ValueError):
        module.build_private_endpoint_inventory({"grafana_ui": {"namespace": "edai2", "service": "edai2-grafana"}}, runner=runner_mismatch)
