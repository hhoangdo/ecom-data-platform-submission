"""Fail-closed KEDA/HA/chat/rollback smoke for Topic 26 live evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Runner = Callable[[list[str], Path], str]
HttpPost = Callable[[str, dict], dict]

PII_MARKERS = ("customer_id=",)

_LIVE_RUNNER: Any = None


def _live_runner_module() -> Any:
    """Load the sibling process-execution helpers without importing them."""
    global _LIVE_RUNNER
    if _LIVE_RUNNER is None:
        path = Path(__file__).resolve().parent / "live_runner.py"
        spec = importlib.util.spec_from_file_location("topic26_smoke_live_runner", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LIVE_RUNNER = module
    return _LIVE_RUNNER


def _http_post(url: str, payload: dict) -> dict:
    """POST one JSON payload and return the decoded JSON response."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get(url: str) -> dict:
    """GET one URL; always report the HTTP status code under `status`."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            code = response.status
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return {"status": error.code, "body": ""}
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {"text": raw}
    result: dict = {"status": code}
    if isinstance(body, dict):
        result.update(body)
    else:
        result["body"] = body
    return result


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _write_evidence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _helm_history(helm: Runner, release: str, cwd: Path) -> list[dict]:
    history = json.loads(helm(["history", release, "-o", "json"], cwd))
    if not isinstance(history, list) or not history:
        raise ValueError(f"no helm history for release: {release}")
    return history


def prove_helm_rollback(
    *,
    helm: Runner,
    kubectl: Runner,
    http_get: Callable[[str], dict],
    release: str,
    namespace: str,
    failure_mode: str,
    readyz_url: str,
    prior_revision: int | None = None,
    cwd: Path = Path("."),
) -> dict:
    """Inject a failing release value, then atomically restore the prior revision."""
    history = _helm_history(helm, release, cwd)
    deployed = [entry["revision"] for entry in history if entry.get("status") == "deployed"]
    if prior_revision is None:
        if not deployed:
            raise ValueError(f"no deployed revision for release: {release}")
        prior_revision = max(deployed)
    if prior_revision not in [entry.get("revision") for entry in history]:
        raise ValueError(f"prior revision {prior_revision} not in helm history for release: {release}")
    try:
        helm(["upgrade", release, "--set", f"failureMode={failure_mode}"], cwd)
    except RuntimeError:
        injected_failed = True
    else:
        injected_failed = False
    if not injected_failed:
        raise ValueError(f"injected failure did not fail for release: {release}")
    after = _helm_history(helm, release, cwd)
    after_revisions = [entry.get("revision") for entry in after]
    failed = [revision for revision in after_revisions if revision not in [h.get("revision") for h in history]]
    if not failed:
        raise ValueError(f"failed revision missing from helm history for release: {release}")
    helm(["rollback", release, str(prior_revision)], cwd)
    restored = _helm_history(helm, release, cwd)
    restored_revisions = [entry.get("revision") for entry in restored]
    deployed_now = sorted(entry["revision"] for entry in restored if entry.get("status") == "deployed")
    history_match = (
        bool(deployed_now)
        and max(deployed_now) > prior_revision
        and prior_revision in restored_revisions
    )
    if not history_match:
        raise ValueError(f"helm history mismatch after rollback for release: {release}")
    kubectl(["rollout", "status", f"deployment/{release}", "--namespace", namespace], cwd)
    ready = http_get(readyz_url)
    readyz_pass = ready.get("status") == 200
    if not readyz_pass:
        raise ValueError(f"/readyz failed after rollback for release: {release}")
    return {
        "release": release,
        "failure_mode": failure_mode,
        "failed_revision": max(failed),
        "prior_revision": prior_revision,
        "restored_revision": max(deployed_now),
        "history_match": True,
        "readyz_pass": True,
    }


def prove_model_rollback(
    *,
    kubectl: Runner,
    http_get: Callable[[str], dict],
    primary: str,
    namespace: str,
    invalid_digest: str,
    readyz_url: str,
    delete_one_healthy: bool,
    active_active_replicas: int = 2,
    cwd: Path = Path("."),
) -> dict:
    """Prove an invalid model image digest never serves, then restore the live digest."""
    observed = json.loads(kubectl(["get", "deployment", primary, "--namespace", namespace, "-o", "json"], cwd))
    try:
        containers = observed["spec"]["template"]["spec"]["containers"]
        live_image = containers[0]["image"]
        container_name = containers[0]["name"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"deployment has no container image: {primary}") from error
    if "@sha256:" not in live_image:
        raise ValueError(f"deployment image is not digest-pinned: {primary}")
    repository, _, prior_digest = live_image.partition("@")
    kubectl(
        ["set", "image", f"deployment/{primary}", f"{container_name}={repository}@{invalid_digest}",
         "--namespace", namespace],
        cwd,
    )
    if http_get(readyz_url).get("status") == 200:
        raise ValueError(f"invalid candidate became ready for model: {primary}")
    kubectl(
        ["set", "image", f"deployment/{primary}", f"{container_name}={repository}@{prior_digest}",
         "--namespace", namespace],
        cwd,
    )
    kubectl(["rollout", "status", f"deployment/{primary}", "--namespace", namespace], cwd)
    if http_get(readyz_url).get("status") != 200:
        raise ValueError(f"restored model not ready for model: {primary}")
    surviving = False
    if delete_one_healthy and active_active_replicas >= 2:
        pods = json.loads(
            kubectl(["get", "pods", "-l", f"app.kubernetes.io/name={primary}", "--namespace", namespace, "-o", "json"], cwd)
        )
        items = pods.get("items", [])
        if not items or "metadata" not in items[0] or "name" not in items[0]["metadata"]:
            raise ValueError(f"no healthy endpoint to delete for model: {primary}")
        kubectl(["delete", "pod", items[0]["metadata"]["name"], "--namespace", namespace], cwd)
        surviving = http_get(readyz_url).get("status") == 200
        if not surviving:
            raise ValueError(f"router did not survive endpoint loss for model: {primary}")
    return {
        "primary": primary,
        "invalid_digest": invalid_digest,
        "invalid_never_ready": True,
        "restored_digest": prior_digest,
        "surviving_endpoint_served": surviving,
    }


def prove_index_rollback(
    *,
    get_active_alias: Callable[[], str],
    promote_candidate: Callable[[str], None],
    rollback_to: Callable[[str], str],
    restore_current: Callable[[], None],
    eval_fn: Callable[[], dict],
    candidate_version: str,
    previous_good: str,
    cwd: Path = Path("."),
) -> dict:
    """Prove a failed candidate cannot mutate the active alias, then roll back."""
    _ = cwd
    before = get_active_alias()
    try:
        promote_candidate(candidate_version)
    except ValueError:
        promoted = False
    else:
        promoted = True
    if promoted:
        raise ValueError(f"invalid candidate unexpectedly promoted: {candidate_version}")
    if get_active_alias() != before:
        raise ValueError("active alias mutated by failed candidate")
    rolled = rollback_to(previous_good)
    evaluation = eval_fn()
    if not evaluation.get("pass"):
        raise ValueError("evaluation regressed after index rollback")
    restore_current()
    return {
        "candidate_version": candidate_version,
        "active_unchanged": True,
        "rollback_to": rolled,
        "restored_current": True,
        "eval_pass": True,
    }


def _hpa_status(kubectl: Runner, name: str, cwd: Path) -> dict:
    return json.loads(kubectl(["get", "hpa", name, "-o", "json"], cwd))


def _endpoints_ready(kubectl: Runner, name: str, cwd: Path) -> bool:
    endpoints = json.loads(kubectl(["get", "endpoints", name, "-o", "json"], cwd))
    return bool(endpoints.get("subsets"))


def _pod_uids(kubectl: Runner, agent: str, cwd: Path) -> list[str]:
    pods = json.loads(kubectl(["get", "pods", "-l", f"app.kubernetes.io/name={agent}", "-o", "json"], cwd))
    return [item["metadata"]["uid"] for item in pods.get("items", [])]


def run_keda_probe(
    *,
    kubectl: Runner,
    http_post: HttpPost,
    agents: list[str],
    api_min: int,
    api_max: int,
    worker_min: int,
    worker_max: int,
    threshold_rps: int,
    overlapping_sessions: int,
    chat_base_url: str,
    poll_interval_s: int = 15,
    max_polls: int = 40,
    cwd: Path = Path("."),
) -> dict:
    """Drive 1->2->1 scaling per agent with distinct overlapping actors."""
    _ = (worker_min, worker_max, threshold_rps)
    probe: dict = {"agents": []}
    for agent in agents:
        if not _endpoints_ready(kubectl, f"{agent}-agent", cwd):
            raise ValueError(f"no ready endpoints for agent: {agent}")
        transitions: list[dict] = []
        scaled = False
        for _ in range(max_polls):
            http_post(f"{chat_base_url}/load", {"agent": agent})
            hpa = _hpa_status(kubectl, f"keda-hpa-{agent}-agent", cwd)
            transitions.append(
                {"at": _utcnow(), "desired": hpa["desired"], "ready": hpa["ready"]}
            )
            if hpa["desired"] >= api_max and hpa["ready"] >= api_max:
                scaled = True
                break
            time.sleep(poll_interval_s)
        if not scaled:
            raise ValueError(f"keda scale-up timeout for agent: {agent}")
        sessions = [f"{agent}-overlap-{index}" for index in range(overlapping_sessions)]
        actor_ids: list[str] = []
        for session in sessions:
            response = http_post(f"{chat_base_url}/chat", {"agent": agent, "session": session})
            actor_ids.append(response.get("actor_id", ""))
        if any(not actor for actor in actor_ids):
            raise ValueError(f"chat response missing actor id for agent: {agent}")
        if len(set(actor_ids)) != len(actor_ids):
            raise ValueError(f"duplicate actor id for agent: {agent}")
        pod_uids = _pod_uids(kubectl, agent, cwd)
        if len(set(pod_uids)) < 2:
            raise ValueError(f"overlapping sessions share one pod for agent: {agent}")
        http_post(f"{chat_base_url}/drain", {"agent": agent})
        cooled = False
        for _ in range(max_polls):
            hpa = _hpa_status(kubectl, f"keda-hpa-{agent}-agent", cwd)
            transitions.append(
                {"at": _utcnow(), "desired": hpa["desired"], "ready": hpa["ready"]}
            )
            if hpa["desired"] <= api_min and hpa["ready"] <= api_min:
                cooled = True
                break
            time.sleep(poll_interval_s)
        if not cooled:
            raise ValueError(f"keda cooldown timeout for agent: {agent}")
        probe["agents"].append(
            {
                "agent": agent,
                "scaled_to": api_max,
                "cooled_to": api_min,
                "overlapping_sessions": [
                    {"session_ids": sessions, "actor_ids": actor_ids, "pod_uids": sorted(set(pod_uids))}
                ],
                "transitions": transitions,
            }
        )
    return probe


def run_agent_chats(
    *,
    http_post: HttpPost,
    agents: list[str],
    registry_evidence: dict,
    chat_base_url: str,
) -> dict:
    """Chat each agent through its registry-bound route; reject PII echoes."""
    evidence: dict = {}
    for agent in agents:
        if agent not in registry_evidence:
            raise ValueError(f"agent not in registry evidence: {agent}")
        response = http_post(
            f"{chat_base_url}/chat", {"agent": agent, "prompt": "Summarize order status."}
        )
        answer = response.get("answer", "")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"empty chat answer for agent: {agent}")
        for marker in PII_MARKERS:
            if marker in answer:
                raise ValueError(f"PII marker echoed in answer for agent: {agent}")
        evidence[agent] = {"grounded": bool(response.get("citations")), "citations": response.get("citations", [])}
    return evidence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the Topic 26 smoke, KEDA, chat, and rollback request."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--release", choices=("retrieval", "drift", "coordinator", "llmd-primary"))
    parser.add_argument("--streaming-writers", action="store_true")
    parser.add_argument("--prove-atomic-rollback", action="store_true")
    parser.add_argument("--prove-model-rollback", action="store_true")
    parser.add_argument("--keda-ha", action="store_true")
    parser.add_argument("--agents", default=None)
    parser.add_argument("--api-min", type=int, default=None)
    parser.add_argument("--api-max", type=int, default=None)
    parser.add_argument("--worker-min", type=int, default=None)
    parser.add_argument("--worker-max", type=int, default=None)
    parser.add_argument("--threshold-rps", type=int, default=None)
    parser.add_argument("--overlapping-sessions", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--agent-chats", default=None)
    parser.add_argument("--registry-evidence", type=Path, default=None)
    parser.add_argument("--kubeconfig", type=Path, default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--chat-base-url", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--inject-helm-failure", default=None)
    parser.add_argument("--inject-model-failure", default=None)
    parser.add_argument("--failure-mode", default=None)
    parser.add_argument("--verify-readyz", default=None)
    parser.add_argument("--expected-revision-from", type=Path, default=None)
    parser.add_argument("--verify-atomic-rollback", action="store_true")
    parser.add_argument("--verify-modelconfig-rollback", action="store_true")
    parser.add_argument("--restore-current", action="store_true")
    parser.add_argument("--active-active-replicas", type=int, default=None)
    parser.add_argument("--delete-one-healthy-primary-endpoint", action="store_true")
    parser.add_argument("--namespace", default="edai2")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the requested smoke; refuse live work without explicit flags."""
    args = parse_args(argv)
    if args.dry_run and not (args.keda_ha or args.agent_chats or args.release):
        print(json.dumps({"live_execution": False, "release": args.release, "streaming_writers": args.streaming_writers}, sort_keys=True))
        return 0
    if bool(args.kubeconfig is None) != bool(args.context is None):
        raise SystemExit("--kubeconfig and --context are required together")
    live_requested = bool(
        args.keda_ha or args.agent_chats or args.inject_helm_failure or args.inject_model_failure or args.verify_readyz
    )
    if live_requested and not args.strict:
        raise SystemExit("live evidence requires --strict")
    if args.release is not None and live_requested:
        raise SystemExit("--release is dry-run only; drop it for live evidence")
    live = _live_runner_module()
    wrote: dict = {}
    if args.keda_ha:
        for name in ("agents", "api_min", "api_max", "worker_min", "worker_max",
                      "threshold_rps", "overlapping_sessions", "output", "chat_base_url",
                      "kubeconfig", "context"):
            if getattr(args, name) is None:
                raise SystemExit(f"--keda-ha requires --{name.replace('_', '-')}")
        kubectl = live.kubectl_runner(args.kubeconfig, args.context)
        evidence = run_keda_probe(
            kubectl=kubectl,
            http_post=_http_post,
            agents=args.agents.split(","),
            api_min=args.api_min,
            api_max=args.api_max,
            worker_min=args.worker_min,
            worker_max=args.worker_max,
            threshold_rps=args.threshold_rps,
            overlapping_sessions=args.overlapping_sessions,
            chat_base_url=args.chat_base_url,
        )
        _write_evidence(args.output, evidence)
        wrote["keda_ha"] = str(args.output)
    if args.agent_chats:
        for name in ("registry_evidence", "output", "chat_base_url"):
            if getattr(args, name) is None:
                raise SystemExit(f"--agent-chats requires --{name.replace('_', '-')}")
        registry = json.loads(Path(args.registry_evidence).read_text(encoding="utf-8"))
        evidence = run_agent_chats(
            http_post=_http_post,
            agents=args.agent_chats.split(","),
            registry_evidence=registry,
            chat_base_url=args.chat_base_url,
        )
        _write_evidence(args.output, evidence)
        wrote["agent_chats"] = str(args.output)
    if args.prove_atomic_rollback and args.inject_helm_failure is None:
        raise SystemExit("--prove-atomic-rollback requires --inject-helm-failure")
    if args.prove_model_rollback and args.inject_model_failure is None:
        raise SystemExit("--prove-model-rollback requires --inject-model-failure")
    if args.inject_helm_failure:
        for name in ("failure_mode", "output", "kubeconfig", "context", "verify_readyz"):
            if getattr(args, name) is None:
                raise SystemExit(f"--inject-helm-failure requires --{name.replace('_', '-')}")
        if not args.verify_atomic_rollback or not args.restore_current:
            raise SystemExit("--inject-helm-failure requires --verify-atomic-rollback --restore-current")
        evidence = prove_helm_rollback(
            helm=live.helm_runner(args.kubeconfig, args.context),
            kubectl=live.kubectl_runner(args.kubeconfig, args.context),
            http_get=_http_get,
            release=args.inject_helm_failure,
            namespace=args.namespace,
            failure_mode=args.failure_mode,
            readyz_url=f"http://{args.verify_readyz}.{args.namespace}.svc.cluster.local/readyz",
            cwd=Path("."),
        )
        _write_evidence(args.output, evidence)
        wrote["helm_rollback"] = str(args.output)
    if args.inject_model_failure:
        for name in ("failure_mode", "output", "kubeconfig", "context"):
            if getattr(args, name) is None:
                raise SystemExit(f"--inject-model-failure requires --{name.replace('_', '-')}")
        if not args.verify_modelconfig_rollback or not args.restore_current:
            raise SystemExit("--inject-model-failure requires --verify-modelconfig-rollback --restore-current")
        kubectl = live.kubectl_runner(args.kubeconfig, args.context)
        evidence = prove_model_rollback(
            kubectl=kubectl,
            http_get=_http_get,
            primary=args.inject_model_failure,
            namespace=args.namespace,
            invalid_digest="sha256:" + "0" * 64,
            readyz_url=f"http://{args.inject_model_failure}.{args.namespace}.svc.cluster.local/readyz",
            delete_one_healthy=args.delete_one_healthy_primary_endpoint,
            active_active_replicas=args.active_active_replicas or 2,
            cwd=Path("."),
        )
        _write_evidence(args.output, evidence)
        wrote["model_rollback"] = str(args.output)
    if args.verify_readyz and not (args.inject_helm_failure or args.inject_model_failure or args.keda_ha or args.agent_chats):
        if args.expected_revision_from is None:
            raise SystemExit("--verify-readyz requires --expected-revision-from")
        try:
            expected = json.loads(Path(args.expected_revision_from).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(f"expected revision is unreadable: {error}") from error
        ready = _http_get(f"http://{args.verify_readyz}.{args.namespace}.svc.cluster.local/readyz")
        if ready.get("status") != 200:
            raise SystemExit(f"/readyz failed for agent: {args.verify_readyz}")
        print(json.dumps({"agent": args.verify_readyz, "readyz_pass": True, "expected_revision": expected.get("restored_revision", expected.get("failed_revision"))}, sort_keys=True))
        return 0
    if not wrote:
        parser_error = "--dry-run is required; live smoke and rollback execution belongs to a future GKE evidence topic; use --dry-run"
        raise SystemExit(parser_error)
    print(json.dumps({"live_execution": True, **wrote}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
