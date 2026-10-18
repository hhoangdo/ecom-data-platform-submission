"""KEDA probe and agent chat contracts for Topic 26 smoke (Task 3)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SMOKE = ROOT / "scripts/llm/smoke_release.py"


def _smoke():
    assert SMOKE.is_file(), "missing smoke CLI"
    spec = importlib.util.spec_from_file_location("topic26_smoke_release", SMOKE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _kubectl_empty_endpoints(command: list[str], cwd: Path) -> str:
    if command[:2] == ["get", "endpoints"]:
        return json.dumps({})
    raise AssertionError(f"unexpected kubectl call: {command}")


def test_keda_probe_fails_closed_on_empty_endpoints() -> None:
    module = _smoke()

    with pytest.raises(ValueError, match="endpoint"):
        module.run_keda_probe(
            kubectl=_kubectl_empty_endpoints,
            http_post=lambda url, payload: {},
            agents=["retrieval"],
            api_min=1,
            api_max=2,
            worker_min=1,
            worker_max=2,
            threshold_rps=1,
            overlapping_sessions=2,
            chat_base_url="http://chat.local",
        )


def _keda_fakes():
    state = {"hpa_replicas": 1, "calls": []}

    def kubectl(command: list[str], cwd: Path) -> str:
        state["calls"].append(command)
        if command[:2] == ["get", "endpoints"]:
            return json.dumps({"subsets": [{"addresses": [{"ip": "10.0.0.1"}]}]})
        if command[:2] == ["get", "hpa"]:
            return json.dumps({"desired": state["hpa_replicas"], "ready": state["hpa_replicas"]})
        if command[:2] == ["get", "pods"]:
            return json.dumps(
                {"items": [{"metadata": {"uid": f"pod-uid-{state['hpa_replicas']}-{i}"}} for i in range(2)]}
            )
        raise AssertionError(f"unexpected kubectl call: {command}")

    def http_post(url: str, payload: dict) -> dict:
        state["calls"].append(["POST", url, payload.get("session", "")])
        if state["hpa_replicas"] < 2 and "load" in url:
            state["hpa_replicas"] = 2
        if state["hpa_replicas"] == 2 and "drain" in url:
            state["hpa_replicas"] = 1
        session = payload.get("session", "s")
        return {"session_id": session, "actor_id": f"actor-{session}"}

    return state, kubectl, http_post


def test_keda_probe_drives_one_two_one_with_distinct_actors() -> None:
    module = _smoke()
    state, kubectl, http_post = _keda_fakes()

    evidence = module.run_keda_probe(
        kubectl=kubectl,
        http_post=http_post,
        agents=["retrieval"],
        api_min=1,
        api_max=2,
        worker_min=1,
        worker_max=2,
        threshold_rps=1,
        overlapping_sessions=2,
        chat_base_url="http://chat.local",
    )

    assert evidence["agents"][0]["scaled_to"] == 2
    assert evidence["agents"][0]["cooled_to"] == 1
    session = evidence["agents"][0]["overlapping_sessions"][0]
    assert len(set(session["actor_ids"])) == 2
    assert len(set(session["pod_uids"])) >= 2
    assert state["hpa_replicas"] == 1


def test_keda_probe_rejects_shared_actor_id() -> None:
    module = _smoke()
    state, kubectl, _ = _keda_fakes()

    def same_actor(url: str, payload: dict) -> dict:
        if "load" in url and state["hpa_replicas"] < 2:
            state["hpa_replicas"] = 2
        if "load" in url:
            return {"session_id": "boot", "actor_id": "actor-boot"}
        return {"session_id": payload.get("session", "s"), "actor_id": "actor-same"}

    with pytest.raises(ValueError, match="actor"):
        module.run_keda_probe(
            kubectl=kubectl,
            http_post=same_actor,
            agents=["drift"],
            api_min=1,
            api_max=2,
            worker_min=1,
            worker_max=2,
            threshold_rps=1,
            overlapping_sessions=2,
            chat_base_url="http://chat.local",
        )


def test_agent_chats_require_registry_binding_and_grounded_answers() -> None:
    module = _smoke()
    registry = {"retrieval": {"route": "retrieval-mcp"}}

    def http_post(url: str, payload: dict) -> dict:
        return {"answer": "Order 42 shipped yesterday.", "citations": ["returns.md"]}

    evidence = module.run_agent_chats(
        http_post=http_post,
        agents=["retrieval"],
        registry_evidence=registry,
        chat_base_url="http://chat.local",
    )

    assert evidence["retrieval"]["grounded"] is True

    with pytest.raises(ValueError, match="registry"):
        module.run_agent_chats(
            http_post=http_post,
            agents=["coordinator"],
            registry_evidence=registry,
            chat_base_url="http://chat.local",
        )


def test_agent_chats_reject_pii_echo() -> None:
    module = _smoke()
    registry = {"retrieval": {"route": "retrieval-mcp"}}

    def http_post(url: str, payload: dict) -> dict:
        return {"answer": "Customer customer_id=12345 lives here."}

    with pytest.raises(ValueError, match="[Pp][Ii][Ii]"):
        module.run_agent_chats(
            http_post=http_post,
            agents=["retrieval"],
            registry_evidence=registry,
            chat_base_url="http://chat.local",
        )


def test_main_accepts_keda_and_chat_flags() -> None:
    module = _smoke()

    args = module.parse_args(
        [
            "--keda-ha",
            "--agents",
            "retrieval,drift,coordinator",
            "--api-min",
            "1",
            "--api-max",
            "2",
            "--worker-min",
            "1",
            "--worker-max",
            "2",
            "--threshold-rps",
            "1",
            "--overlapping-sessions",
            "2",
            "--output",
            "keda_ha.json",
            "--agent-chats",
            "retrieval",
            "--registry-evidence",
            "registry.json",
            "--kubeconfig",
            "kubeconfig",
            "--context",
            "edai2-gke",
            "--chat-base-url",
            "http://chat.local",
            "--strict",
        ]
    )

    assert args.keda_ha is True
    assert args.agents == "retrieval,drift,coordinator"
    assert args.overlapping_sessions == 2
