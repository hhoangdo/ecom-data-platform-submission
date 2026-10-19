"""Rollback proof contracts for Topic 26 smoke (Task 4)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SMOKE = ROOT / "scripts/llm/smoke_release.py"


def _smoke():
    assert SMOKE.is_file(), "missing smoke CLI"
    spec = importlib.util.spec_from_file_location("topic26_smoke_rollback", SMOKE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _helm_history_ok(*, current: int = 7) -> list[dict]:
    return [
        {"revision": current - 1, "status": "superseded"},
        {"revision": current, "status": "deployed"},
    ]


def test_helm_rollback_rejects_history_mismatch(tmp_path: Path) -> None:
    module = _smoke()

    def helm(command: list[str], cwd: Path) -> str:
        if command[:2] == ["history", "retrieval"]:
            return json.dumps([{"revision": 3, "status": "deployed"}])
        raise AssertionError(f"unexpected helm call: {command}")

    def kubectl(command: list[str], cwd: Path) -> str:
        raise AssertionError(f"unexpected kubectl call: {command}")

    with pytest.raises(ValueError, match="history"):
        module.prove_helm_rollback(
            helm=helm,
            kubectl=kubectl,
            http_get=lambda url: {"status": 200},
            release="retrieval",
            namespace="edai2",
            failure_mode="bad-readiness",
            readyz_url="http://retrieval.edai2.svc.cluster.local/readyz",
            prior_revision=7,
            cwd=tmp_path,
        )


def test_helm_rollback_restores_prior_revision_and_passes_readyz(tmp_path: Path) -> None:
    module = _smoke()
    calls: list[list[str]] = []
    history = {"revisions": _helm_history_ok(current=7)}

    def helm(command: list[str], cwd: Path) -> str:
        calls.append(command)
        if command[:2] == ["history", "retrieval"]:
            return json.dumps(history["revisions"])
        if command[:2] == ["upgrade", "retrieval"]:
            history["revisions"].append({"revision": 8, "status": "failed"})
            raise RuntimeError("helm exited 1")
        if command[:2] == ["rollback", "retrieval"]:
            history["revisions"].append({"revision": 9, "status": "deployed"})
            return "rolled back"
        raise AssertionError(f"unexpected helm call: {command}")

    def kubectl(command: list[str], cwd: Path) -> str:
        calls.append(command)
        return "deployment ready"

    evidence = module.prove_helm_rollback(
        helm=helm,
        kubectl=kubectl,
        http_get=lambda url: {"status": 200},
        release="retrieval",
        namespace="edai2",
        failure_mode="bad-readiness",
        readyz_url="http://retrieval.edai2.svc.cluster.local/readyz",
        prior_revision=7,
        cwd=tmp_path,
    )

    assert evidence["failed_revision"] == 8
    assert evidence["restored_revision"] == 9
    assert evidence["history_match"] is True
    assert evidence["readyz_pass"] is True
    rollbacks = [call for call in calls if call[:2] == ["rollback", "retrieval"]]
    assert rollbacks == [["rollback", "retrieval", "7"]]


def test_helm_rollback_rejects_missing_failed_revision(tmp_path: Path) -> None:
    module = _smoke()

    def helm(command: list[str], cwd: Path) -> str:
        if command[:2] == ["history", "retrieval"]:
            return json.dumps(_helm_history_ok(current=7))
        if command[:2] == ["upgrade", "retrieval"]:
            raise RuntimeError("helm exited 1")
        raise AssertionError(f"unexpected helm call: {command}")

    with pytest.raises(ValueError, match="failed revision"):
        module.prove_helm_rollback(
            helm=helm,
            kubectl=lambda command, cwd: "ok",
            http_get=lambda url: {"status": 200},
            release="retrieval",
            namespace="edai2",
            failure_mode="bad-readiness",
            readyz_url="http://retrieval.edai2.svc.cluster.local/readyz",
            prior_revision=7,
            cwd=tmp_path,
        )


def test_helm_rollback_rejects_inject_that_did_not_fail(tmp_path: Path) -> None:
    module = _smoke()

    def helm(command: list[str], cwd: Path) -> str:
        if command[:2] == ["history", "retrieval"]:
            return json.dumps(_helm_history_ok(current=7))
        if command[:2] == ["upgrade", "retrieval"]:
            return "deployed"
        raise AssertionError(f"unexpected helm call: {command}")

    with pytest.raises(ValueError, match="did not fail"):
        module.prove_helm_rollback(
            helm=helm,
            kubectl=lambda command, cwd: "ok",
            http_get=lambda url: {"status": 200},
            release="retrieval",
            namespace="edai2",
            failure_mode="bad-readiness",
            readyz_url="http://retrieval.edai2.svc.cluster.local/readyz",
            prior_revision=7,
            cwd=tmp_path,
        )


def _model_deployment(command: list[str], state: dict) -> str:
    if command[:2] == ["get", "deployment"]:
        return json.dumps(
            {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {"name": "model", "image": f"ghcr.io/llm-d/llm-d-cpu@{state['digest']}"}
                            ]
                        }
                    }
                }
            }
        )
    if command[:2] == ["set", "image"]:
        state["digest"] = command[3].split("@", 1)[1]
        return "image updated"
    if command[:2] == ["rollout", "status"]:
        return "deployment ready"
    if command[:2] == ["get", "pods"]:
        return json.dumps({"items": [{"metadata": {"name": "llmd-primary-abc", "uid": "uid-1"}}]})
    if command[:2] == ["delete", "pod"]:
        state["deleted"] += 1
        return "pod deleted"
    raise AssertionError(f"unexpected kubectl call: {command}")


def test_model_rollback_restores_prior_digest_and_survives_endpoint_loss() -> None:
    module = _smoke()
    state = {"digest": "sha256:good", "deleted": 0}

    def kubectl(command: list[str], cwd: Path) -> str:
        return _model_deployment(command, state)

    def http_get(url: str) -> dict:
        if "readyz" in url and state["digest"] != "sha256:good":
            return {"status": 503}
        return {"status": 200}

    evidence = module.prove_model_rollback(
        kubectl=kubectl,
        http_get=http_get,
        primary="llmd-primary",
        namespace="edai2",
        invalid_digest="sha256:" + "0" * 64,
        readyz_url="http://llmd-primary/readyz",
        delete_one_healthy=True,
        active_active_replicas=2,
        cwd=Path("."),
    )

    assert evidence["invalid_never_ready"] is True
    assert evidence["restored_digest"] == "sha256:good"
    assert evidence["surviving_endpoint_served"] is True
    assert state["digest"] == "sha256:good"


def test_model_rollback_rejects_unexpected_ready_candidate() -> None:
    module = _smoke()

    def kubectl(command: list[str], cwd: Path) -> str:
        return _model_deployment(command, {"digest": "sha256:good", "deleted": 0})

    with pytest.raises(ValueError, match="became ready"):
        module.prove_model_rollback(
            kubectl=kubectl,
            http_get=lambda url: {"status": 200},
            primary="llmd-primary",
            namespace="edai2",
            invalid_digest="sha256:" + "0" * 64,
            readyz_url="http://llmd-primary/readyz",
            delete_one_healthy=False,
            active_active_replicas=2,
            cwd=Path("."),
        )


def test_live_evidence_requires_strict() -> None:
    module = _smoke()

    with pytest.raises(SystemExit, match="strict"):
        module.main(["--keda-ha"])

    with pytest.raises(SystemExit, match="strict"):
        module.main(["--verify-readyz", "retrieval", "--expected-revision-from", "helm.json"])


def test_verify_readyz_gate_checks_live_readiness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _smoke()
    expected = tmp_path / "helm.json"
    expected.write_text(json.dumps({"restored_revision": 9, "failed_revision": 8}), encoding="utf-8")
    monkeypatch.setattr(module, "_http_get", lambda url: {"status": 200})

    assert (
        module.main(
            [
                "--verify-readyz",
                "retrieval",
                "--expected-revision-from",
                str(expected),
                "--strict",
            ]
        )
        == 0
    )

    monkeypatch.setattr(module, "_http_get", lambda url: {"status": 503})
    with pytest.raises(SystemExit, match="readyz failed"):
        module.main(
            [
                "--verify-readyz",
                "retrieval",
                "--expected-revision-from",
                str(expected),
                "--strict",
            ]
        )


def test_inject_requires_verify_and_restore_flags() -> None:
    module = _smoke()

    with pytest.raises(SystemExit, match="verify-atomic-rollback"):
        module.main(
            [
                "--inject-helm-failure",
                "retrieval",
                "--failure-mode",
                "bad-readiness",
                "--verify-readyz",
                "retrieval",
                "--output",
                "helm.json",
                "--kubeconfig",
                "kubeconfig",
                "--context",
                "edai2-gke",
                "--strict",
            ]
        )


def test_index_rollback_keeps_active_alias_on_failed_candidate() -> None:
    module = _smoke()
    store = {"active": "v3", "candidates": {}}

    def get_active() -> str:
        return store["active"]

    def promote(version: str) -> None:
        raise ValueError("candidate validation failed")

    rolled: list[str] = []
    restored: list[bool] = []

    evidence = module.prove_index_rollback(
        get_active_alias=get_active,
        promote_candidate=promote,
        rollback_to=lambda alias: rolled.append(alias) or alias,
        restore_current=lambda: restored.append(True),
        eval_fn=lambda: {"pass": True},
        candidate_version="v4-bad",
        previous_good="v2",
        cwd=Path("."),
    )

    assert store["active"] == "v3"
    assert evidence["active_unchanged"] is True
    assert evidence["rollback_to"] == "v2"
    assert evidence["restored_current"] is True
    assert evidence["eval_pass"] is True


def test_index_rollback_rejects_eval_regression() -> None:
    module = _smoke()

    with pytest.raises(ValueError, match="evaluation"):
        module.prove_index_rollback(
            get_active_alias=lambda: "v3",
            promote_candidate=lambda version: (_ for _ in ()).throw(ValueError("bad")),
            rollback_to=lambda alias: alias,
            restore_current=lambda: None,
            eval_fn=lambda: {"pass": False},
            candidate_version="v4-bad",
            previous_good="v2",
            cwd=Path("."),
        )


def test_verify_namespace_rejects_expected_actual_mismatch() -> None:
    """Releases live in default, Deployments in edai2; single-ns assumption must fail."""
    module = _smoke()
    with pytest.raises(ValueError, match="namespace"):
        module.verify_namespace(expected="default", actual="edai2", context="helm-release-vs-deployment")


def test_helm_rollback_fails_closed_on_namespace_mismatch(tmp_path: Path) -> None:
    module = _smoke()

    def helm(command: list[str], cwd: Path) -> str:
        raise AssertionError("helm must not run after namespace mismatch")

    def kubectl(command: list[str], cwd: Path) -> str:
        raise AssertionError("kubectl must not run after namespace mismatch")

    with pytest.raises(ValueError, match="namespace"):
        module.prove_helm_rollback(
            helm=helm,
            kubectl=kubectl,
            http_get=lambda url: {"status": 200},
            release="retrieval",
            namespace="edai2",
            failure_mode="bad-readiness",
            readyz_url="http://retrieval.edai2.svc.cluster.local/readyz",
            prior_revision=7,
            cwd=tmp_path,
            expected_namespace="default",
            actual_namespace="edai2",
        )


def test_model_rollback_fails_closed_on_namespace_mismatch() -> None:
    module = _smoke()

    def kubectl(command: list[str], cwd: Path) -> str:
        raise AssertionError("kubectl must not run after namespace mismatch")

    with pytest.raises(ValueError, match="namespace"):
        module.prove_model_rollback(
            kubectl=kubectl,
            http_get=lambda url: {"status": 200},
            primary="llmd-primary",
            namespace="edai2",
            invalid_digest="sha256:" + "0" * 64,
            readyz_url="http://llmd-primary/readyz",
            delete_one_healthy=False,
            active_active_replicas=2,
            cwd=Path("."),
            expected_namespace="default",
            actual_namespace="edai2",
        )
