"""Fail-closed rendering contract for temporary EDAI2 evidence ingress."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Callable

import yaml


ROUTES = {
    "chat": ("edai2-chat", "coordinator", 8080, "/v1/chat"),
    "retrieval": ("edai2-retrieval", "retrieval-agent", 8080, "/"),
    "grafana": ("edai2-grafana", "grafana", 3000, "/"),
    "langfuse": ("edai2-langfuse", "langfuse", 3000, "/"),
    "jenkins": ("edai2-jenkins", "jenkins", 8080, "/"),
}


def validate_target(kubeconfig: Path, context: str, *, render_only: bool) -> None:
    if not kubeconfig.is_absolute() or not kubeconfig.is_file():
        raise ValueError("--kubeconfig must be an absolute readable file")
    loaded = yaml.safe_load(kubeconfig.read_text(encoding="utf-8")) or {}
    contexts = {item.get("name") for item in loaded.get("contexts", []) if isinstance(item, dict)}
    if context not in contexts:
        raise ValueError("--context is absent from the supplied kubeconfig")
    if render_only and context != "render-only":
        raise ValueError("render-only requires the dedicated render-only context")
    if not render_only and not context.startswith("gke_"):
        raise ValueError("live ingress requires an explicit GKE context")


def render_contract(root: Path) -> dict[str, object]:
    values = yaml.safe_load((root / "infra/helm/edai2/values/ingress-nginx.yaml").read_text(encoding="utf-8"))
    catalog = yaml.safe_load((root / "infra/helm/edai2/releases.yaml").read_text(encoding="utf-8"))
    if values["chartVersion"] != catalog["versions"]["ingress_nginx_chart"] or values["chartVersion"] != "4.15.1":
        raise ValueError("ingress chart version must be 4.15.1")
    controller = values["controller"]
    if controller["replicaCount"] != 1 or controller["config"].get("limit-req-status-code") != "429" or values.get("enabled") is not False:
        raise ValueError("evidence ingress contract is invalid")
    return {"chart_version": "4.15.1", "controller_replicas": 1, "limit_req_status_code": "429", "enabled": False}


def _parse_request(*, route_set: str, routes: str, ingress_ip: str, hosts: str, issuer: str, lease_owner: str, ttl: str, output: Path) -> list[tuple[str, str]]:
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", route_set or "") or not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", lease_owner or ""):
        raise ValueError("route set and lease owner are required")
    try:
        ipaddress.ip_address(ingress_ip)
    except ValueError as error:
        raise ValueError("temporary ingress IP is invalid") from error
    if issuer not in {"acme-staging", "acme-production"} or not re.fullmatch(r"[1-6]h", ttl or "") or not output.is_absolute():
        raise ValueError("issuer, TTL, and absolute output are required")
    names = routes.split(",") if routes else []
    if not names or len(set(names)) != len(names) or any(name not in ROUTES for name in names):
        raise ValueError("routes are not authorized")
    pairs = [item.split("=", 1) for item in hosts.split(",") if item] if hosts else []
    if len(pairs) != len(names) or any(len(pair) != 2 for pair in pairs) or {pair[0] for pair in pairs} != set(names):
        raise ValueError("hosts must exactly name selected routes")
    mapping = {route: host for route, host in pairs}
    selected = [(name, mapping[name]) for name in names]
    if any(host != f"{name}.{ingress_ip}.sslip.io" for name, host in selected):
        raise ValueError("hosts must match the explicit temporary ingress IP")
    return selected


def render_owned_ingresses(*, selected: list[tuple[str, str]], route_set: str, issuer: str, lease_owner: str) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    for route, host in selected:
        name, service, port, path = ROUTES[route]
        annotations = {"cert-manager.io/cluster-issuer": issuer}
        if route == "chat":
            annotations |= {"nginx.ingress.kubernetes.io/auth-type": "basic", "nginx.ingress.kubernetes.io/auth-secret": "chat-basic-auth", "nginx.ingress.kubernetes.io/limit-rps": "1", "nginx.ingress.kubernetes.io/limit-burst-multiplier": "5"}
        objects.append({"apiVersion": "networking.k8s.io/v1", "kind": "Ingress", "metadata": {"name": name, "namespace": "edai2", "labels": {"edai2.route-set": route_set, "edai2.lease-owner": lease_owner}, "annotations": annotations}, "spec": {"ingressClassName": "nginx", "tls": [{"hosts": [host], "secretName": f"{name}-tls"}], "rules": [{"host": host, "http": {"paths": [{"path": path, "pathType": "Prefix", "backend": {"service": {"name": service, "port": {"number": port}}}}]}}]}})
    return objects


def render_owned_issuer(root: Path, issuer: str) -> dict[str, object]:
    name = f"edai2-{issuer}"
    documents = [item for item in yaml.safe_load_all((root / "infra/ingress/edai2/certificate-issuer.yaml").read_text(encoding="utf-8")) if item]
    selected = [item for item in documents if item.get("kind") == "ClusterIssuer" and item.get("metadata", {}).get("name") == name]
    if len(selected) != 1:
        raise ValueError("requested issuer is not defined exactly once")
    return selected[0]


def _write_atomic(output: Path, objects: list[dict[str, object]]) -> None:
    temporary = output.with_name(f".{output.name}.tmp")
    try:
        temporary.write_text(yaml.safe_dump_all(objects, sort_keys=False), encoding="utf-8")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def _validate_readback(readback: dict[str, object], selected: list[tuple[str, str]], route_set: str, lease_owner: str) -> None:
    items = readback.get("items") if isinstance(readback, dict) else None
    expected = {ROUTES[route][0]: host for route, host in selected}
    if not isinstance(items, list) or len(items) != len(expected):
        raise ValueError("ingress readback failed")
    found: dict[str, str] = {}
    for item in items:
        try:
            metadata, spec = item["metadata"], item["spec"]
            labels, rules = metadata["labels"], spec["rules"]
            if labels != {"edai2.route-set": route_set, "edai2.lease-owner": lease_owner}:
                raise ValueError
            found[metadata["name"]] = rules[0]["host"]
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ValueError("ingress readback failed") from error
    if found != expected:
        raise ValueError("ingress readback failed")


def _validate_controller(readback: dict[str, object]) -> None:
    try:
        if readback["spec"]["replicas"] != 1 or readback["data"]["limit-req-status-code"] != "429":
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("controller readback failed") from error


def _validate_issuer(readback: dict[str, object], issuer: str) -> None:
    expected_name = f"edai2-{issuer}"
    try:
        conditions = readback["status"]["conditions"]
        ready = any(item["type"] == "Ready" and item["status"] == "True" for item in conditions)
        if readback["metadata"]["name"] != expected_name or not ready:
            raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("issuer readback failed") from error


def execute_contract(root: Path, *, mode: str, kubeconfig: Path, context: str, strict: bool, route_set: str, routes: str, ingress_ip: str, hosts: str, issuer: str, lease_owner: str, ttl: str, output: Path, runner: Callable[[list[str]], dict[str, object]]) -> dict[str, object]:
    if not strict:
        raise ValueError("--strict is required")
    if mode not in {"enable", "disable"}:
        raise ValueError("unsupported ingress mode")
    validate_target(kubeconfig, context, render_only=False)
    selected = _parse_request(route_set=route_set, routes=routes, ingress_ip=ingress_ip, hosts=hosts, issuer=issuer, lease_owner=lease_owner, ttl=ttl, output=output)
    objects = render_owned_ingresses(selected=selected, route_set=route_set, issuer=issuer, lease_owner=lease_owner)
    _write_atomic(output, objects)
    target = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context]
    base = [*target, "-n", "edai2"]
    names = [ROUTES[route][0] for route, _ in selected]
    if mode == "enable":
        issuer_output = output.with_name(f"{output.stem}.issuer.yaml")
        _write_atomic(issuer_output, [render_owned_issuer(root, issuer)])
        runner([*target, "apply", "-f", str(issuer_output)])
        _validate_issuer(runner([*target, "get", "clusterissuer", f"edai2-{issuer}", "-o", "json"]), issuer)
        runner([*base, "apply", "-f", str(output)])
        _validate_readback(runner([*base, "get", "ingress", *names, "-o", "json"]), selected, route_set, lease_owner)
        _validate_controller(runner([*base, "get", "deployment", "ingress-nginx-controller", "-n", "ingress-nginx", "-o", "json"]))
    else:
        runner([*base, "delete", "-f", str(output), "--ignore-not-found=false"])
        absence = runner([*base, "get", "ingress", *names, "-o", "json"])
        if absence.get("items") not in ([], None) or absence.get("present", False):
            raise ValueError("ingress absence readback failed")
    return {"mode": mode, "routes": [route for route, _ in selected], "hosts": [host for _, host in selected], "issuer": issuer, "lease_owner": lease_owner}


def main() -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--render-only", action="store_true")
    modes.add_argument("--enable", action="store_true")
    modes.add_argument("--disable", action="store_true")
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--route-set")
    parser.add_argument("--routes")
    parser.add_argument("--ingress-ip")
    parser.add_argument("--hosts")
    parser.add_argument("--issuer")
    parser.add_argument("--lease-owner")
    parser.add_argument("--ttl")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        if not args.render_only:
            raise ValueError("live ingress execution belongs to the GCP evidence topic")
        if not args.strict:
            raise ValueError("--strict is required")
        validate_target(Path(args.kubeconfig), args.context, render_only=True)
        supplied = (args.route_set, args.routes, args.ingress_ip, args.hosts, args.issuer, args.lease_owner, args.ttl, args.output)
        if any(value is not None for value in supplied):
            if not all(value is not None for value in supplied):
                raise ValueError("ingress render inputs must be complete")
            selected = _parse_request(route_set=args.route_set, routes=args.routes, ingress_ip=args.ingress_ip, hosts=args.hosts, issuer=args.issuer, lease_owner=args.lease_owner, ttl=args.ttl, output=Path(args.output))
            _write_atomic(Path(args.output), render_owned_ingresses(selected=selected, route_set=args.route_set, issuer=args.issuer, lease_owner=args.lease_owner))
        print(json.dumps(render_contract(Path.cwd()), sort_keys=True))
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
