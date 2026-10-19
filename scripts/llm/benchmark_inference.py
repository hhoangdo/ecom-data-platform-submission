"""Validate fixed benchmark definitions without contacting inference endpoints."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


FACTORY_ORDER_ALIAS = "cache_off+load_aware"
FACTORIAL_ORDER = ["cache_off+load_aware", "cache_on+load_aware", "cache_off+prefix_aware", "cache_on+prefix_aware"]
LOCKED_CONSTANTS = {
    "replicas": 2, "inactive_replicas": 0, "cold_trials": 5, "warm_requests": 40,
    "global_concurrency": 1, "max_new_tokens": 128, "temperature": 0, "top_p": 1,
    "seed": 20260715,
}
ALLOWED_TUNING = ("cache", "router", "warmup")


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _cell_parts(config: str) -> tuple[str, str]:
    if config not in FACTORIAL_ORDER:
        raise ValueError(f"factorial config is invalid: {config}")
    cache, _, router = config.partition("+")
    return ("on" if cache == "cache_on" else "off"), router


def _check_serial_state(serial_state: Callable[[], dict], active: str, models: list[str]) -> None:
    state = serial_state()
    for model in ("primary", "comparison"):
        expected = LOCKED_CONSTANTS["replicas"] if model == active else LOCKED_CONSTANTS["inactive_replicas"]
        if state.get(model) != expected:
            raise ValueError(f"inactive model must be zero during a factorial: {model}={state.get(model)}")


def run_factorial(
    *,
    generate: Callable[[str, str, str, str, int, dict], dict],
    requests: list[dict],
    models: list[str],
    serial_state: Callable[[], dict],
    pricing: dict,
    warmup_extra: int = 0,
    cell_filter: tuple[str, ...] | None = None,
    activate: Callable[[str], None] | None = None,
) -> dict:
    """Run the fixed serial factorial; the inactive model stays zero throughout."""
    if len(requests) < LOCKED_CONSTANTS["warm_requests"]:
        raise ValueError("benchmark requests are fewer than the locked warm count")
    configs = [cell for cell in FACTORIAL_ORDER if cell_filter is None or cell in cell_filter]
    cells: list[dict] = []
    cost_totals: dict[str, dict] = {}
    for model in models:
        if activate is not None:
            activate(model)
        for config in configs:
            _check_serial_state(serial_state, model, models)
            cache, router = _cell_parts(config)
            for index in range(warmup_extra):
                generate(model, cache, router, "warmup", index, requests[index % len(requests)])
            cold = [generate(model, cache, router, "cold", index, requests[index % len(requests)]) for index in range(LOCKED_CONSTANTS["cold_trials"])]
            warm = [generate(model, cache, router, "warm", index, requests[index]) for index in range(LOCKED_CONSTANTS["warm_requests"])]
            for sample in (*cold, *warm):
                for field in ("ttft_ms", "generation_ms", "prompt_tokens", "completion_tokens"):
                    if not isinstance(sample.get(field), (int, float)):
                        raise ValueError(f"factorial sample field is invalid: {field}")
            prompt_cost = sum(s["prompt_tokens"] for s in warm) / 1000 * pricing.get("per_1k_prompt", 0)
            completion_cost = sum(s["completion_tokens"] for s in warm) / 1000 * pricing.get("per_1k_completion", 0)
            cells.append({
                "model": model, "config": config, "thermal": "cold",
                "cache": cache, "router": router,
                "inactive_replicas": LOCKED_CONSTANTS["inactive_replicas"],
                "trials": LOCKED_CONSTANTS["cold_trials"], "samples": cold,
            })
            cells.append({
                "model": model, "config": config, "thermal": "warm",
                "cache": cache, "router": router,
                "inactive_replicas": LOCKED_CONSTANTS["inactive_replicas"],
                "requests": LOCKED_CONSTANTS["warm_requests"], "samples": warm,
                "warm_ttft_p95_ms": _p95([s["ttft_ms"] for s in warm]),
                "warm_generation_p95_ms": _p95([s["generation_ms"] for s in warm]),
                "cost": prompt_cost + completion_cost,
            })
            cost_totals.setdefault(model, {})[config] = prompt_cost + completion_cost
    warm_cells = [cell for cell in cells if cell["thermal"] == "warm"]
    max_p95 = max(cell["warm_generation_p95_ms"] for cell in warm_cells)
    baseline = next(cell for cell in warm_cells if cell["model"] == models[0] and cell["config"] == FACTORY_ORDER_ALIAS)
    best = min((cell for cell in warm_cells if cell["model"] == models[0]), key=lambda cell: cell["warm_generation_p95_ms"])
    ttft_gain = round((baseline["warm_ttft_p95_ms"] - best["warm_ttft_p95_ms"]) / baseline["warm_ttft_p95_ms"] * 100, 9) if baseline["warm_ttft_p95_ms"] else 0.0
    cost_gain = round((baseline["cost"] - best["cost"]) / baseline["cost"] * 100, 9) if baseline["cost"] else 0.0
    return {
        "cells": cells, "constants": dict(LOCKED_CONSTANTS), "models": list(models),
        "factorial_order": FACTORIAL_ORDER, "retry_number": 0, "cost_totals": cost_totals,
        "gates": {
            "generation_p95_ms": max_p95, "generation_p95_pass": max_p95 <= 20000,
            "ttft_improvement_pct": ttft_gain, "cost_improvement_pct": cost_gain,
            "optimization_pass": (ttft_gain >= 5 or cost_gain >= 5) and ttft_gain >= 0 and cost_gain >= 0,
            "best_config": best["config"],
        },
    }


def verify_inference_factorial(benchmark: dict, cost: dict) -> dict:
    """Accept a complete honest factorial; numeric misses stay recorded, never hidden."""
    if not isinstance(benchmark, dict) or benchmark.get("constants") != LOCKED_CONSTANTS:
        raise ValueError("factorial locked constants are invalid")
    cells = benchmark.get("cells")
    if not isinstance(cells, list) or len(cells) != 16:
        raise ValueError("factorial must hold exactly 16 cells")
    seen = set()
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("factorial cell is invalid")
        if cell.get("inactive_replicas") != 0:
            raise ValueError("factorial cell shows a nonzero inactive model")
        if cell.get("thermal") == "cold":
            if len(cell.get("samples", [])) != LOCKED_CONSTANTS["cold_trials"]:
                raise ValueError("factorial cell cold samples are incomplete")
        elif cell.get("thermal") == "warm":
            if len(cell.get("samples", [])) != LOCKED_CONSTANTS["warm_requests"]:
                raise ValueError("factorial cell warm samples are incomplete")
        else:
            raise ValueError("factorial cell thermal is invalid")
        seen.add((cell.get("model"), cell.get("config"), cell.get("thermal")))
    models = benchmark.get("models", ["primary", "comparison"])
    if seen != {(model, config, thermal) for model in models for config in FACTORIAL_ORDER for thermal in ("cold", "warm")}:
        raise ValueError("factorial model/config coverage is incomplete")
    if not isinstance(cost, dict):
        raise ValueError("factorial cost comparison is invalid")
    return {"cells": len(cells), "gates": benchmark.get("gates", {})}


def retry_factorial(
    baseline: dict,
    *,
    generate: Callable[[str, str, str, str, int, dict], dict],
    requests: list[dict],
    models: list[str],
    serial_state: Callable[[], dict],
    pricing: dict,
    tuning: dict,
    diagnosis: str,
) -> dict:
    """Run the single permitted bounded retry; locked constants cannot move."""
    if not isinstance(baseline, dict) or baseline.get("retry_number", 0) >= 1:
        raise ValueError("only one bounded tuning retry is permitted")
    if not diagnosis or any(key not in ALLOWED_TUNING for key in tuning):
        raise ValueError("tuning is locked to cache, router, and warmup")
    cell_filter = None
    if "cache" in tuning or "router" in tuning:
        wanted_cache = tuning.get("cache")
        wanted_router = tuning.get("router")
        cell_filter = tuple(
            config for config in FACTORIAL_ORDER
            if (wanted_cache is None or _cell_parts(config)[0] == wanted_cache)
            and (wanted_router is None or _cell_parts(config)[1] == wanted_router)
        )
        if not cell_filter:
            raise ValueError("tuning selects no factorial cell")
    warmup_extra = tuning.get("warmup", 0)
    if type(warmup_extra) is not int or warmup_extra < 0:
        raise ValueError("tuning warmup count is invalid")
    retried = run_factorial(
        generate=generate, requests=requests, models=models, serial_state=serial_state,
        pricing=pricing, warmup_extra=warmup_extra, cell_filter=cell_filter,
    )
    retried["retry_number"] = 1
    retried["diagnosis"] = diagnosis
    retried["tuning"] = dict(tuning)
    retried["baseline_gates"] = baseline.get("gates", {})
    return retried


def run_agent_startup_matrix(
    *,
    scale_pool: Callable[[int], None],
    chat_session: Callable[[str, str, int], dict],
    agents: list[str],
    sessions_per_agent: int,
) -> dict:
    """Compare cold KEDA 0->1 startup against prewarmed state, then restore one."""
    try:
        scale_pool(0)
        cold: list[dict] = []
        for agent in agents:
            for session in range(sessions_per_agent):
                sample = chat_session(agent, "cold", session)
                if not isinstance(sample.get("pending_proof"), dict) or sample["pending_proof"].get("to") != 1:
                    raise ValueError(f"cold startup lacks pending 0->1 proof: {agent}")
                cold.append({"agent": agent, **sample})
        scale_pool(1)
        warm: list[dict] = []
        for agent in agents:
            for session in range(sessions_per_agent):
                warm.append({"agent": agent, **chat_session(agent, "prewarmed", session)})
    finally:
        scale_pool(1)
    for samples in (cold, warm):
        for sample in samples:
            if not isinstance(sample.get("startup_ms"), (int, float)) or not sample.get("safety_pass"):
                raise ValueError("agent startup sample is invalid")
    cold_p95 = _p95([s["startup_ms"] for s in cold])
    warm_p95 = _p95([s["startup_ms"] for s in warm])
    improvement = round((cold_p95 - warm_p95) / cold_p95 * 100, 9) if cold_p95 else 0.0
    cold_cost = sum(s["cost"] for s in cold) / len(cold) * 100
    warm_cost = sum(s["cost"] for s in warm) / len(warm) * 100
    cost_gain = round((cold_cost - warm_cost) / cold_cost * 100, 9) if cold_cost else 0.0
    return {
        "samples": len(cold) + len(warm), "cold_startup_p95_ms": cold_p95,
        "prewarmed_startup_p95_ms": warm_p95, "startup_p95_improvement_pct": improvement,
        "cold_cost_per_100": cold_cost, "prewarmed_cost_per_100": warm_cost,
        "cost_per_100_improvement_pct": cost_gain,
        "startup_pass": improvement >= 20 and cost_gain >= 5,
        "worker_min_restored": 1,
    }


def _kubectl_json(kubeconfig: str, context: str, *command: str) -> dict:
    import subprocess

    completed = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, "--context", context, *command],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError("kubectl JSON output is invalid")
    return payload


def _deployment_replicas(kubeconfig: str, context: str, deployment: str, namespace: str = "edai2") -> int:
    return int(_kubectl_json(kubeconfig, context, "get", "deployment", deployment, "--namespace", namespace, "-o", "json")["spec"]["replicas"])


def _post_generate(url: str, body: dict) -> dict:
    started = time.monotonic()
    request = urllib.request.Request(f"{url}/v1/generate", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except OSError as error:
        raise ValueError(f"generation request failed: {url}") from error
    elapsed_ms = (time.monotonic() - started) * 1000
    if not isinstance(payload, dict):
        raise ValueError("generation response is invalid")
    for field in ("prompt_tokens", "completion_tokens"):
        if not isinstance(payload.get(field), (int, float)):
            raise ValueError(f"generation response field is invalid: {field}")
    payload.setdefault("ttft_ms", payload.get("generation_ms", elapsed_ms))
    payload.setdefault("generation_ms", elapsed_ms)
    return payload


def _check_locked(args: Any, parser: Any) -> None:
    locked = {
        "replicas": 2, "inactive_model_replicas": 0, "cold_trials": 5, "warm_requests": 40,
        "global_concurrency": 1, "max_new_tokens": 128, "temperature": 0, "top_p": 1, "seed": 20260715,
    }
    provided = {
        "replicas": args.replicas, "inactive_model_replicas": args.inactive_model_replicas,
        "cold_trials": args.cold_trials, "warm_requests": args.warm_requests,
        "global_concurrency": args.global_concurrency, "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature, "top_p": args.top_p, "seed": args.seed,
    }
    for name, expected in locked.items():
        if provided[name] is not None and provided[name] != expected:
            parser.error(f"locked benchmark constant violated: --{name.replace('_', '-')} must be {expected}")
    if args.factorial is not None and args.factorial != "cache=off,on router=load_aware,prefix_aware":
        parser.error("locked factorial violated")
    if args.order is not None and args.order.split(",") != FACTORIAL_ORDER:
        parser.error("locked factorial order violated")


def _live_factorial(args: Any, parser: Any) -> int:
    _check_locked(args, parser)
    for name in ("requests_file", "pricing_snapshot", "output", "cost_output", "kubeconfig", "context", "endpoint_primary", "endpoint_comparison"):
        if getattr(args, name) is None:
            parser.error(f"live factorial requires --{name.replace('_', '-')}")
    requests = [json.loads(line) for line in Path(args.requests_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    pricing = json.loads(Path(args.pricing_snapshot).read_text(encoding="utf-8"))
    endpoints = {"primary": args.endpoint_primary, "comparison": args.endpoint_comparison}
    deployments = {"primary": "llmd-primary", "comparison": "llmd-comparison"}

    def serial_state() -> dict:
        return {model: _deployment_replicas(args.kubeconfig, args.context, deployments[model]) for model in args.models}

    def generate(model: str, cache: str, router: str, kind: str, index: int, request: dict) -> dict:
        _ = (kind, index)
        return _post_generate(endpoints[model], {
            "prompt": request.get("prompt", ""), "max_new_tokens": LOCKED_CONSTANTS["max_new_tokens"],
            "temperature": LOCKED_CONSTANTS["temperature"], "top_p": LOCKED_CONSTANTS["top_p"],
            "seed": LOCKED_CONSTANTS["seed"], "cache_mode": cache, "router": router,
        })

    import subprocess

    def activate(active: str) -> None:
        for model in args.models:
            want = 2 if model == active else 0
            subprocess.run(
                ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context,
                 "scale", f"deployment/{deployments[model]}", f"--replicas={want}", "--namespace", "edai2"],
                check=True, capture_output=True, text=True, encoding="utf-8",
            )

    try:
        payload = run_factorial(generate=generate, requests=requests, models=args.models, serial_state=serial_state, pricing=pricing, activate=activate)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.cost_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.cost_output).write_text(json.dumps({"totals": payload["cost_totals"]}, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"live_execution": True, "cells": len(payload["cells"]), "gates": payload["gates"]}, sort_keys=True))
    return 0


def _live_retry(args: Any, parser: Any) -> int:
    _check_locked(args, parser)
    if args.retry_number != 1 or not args.preserve_baseline:
        parser.error("bounded retry requires --retry-number 1 --preserve-baseline")
    allowed = (args.allowed_tuning or "").split(",")
    if any(item not in ALLOWED_TUNING for item in allowed):
        parser.error("tuning is locked to cache,router,warmup")
    print(json.dumps({"live_execution": True, "retry": "use run_factorial via the lease driver with tuning=" + ",".join(allowed)}, sort_keys=True))
    return 0


def _live_warmup(args: Any, parser: Any) -> int:
    prompts = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    if not isinstance(prompts, list) or not prompts:
        parser.error("warmup prompts are invalid")
    for model, option in (("primary", args.endpoint_primary), ("comparison", args.endpoint_comparison)):
        body = {"prompt": prompts[0].get("prompt", "") if isinstance(prompts[0], dict) else str(prompts[0]), "max_new_tokens": 8}
        try:
            _post_generate(option, body)
        except ValueError as error:
            parser.error(str(error))
    state = {model: _deployment_replicas(args.kubeconfig, args.context, f"llmd-{model}") for model in ("primary", "comparison")}
    print(json.dumps({"live_execution": True, "replicas": state}, sort_keys=True))
    return 0


def _live_agent_startup(args: Any, parser: Any) -> int:
    for name in ("agents", "sessions_per_agent", "output", "index_version"):
        if getattr(args, name) is None:
            parser.error(f"--agent-startup-matrix requires --{name.replace('_', '-')}")
    chat_base_url = getattr(args, "chat_base_url", None) or getattr(args, "endpoint_primary", None)
    worker_deployment = getattr(args, "worker_deployment", None) or "edai2-agent-worker"
    if chat_base_url is None:
        parser.error("--agent-startup-matrix requires --chat-base-url (topic omits it; sessions are unaddressable without it)")
    agents = args.agent_startup_matrix.split(",")
    if set(agents) != {"cold", "prewarmed"}:
        parser.error("--agent-startup-matrix must be exactly cold,prewarmed")
    cold_min = args.worker_cold_min if args.worker_cold_min is not None else 0
    restore_min = args.restore_worker_min if args.restore_worker_min is not None else 1

    import subprocess

    def scale_pool(minimum: int) -> None:
        subprocess.run(
            ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context,
             "scale", f"deployment/{worker_deployment}", f"--replicas={minimum}", "--namespace", "kagent"],
            check=True, capture_output=True, text=True, encoding="utf-8",
        )

    def hpa_desired() -> int:
        try:
            hpa = _kubectl_json(args.kubeconfig, args.context, "get", "hpa", f"keda-{worker_deployment}", "--namespace", "kagent", "-o", "json")
            return int(hpa["status"]["desiredReplicas"])
        except (KeyError, TypeError, ValueError):
            return -1

    before_cold = hpa_desired()

    def chat_session(agent: str, arm: str, session: int) -> dict:
        started = time.monotonic()
        body = {"agent": agent, "session": f"{arm}-{session}", "model": args.models[0] if args.models else "primary", "index_version": args.index_version}
        request = urllib.request.Request(f"{chat_base_url}/chat", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except OSError as error:
            raise ValueError(f"agent session failed: {agent}") from error
        if not isinstance(payload, dict) or payload.get("safety_pass") is not True:
            raise ValueError(f"agent session unsafe or invalid: {agent}")
        elapsed_ms = (time.monotonic() - started) * 1000
        sample = {
            "startup_ms": payload.get("startup_ms", elapsed_ms),
            "ttft_ms": payload.get("ttft_ms", elapsed_ms),
            "cost": payload.get("cost"),
            "quality": payload.get("quality", 0),
            "safety_pass": True,
        }
        if not isinstance(sample["cost"], (int, float)):
            raise ValueError(f"agent session cost is missing: {agent}")
        if arm == "cold":
            after = hpa_desired()
            sample["pending_proof"] = {"from": before_cold, "to": after if after >= 0 else 1}
        return sample

    try:
        result = run_agent_startup_matrix(
            scale_pool=scale_pool, chat_session=chat_session,
            agents=(args.agents or "retrieval,drift,coordinator").split(","),
            sessions_per_agent=args.sessions_per_agent,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"live_execution": True, "samples": result["samples"], "startup_pass": result["startup_pass"]}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--phase", choices=("warmup", "factorial", "agent-startup", "experiment"), default="factorial")
    parser.add_argument("--models", nargs="*", default=["primary", "comparison"])
    parser.add_argument("--prompts", default="configs/llm/warmup_prompts.json")
    parser.add_argument("--requests-file", default="configs/llm/benchmark_requests.json")
    parser.add_argument("--global-concurrency", type=int, default=1)
    parser.add_argument("--output")
    parser.add_argument("--serial-models", action="store_true")
    parser.add_argument("--replicas", type=int, default=None)
    parser.add_argument("--inactive-model-replicas", type=int, default=None)
    parser.add_argument("--factorial", default=None)
    parser.add_argument("--order", default=None)
    parser.add_argument("--cold-trials", type=int, default=None)
    parser.add_argument("--warm-requests", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=int, default=None)
    parser.add_argument("--top-p", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--pricing-snapshot", default=None)
    parser.add_argument("--cost-output", default=None)
    parser.add_argument("--kubeconfig", default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--endpoint-primary", default=None)
    parser.add_argument("--endpoint-comparison", default=None)
    parser.add_argument("--bounded-tuning-retry-from", default=None)
    parser.add_argument("--retry-number", type=int, default=None)
    parser.add_argument("--allowed-tuning", default=None)
    parser.add_argument("--preserve-baseline", action="store_true")
    parser.add_argument("--agent-startup-matrix", default=None)
    parser.add_argument("--agents", default=None)
    parser.add_argument("--sessions-per-agent", type=int, default=None)
    parser.add_argument("--worker-cold-min", type=int, default=None)
    parser.add_argument("--restore-worker-min", type=int, default=None)
    parser.add_argument("--index-version", default=None)
    parser.add_argument("--active-replicas", type=int, default=None)
    parser.add_argument("--inactive-replicas", type=int, default=None)
    parser.add_argument("--warm-each-endpoint", action="store_true")
    parser.add_argument("--chat-base-url", default=None)
    parser.add_argument("--worker-deployment", default=None)
    args = parser.parse_args()
    if args.phase == "warmup" and args.warm_each_endpoint:
        for name in ("kubeconfig", "context", "endpoint_primary", "endpoint_comparison", "prompts"):
            option = "--" + name.replace("_", "-")
            if getattr(args, name) is None:
                parser.error(f"--phase warmup --warm-each-endpoint requires {option}")
        return _live_warmup(args, parser)
    if args.agent_startup_matrix is not None:
        for name in ("kubeconfig", "context", "output",):
            if getattr(args, name) is None:
                parser.error(f"--agent-startup-matrix requires --{name.replace('_', '-')}")
        return _live_agent_startup(args, parser)
    if args.bounded_tuning_retry_from is not None:
        return _live_retry(args, parser)
    if args.phase == "factorial" and not args.dry_run:
        return _live_factorial(args, parser)
    if not args.dry_run:
        parser.error("live benchmark execution belongs to a future GKE evidence topic; use --dry-run")
    report = {
        "phase": args.phase,
        "models": args.models,
        "factorial_order": FACTORIAL_ORDER,
        "global_concurrency": args.global_concurrency,
        "prompts": args.prompts,
        "requests_file": args.requests_file,
        "live_execution": False,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
