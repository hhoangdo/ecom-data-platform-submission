from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def _load_script(relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_labels_alert_alloy_trace_enforce_the_locked_telemetry_contract() -> None:
    """A missing label, alert threshold, scope split, or trace hop is a rubric defect."""
    alerts = yaml.safe_load((ROOT / "infra/observability/prometheus/alerts.yaml").read_text(encoding="utf-8"))
    rules = alerts["spec"]["groups"][0]["rules"]
    assert {rule["alert"] for rule in rules} == {
        "EDAI2ApiToolFailureHigh", "EDAI2RetrievalP95High", "EDAI2ActiveIndexStale",
        "EDAI2MemoryHigh", "EDAI2DiskHigh",
    }
    expressions = "\n".join(rule["expr"] for rule in rules)
    for expected in ("> 0.05", "> 0.75", "> 86400", "> 0.90", "> 0.80"):
        assert expected in expressions
    alloy = (ROOT / "infra/observability/alloy/config.alloy").read_text(encoding="utf-8")
    assert 'log_scope = "application"' in alloy
    assert 'log_scope = "system"' in alloy
    assert "nginx/chat -> facade -> agentgateway -> coordinator" in alloy
    assert "agentgateway -> specialist -> agentgateway -> matching MCP -> retrieval/drift API -> Feast/PostgreSQL" in alloy
    assert "customer_id" not in alloy and "message" not in alloy


def test_stable_labels_alert_fixtures_and_structured_trace_are_exact() -> None:
    """Unknown labels, absent alert transitions, or a second trace root invalidate telemetry evidence."""
    capture = _load_script("scripts/qa/capture_edai2_evidence.py")
    assert capture.STABLE_LABELS == ("service", "route", "agent", "tool", "model_version", "agent_config", "index_version", "status", "safety_action", "log_scope")
    with pytest.raises(ValueError, match="label"):
        capture.validate_labels({"service": "api", "customer_id": "42"})
    assert set(capture.ALERT_FIXTURES) == {"EDAI2ApiToolFailureHigh", "EDAI2RetrievalP95High", "EDAI2ActiveIndexStale", "EDAI2MemoryHigh", "EDAI2DiskHigh"}
    assert all(set(states) == {"pending", "firing"} for states in capture.ALERT_FIXTURES.values())
    capture.validate_trace_fixture(capture.TRACE_FIXTURE)
    bad = [dict(span) for span in capture.TRACE_FIXTURE]
    bad[-1]["parent"] = None
    with pytest.raises(ValueError, match="root"):
        capture.validate_trace_fixture(bad)


def test_observability_contract_validates_all_fixture_values_and_scope_separation() -> None:
    """Changing one pending/firing threshold, parent, dashboard, or log scope must fail closed."""
    capture = _load_script("scripts/qa/capture_edai2_evidence.py")
    capture.validate_observability_contract(ROOT)


def test_dashboards_keep_log_scopes_separate_and_cover_required_panels() -> None:
    """A merged log selector or omitted rubric metric would hide the required signal."""
    dashboards = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (ROOT / "infra/observability/grafana/dashboards").glob("*.json")
    }
    assert set(dashboards) == {"http", "compute", "agents", "llm", "ab"}
    titles = {name: {panel["title"] for panel in item["panels"]} for name, item in dashboards.items()}
    assert {"RPS", "Request count", "Failures"} <= titles["http"]
    assert {"CPU", "RAM", "Disk", "Network"} <= titles["compute"]
    assert {"Agent calls", "MCP calls", "Tool failures"} <= titles["agents"]
    assert {"Input tokens", "Output tokens", "Total tokens", "Generation RTT", "TTFT", "Safety/PII"} <= titles["llm"]
    assert {"Agent arms", "Model arms", "Sample counts", "Quality/latency"} <= titles["ab"]
    log_queries = [target["expr"] for dashboard in dashboards.values() for panel in dashboard["panels"] for target in panel.get("targets", []) if "log_scope" in target.get("expr", "")]
    assert log_queries and all("log_scope=~" not in query for query in log_queries)


def test_ingress_contract_is_temporary_one_replica_and_rate_limited() -> None:
    """A second controller, public default, or wrong rejection code invalidates rate evidence."""
    ingress = yaml.safe_load((ROOT / "infra/ingress/edai2/ingresses.yaml").read_text(encoding="utf-8"))
    docs = [item for item in ingress if item]
    chat = next(item for item in docs if item["metadata"]["name"] == "edai2-chat")
    annotations = chat["metadata"]["annotations"]
    assert annotations["nginx.ingress.kubernetes.io/limit-rps"] == "1"
    assert annotations["nginx.ingress.kubernetes.io/limit-burst-multiplier"] == "5"
    assert "limit-rate-after" not in "\n".join(annotations)
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/ingress-nginx.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((ROOT / "infra/helm/edai2/releases.yaml").read_text(encoding="utf-8"))
    assert values["chartVersion"] == catalog["versions"]["ingress_nginx_chart"] == "4.15.1"
    assert values["controller"]["replicaCount"] == 1
    assert values["controller"]["config"]["limit-req-status-code"] == "429"
    assert values["enabled"] is False
    script = _load_script("scripts/gke/configure_evidence_ingress.py")
    assert script.render_contract(ROOT)["controller_replicas"] == 1


