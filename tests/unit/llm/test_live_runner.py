"""Unit tests for scripts/llm/live_runner.py process-execution helpers."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts/llm/live_runner.py"


def _runner():
    assert RUNNER.is_file(), "missing live runner helper"
    spec = importlib.util.spec_from_file_location("topic26_live_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_local_runner_rejects_missing_arctl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _runner()
    monkeypatch.setattr("shutil.which", lambda _name: None)

    with pytest.raises(ValueError, match="arctl"):
        module.local_arctl_runner()(["arctl", "agent", "show"], tmp_path)


def test_local_runner_passes_through_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _runner()
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/arctl")
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    assert module.local_arctl_runner()(["arctl", "agent", "show", "retrieval", "--output", "json"], tmp_path) == "{}"
    assert seen == [["arctl", "agent", "show", "retrieval", "--output", "json"]]


def test_runners_reject_unauthorized_context(tmp_path: Path) -> None:
    module = _runner()

    with pytest.raises(ValueError, match="context"):
        module.kubectl_runner(tmp_path / "kubeconfig", "corporate-cluster")
    with pytest.raises(ValueError, match="context"):
        module.helm_runner(tmp_path / "kubeconfig", "corporate-cluster")
    with pytest.raises(ValueError, match="context"):
        module.gke_job_runner(
            tmp_path / "kubeconfig",
            "corporate-cluster",
            "edai2",
            "image",
            ["arctl"],
            600,
        )


def test_runners_accept_dedicated_and_gke_contexts(tmp_path: Path) -> None:
    module = _runner()

    for context in ("edai2-gke", "gke_my-project_us-central1-a_edai2"):
        assert module.kubectl_runner(tmp_path / "kubeconfig", context) is not None
        assert module.helm_runner(tmp_path / "kubeconfig", context) is not None


def test_kubectl_and_helm_runners_prefix_kubeconfig_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _runner()
    seen: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    kubeconfig = tmp_path / "kubeconfig"

    assert module.kubectl_runner(kubeconfig, "edai2-gke")(["get", "deploy"], tmp_path) == "ok"
    assert module.helm_runner(kubeconfig, "edai2-gke")(["list"], tmp_path) == "ok"
    assert seen[0][:5] == ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "edai2-gke"]
    assert seen[1][:5] == ["helm", "--kubeconfig", str(kubeconfig), "--kube-context", "edai2-gke"]


def test_gke_job_runner_applies_waits_logs_and_deletes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _runner()
    seen: list[list[str]] = []
    manifests: list[str] = []

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(argv)
        assert argv[:5] == [
            "kubectl",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--context",
            "edai2-gke",
        ]
        if argv[5:7] == ["apply", "-f"]:
            manifests.append(Path(argv[7]).read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(argv, 0, stdout="job created", stderr="")
        if argv[5:7] == ["wait", "--for=condition=complete"]:
            return subprocess.CompletedProcess(argv, 0, stdout="job complete", stderr="")
        if argv[5] == "logs":
            return subprocess.CompletedProcess(argv, 0, stdout="{}" + "\n", stderr="")
        if argv[5:7] == ["delete", "-f"]:
            return subprocess.CompletedProcess(argv, 0, stdout="job deleted", stderr="")
        raise AssertionError(f"unexpected kubectl call: {argv}")

    monkeypatch.setattr("subprocess.run", fake_run)

    logs = module.gke_job_runner(
        tmp_path / "kubeconfig",
        "edai2-gke",
        "edai2",
        "example/arctl@sha256:" + "a" * 64,
        ["arctl", "agent", "publish", "/tmp/x"],
        600,
    )

    assert logs == "{}" + "\n"
    kinds = [argv[5] for argv in seen]
    assert kinds == ["apply", "wait", "logs", "delete"]
    assert "namespace: edai2" in manifests[0]
    assert "activeDeadlineSeconds:" in manifests[0]
    assert "ttlSecondsAfterFinished:" in manifests[0]


def test_gke_job_runner_never_leaks_command_output_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _runner()

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[5:7] == ["apply", "-f"]:
            return subprocess.CompletedProcess(argv, 0, stdout="job created", stderr="")
        raise subprocess.CalledProcessError(1, argv, output="SECRET-TOKEN", stderr="boom")

    monkeypatch.setattr("subprocess.run", fake_run)

    with pytest.raises(RuntimeError) as excinfo:
        module.gke_job_runner(
            tmp_path / "kubeconfig", "edai2-gke", "edai2", "example/img", ["arctl"], 600
        )
    assert "SECRET-TOKEN" not in str(excinfo.value)
