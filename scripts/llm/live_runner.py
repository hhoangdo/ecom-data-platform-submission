"""Injectable process-execution runners for Topic 26 live CLIs.

No live calls happen at import time. Every Kubernetes-aware path takes an
explicit kubeconfig and context; the default context is never used. Error
messages never include command output, so secrets cannot leak through them.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

Runner = Callable[[list[str], Path], str]

AUTHORIZED_CONTEXT = "edai2-gke"


def _check_context(context: str) -> None:
    """Refuse any cluster context except the dedicated one or a gke_ cluster context."""
    if context != AUTHORIZED_CONTEXT and not context.startswith("gke_"):
        raise ValueError(f"only context {AUTHORIZED_CONTEXT} or a gke_ cluster context is authorized")


def _run(argv: list[str], cwd: Path | None = None) -> str:
    """Run one process; report only the executable name and exit code on failure."""
    try:
        completed = subprocess.run(
            argv,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"command {argv[0]} exited {error.returncode}") from error
    return completed.stdout


def _kubectl_base(kubeconfig: Path, context: str) -> list[str]:
    _check_context(context)
    return ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context]


def kubectl_runner(kubeconfig: Path, context: str) -> Runner:
    """Prefix every command with an explicit kubectl kubeconfig/context."""
    base = _kubectl_base(kubeconfig, context)

    def run(command: Sequence[str], cwd: Path) -> str:
        return _run([*base, *command], cwd)

    return run


def helm_runner(kubeconfig: Path, context: str) -> Runner:
    """Prefix every command with an explicit helm kubeconfig/kube-context."""
    _check_context(context)
    base = ["helm", "--kubeconfig", str(kubeconfig), "--kube-context", context]

    def run(command: Sequence[str], cwd: Path) -> str:
        return _run([*base, *command], cwd)

    return run


def local_arctl_runner() -> Runner:
    """Run arctl from PATH; fail closed when it is not installed."""

    def run(command: list[str], cwd: Path) -> str:
        if shutil.which("arctl") is None:
            raise ValueError("arctl executable not found on PATH")
        return _run(list(command), cwd)

    return run


def gke_job_runner(
    kubeconfig: Path,
    context: str,
    namespace: str,
    image: str,
    command: list[str],
    ttl_seconds: int,
) -> str:
    """Submit one TTL-bounded Job, wait, return its logs, then delete it."""
    base = _kubectl_base(kubeconfig, context)
    if not namespace or not image or not command:
        raise ValueError("namespace, image, and command are required")
    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer")
    job_name = f"edai2-{uuid.uuid4().hex[:8]}"
    manifest = (
        "apiVersion: batch/v1\n"
        "kind: Job\n"
        f"metadata: {{name: {job_name}, namespace: {namespace}}}\n"
        "spec:\n"
        f"  activeDeadlineSeconds: {ttl_seconds}\n"
        "  ttlSecondsAfterFinished: 300\n"
        "  template:\n"
        "    spec:\n"
        "      restartPolicy: Never\n"
        "      containers:\n"
        f"      - {{name: job, image: {image}, command: {command!r}}}\n"
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".yaml", delete=False
    ) as handle:
        handle.write(manifest)
        manifest_path = handle.name
    try:
        _run([*base, "apply", "-f", manifest_path])
        _run([*base, "wait", "--for=condition=complete", f"job/{job_name}",
              "--namespace", namespace, f"--timeout={ttl_seconds}s"])
        return _run([*base, "logs", f"job/{job_name}", "--namespace", namespace])
    finally:
        try:
            _run([*base, "delete", "-f", manifest_path, "--ignore-not-found=true"])
        except RuntimeError:
            pass
        Path(manifest_path).unlink(missing_ok=True)