def test_ingress_render_only_rejects_an_unapproved_context(tmp_path: Path) -> None:
    """Falling back to a default Kubernetes context would target the wrong cluster."""
    script = _load_script("scripts/gke/configure_evidence_ingress.py")
    kubeconfig = tmp_path / "config.yaml"
    kubeconfig.write_text("contexts:\n- name: corporate\n", encoding="utf-8")
    with pytest.raises(ValueError, match="render-only"):
        script.validate_target(kubeconfig, "corporate", render_only=True)


def test_ingress_enable_disable_contract_uses_only_explicit_targeted_runner(tmp_path: Path) -> None:
    """Missing route authorization must fail before a runner can apply or delete anything."""
    script = _load_script("scripts/gke/configure_evidence_ingress.py")
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    commands: list[list[str]] = []
    state = {"present": True}
    def runner(command: list[str]) -> dict[str, object]:
        commands.append(command)
        if "clusterissuer" in command:
            return {"metadata": {"name": "edai2-acme-staging"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        if "delete" in command:
            state["present"] = False
        if "ingress" in command and "get" in command:
            if not state["present"]:
                return {"items": []}
            return {"items": [
                {"metadata": {"name": "edai2-retrieval", "labels": {"edai2.route-set": "topic27", "edai2.lease-owner": "owner"}}, "spec": {"rules": [{"host": "retrieval.203.0.113.7.sslip.io"}]}},
                {"metadata": {"name": "edai2-chat", "labels": {"edai2.route-set": "topic27", "edai2.lease-owner": "owner"}}, "spec": {"rules": [{"host": "chat.203.0.113.7.sslip.io"}]}},
            ]}
        if "deployment" in command:
            return {"spec": {"replicas": 1}, "data": {"limit-req-status-code": "429"}}
        return {}
    with pytest.raises(ValueError, match="route set"):
        script.execute_contract(ROOT, mode="enable", kubeconfig=kubeconfig, context="gke_expected", strict=True, route_set="", routes="", ingress_ip="203.0.113.7", hosts="", issuer="acme-staging", lease_owner="owner", ttl="1h", output=tmp_path / "routes.yaml", runner=runner)
    assert commands == []
    result = script.execute_contract(ROOT, mode="enable", kubeconfig=kubeconfig, context="gke_expected", strict=True, route_set="topic27", routes="retrieval,chat", ingress_ip="203.0.113.7", hosts="retrieval=retrieval.203.0.113.7.sslip.io,chat=chat.203.0.113.7.sslip.io", issuer="acme-staging", lease_owner="owner", ttl="1h", output=tmp_path / "routes.yaml", runner=runner)
    assert result["mode"] == "enable" and commands[0][:5] == ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "gke_expected"]
    script.execute_contract(ROOT, mode="disable", kubeconfig=kubeconfig, context="gke_expected", strict=True, route_set="topic27", routes="retrieval,chat", ingress_ip="203.0.113.7", hosts="retrieval=retrieval.203.0.113.7.sslip.io,chat=chat.203.0.113.7.sslip.io", issuer="acme-staging", lease_owner="owner", ttl="1h", output=tmp_path / "routes.yaml", runner=runner)
    assert any("delete" in command for command in commands)


def test_ingress_renders_only_selected_labeled_objects_and_verifies_exact_readback(tmp_path: Path) -> None:
    """Applying an unresolved host or an unowned selector can alter unrelated ingress routes."""
    script = _load_script("scripts/gke/configure_evidence_ingress.py")
    kubeconfig = tmp_path / "gke.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    output = tmp_path / "owned.yaml"
    commands: list[list[str]] = []
    def runner(command: list[str]) -> dict[str, object]:
        commands.append(command)
        if "clusterissuer" in command:
            return {"metadata": {"name": "edai2-acme-staging"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        if "ingress" in command:
            return {"items": [
                {"metadata": {"name": "edai2-chat", "labels": {"edai2.route-set": "topic27", "edai2.lease-owner": "owner"}}, "spec": {"rules": [{"host": "chat.203.0.113.7.sslip.io"}]}},
                {"metadata": {"name": "edai2-retrieval", "labels": {"edai2.route-set": "topic27", "edai2.lease-owner": "owner"}}, "spec": {"rules": [{"host": "retrieval.203.0.113.7.sslip.io"}]}},
            ]}
        return {"spec": {"replicas": 1}, "data": {"limit-req-status-code": "429"}}
    result = script.execute_contract(ROOT, mode="enable", kubeconfig=kubeconfig, context="gke_expected", strict=True,
        route_set="topic27", routes="chat,retrieval", ingress_ip="203.0.113.7",
        hosts="chat=chat.203.0.113.7.sslip.io,retrieval=retrieval.203.0.113.7.sslip.io", issuer="acme-staging",
        lease_owner="owner", ttl="1h", output=output, runner=runner)
    rendered = output.read_text(encoding="utf-8")
    assert result["hosts"] == ["chat.203.0.113.7.sslip.io", "retrieval.203.0.113.7.sslip.io"]
    assert "${" not in rendered and "edai2.route-set: topic27" in rendered and "cert-manager.io/cluster-issuer: acme-staging" in rendered
    assert commands[0][-2:] == ["-f", str(output.with_name("owned.issuer.yaml"))]
    assert commands[2][-2:] == ["-f", str(output)]
    assert all(command[:5] == ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "gke_expected"] for command in commands)
    with pytest.raises(ValueError, match="hosts"):
        script.execute_contract(ROOT, mode="enable", kubeconfig=kubeconfig, context="gke_expected", strict=True,
            route_set="topic27", routes="chat,retrieval", ingress_ip="203.0.113.7", hosts="chat=bad.example.test",
            issuer="acme-staging", lease_owner="owner", ttl="1h", output=tmp_path / "bad.yaml", runner=lambda _: pytest.fail("runner used"))


def test_ingress_applies_only_selected_ready_issuer_before_owned_routes(tmp_path: Path) -> None:
    """Route apply before a selected Ready issuer can publish a route with the wrong certificate contract."""
    script = _load_script("scripts/gke/configure_evidence_ingress.py")
    kubeconfig, output = tmp_path / "gke.yaml", tmp_path / "routes.yaml"
    kubeconfig.write_text("contexts:\n- name: gke_expected\n", encoding="utf-8")
    commands: list[list[str]] = []
    present = True
    def runner(command: list[str]) -> dict[str, object]:
        nonlocal present
        commands.append(command)
        if "delete" in command:
            present = False
        if "clusterissuer" in command:
            return {"metadata": {"name": "edai2-acme-staging"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        if "ingress" in command:
            if not present:
                return {"items": []}
            return {"items": [{"metadata": {"name": "edai2-chat", "labels": {"edai2.route-set": "topic27", "edai2.lease-owner": "owner"}}, "spec": {"rules": [{"host": "chat.203.0.113.7.sslip.io"}]}}]}
        if "deployment" in command:
            return {"spec": {"replicas": 1}, "data": {"limit-req-status-code": "429"}}
        return {}
    script.execute_contract(ROOT, mode="enable", kubeconfig=kubeconfig, context="gke_expected", strict=True,
        route_set="topic27", routes="chat", ingress_ip="203.0.113.7", hosts="chat=chat.203.0.113.7.sslip.io",
        issuer="acme-staging", lease_owner="owner", ttl="1h", output=output, runner=runner)
    assert commands[0][-2:] == ["-f", str(output.with_name("routes.issuer.yaml"))]
    assert commands[1][-5:] == ["get", "clusterissuer", "edai2-acme-staging", "-o", "json"]
    assert commands[2][-2:] == ["-f", str(output)]
    assert "edai2-acme-production" not in output.with_name("routes.issuer.yaml").read_text(encoding="utf-8")
    before = len(commands)
    script.execute_contract(ROOT, mode="disable", kubeconfig=kubeconfig, context="gke_expected", strict=True,
        route_set="topic27", routes="chat", ingress_ip="203.0.113.7", hosts="chat=chat.203.0.113.7.sslip.io",
        issuer="acme-staging", lease_owner="owner", ttl="1h", output=output, runner=runner)
    assert all("clusterissuer" not in command for command in commands[before:])
    invalid_output = tmp_path / "invalid.yaml"
    with pytest.raises(ValueError, match="unsupported"):
        script.execute_contract(ROOT, mode="bad", kubeconfig=kubeconfig, context="gke_expected", strict=True,
            route_set="topic27", routes="chat", ingress_ip="203.0.113.7", hosts="chat=chat.203.0.113.7.sslip.io",
            issuer="acme-staging", lease_owner="owner", ttl="1h", output=invalid_output, runner=lambda _: pytest.fail("runner used"))
    assert not invalid_output.exists()
