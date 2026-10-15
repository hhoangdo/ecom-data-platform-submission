"""Topic 24 pre-lease checks against pinned Helm/Kustomize renders.

All four remaining OCI components are rendered instead of being assigned zero
resources. Missing container requests are a separate failing completeness gate.
The CPU total is a lower bound until generated gateway/WorkerPool Pods and
installation phases are fully accounted for; these checks do not prove readiness.

The current live PVC baseline is 71 GiB (10 Bound claims, verified 2026-10-12).
Jenkins adds 8 GiB. No orphan subtraction or PVC deletion is assumed.
Accepted ephemeral telemetry remains unchanged.
"""

from __future__ import annotations

import functools
import re
import subprocess
from pathlib import Path

import yaml

from scripts.gke.topic24_postrender import render as postrender
from scripts.gke.topic24_capacity import workload_totals, managed_projections

ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = ROOT / "infra/helm/edai2/releases.yaml"
VALUES_DIR = ROOT / "infra/helm/edai2/values"
LLMD_OVERLAY = ROOT / "infra/kustomize/llmd/overlays/cpu"

CHART_NAME_OVERRIDES = {"postgres": "postgresql"}

CPU_CEILING = 5.00
MEM_CEILING_GI = 18.0
LIVE_PVC_GI = 71.0
PVC_CEILING_GI = 80.0

# Current live read-back, without historical orphan subtraction.
ADJUSTED_LIVE_PVC_GI = LIVE_PVC_GI
REMAINING_RELEASES = [
    "prometheus", "loki", "tempo", "grafana", "alloy",
    "langfuse", "jenkins",
]
REMAINING_OCI_RELEASES = ("substrate", "kagent", "agentregistry", "agentgateway")

# RECORDED live baseline (verified once via kubectl get/describe/top -n edai2,
# NO live query in-test; cluster unreachable in CI). Grounded 2026-10-09:
# edai2 Running pods request cpu=3.200/mem=3.848Gi. Infra namespaces excluded.
RECORDED_LIVE_BASELINE = {
    "opensearch": {"cpu": 1.0, "mem_gi": 0.098, "note": "1000m/100Mi requests"},
    "redpanda": {"cpu": 1.0, "mem_gi": 2.5, "note": "limits-only 1/2.5Gi effective as requests"},
    "clickhouse-keeper": {"cpu": 0.5, "mem_gi": 0.5, "note": "500m/512Mi"},
    "clickhouse-shard": {"cpu": 0.5, "mem_gi": 0.5, "note": "500m/512Mi"},
    "postgres": {"cpu": 0.1, "mem_gi": 0.125, "note": "100m/128Mi"},
    "valkey": {"cpu": 0.1, "mem_gi": 0.125, "note": "100m/128Mi"},
    "airflow": {"cpu": 0.0, "mem_gi": 0.0, "note": "6 pods incl redis, no requests"},
    "feast": {"cpu": 0.0, "mem_gi": 0.0, "note": "2 pods, no requests"},
    "redpanda-console": {"cpu": 0.0, "mem_gi": 0.0, "note": "resources {}"},
}
RECORDED_BASELINE_CPU = 3.2
RECORDED_BASELINE_MEM_GI = 3.848

# Install-order Helm releases (Topic 24 14-stage order, cf.
# test_topic24_releases_catalog INSTALL_STAGE_CHARTS). EDAI2 platform scope
# excludes infra namespaces (external-secrets/cert-manager/ingress-nginx/keda)
# which have separate capacity; they are rendered but reported separately.
PLATFORM_RELEASES = [
    "postgres", "valkey", "redpanda", "opensearch", "clickhouse",
    "airflow", "feast", "datahub",
    "prometheus", "loki", "tempo", "grafana", "alloy",
    "langfuse", "jenkins",
]
INFRA_RELEASES = ["external-secrets", "cert-manager", "ingress-nginx", "keda"]

_CPU_RE = re.compile(r"^([0-9.]+)(m?)$")
_MEM_RE = re.compile(r"^([0-9.]+)([a-zA-Z]+)$")


def _parse_cpu(value: object) -> float:
    text = str(value).strip()
    match = _CPU_RE.match(text)
    assert match, f"unparseable cpu {value!r}"
    number = float(match.group(1))
    if match.group(2) == "m":
        return number / 1000.0
    return number


def _parse_mem_gi(value: object) -> float:
    text = str(value).strip()
    match = _MEM_RE.match(text)
    assert match, f"unparseable memory {value!r}"
    number = float(match.group(1))
    unit = match.group(2)
    if unit == "Gi":
        return number
    if unit == "Mi":
        return number / 1024.0
    if unit == "Ki":
        return number / 1024.0 / 1024.0
    if unit == "G":
        return number * 1000**3 / 1024**3
    if unit == "M":
        return number * 1000**2 / 1024**3
    raise AssertionError(f"unsupported memory unit {value!r}")


def _catalog_pins() -> dict[str, dict]:
    loaded = yaml.safe_load(CATALOG_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return {str(e["name"]): e for e in loaded.get("charts", []) + loaded.get("oci_charts", [])}


def test_remaining_components_are_counted_from_rendered_resources(monkeypatch) -> None:
    remaining = {"substrate", "kagent", "agentregistry", "agentgateway"}
    def render(release):
        if release not in remaining:
            return ""
        return yaml.safe_dump({"apiVersion": "apps/v1", "kind": "Deployment",
            "metadata": {"name": release}, "spec": {"replicas": 1, "template": {"spec": {
            "containers": [{"name": release, "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}}}]}}}})
    monkeypatch.setattr(__import__(__name__, fromlist=["x"]), "_render_helm", render)
    monkeypatch.setattr(__import__(__name__, fromlist=["x"]), "_render_llmd_cached", lambda: "")
    totals = _platform_totals()
    assert abs(sum(totals["per_release"][name]["cpu"] for name in remaining) - 0.4) < 1e-9
    assert totals["total_mem_gi"] >= 0.5
    assert all(totals["per_release"][name]["detail"] for name in remaining)


@functools.lru_cache(maxsize=None)
def _render_helm(release: str) -> str:
    pins = _catalog_pins()
    entry = pins[release]
    chart = CHART_NAME_OVERRIDES.get(release, release)
    target = ["--kubeconfig", str(ROOT / "tmp/edai2-gcp/kubeconfig"), "--kube-context", "edai2-gke"]
    source = str(entry["repo"])
    cmd = ["helm", *target, "template", release]
    if source.startswith("oci://"):
        cached = ROOT / "tmp/edai2-gcp/topic24-finalize/charts" / release
        assert entry.get("artifact_digest"), "Cached OCI render needs previously verified artifact provenance"
        assert cached.is_dir(), "Pinned OCI chart cache missing"
        metadata = yaml.safe_load((cached / "Chart.yaml").read_text(encoding="utf-8"))
        assert str(metadata["version"]).lstrip("v") == str(entry["version"]).lstrip("v")
        cmd += [str(cached)]
    else:
        cmd += [chart, "--repo", source]
    namespace = {"kagent": "kagent", "vault": "vault", "external-secrets": "external-secrets", "cert-manager": "cert-manager", "ingress-nginx": "ingress-nginx", "keda": "keda"}.get(release, "edai2")
    cmd += ["--version", str(entry["version"]), "-n", namespace]
    values_file = VALUES_DIR / f"{release}.yaml"
    if values_file.is_file():
        cmd += ["-f", str(values_file)]
    cmd += ["--dry-run=client"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, (
        f"helm template {release} failed: {proc.stderr[:2000]}"
    )
    return yaml.safe_dump_all(postrender(_split_docs(proc.stdout)), sort_keys=False)


def _render_llmd() -> str:
    proc = subprocess.run(
        ["kubectl", "--kubeconfig", str(ROOT / "tmp/edai2-gcp/kubeconfig"), "--context", "edai2-gke", "kustomize", str(LLMD_OVERLAY)],
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, f"kubectl kustomize llmd failed: {proc.stderr[:2000]}"
    return proc.stdout


@functools.lru_cache(maxsize=None)
def _render_llmd_cached() -> str:
    return _render_llmd()


def _split_docs(manifest: str) -> list[dict]:
    docs: list[dict] = []
    for part in re.split(r"(?m)^---[ \t]*\r?\n", manifest):
        if not part.strip():
            continue
        try:
            loaded = yaml.safe_load(part)
        except Exception:
            continue
        if isinstance(loaded, dict) and loaded.get("kind"):
            docs.append(loaded)
    return docs


def _workload_requests(docs: list[dict]) -> tuple[float, float, list[tuple]]:
    totals = workload_totals(docs, eligible_nodes=2, peak=False)
    return totals["cpu"], totals["memory_gib"], [(w["name"], w["kind"], "effective-pod", w["cpu"], w["memory_gib"], w["replicas"]) for w in totals["workloads"]]


def _pvc_gi(docs: list[dict]) -> float:
    total = 0.0
    for doc in docs:
        kind = doc.get("kind")
        if kind == "PersistentVolumeClaim":
            size = (((doc.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
            if size:
                text = str(size)
                if text.endswith("Gi"):
                    total += float(text[:-2])
                elif text.endswith("Mi"):
                    total += float(text[:-2]) / 1024.0
        if kind == "StatefulSet":
            for claim in (doc.get("spec") or {}).get("volumeClaimTemplates") or []:
                size = (((claim.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
                if size:
                    text = str(size)
                    if text.endswith("Gi"):
                        total += float(text[:-2])
                    elif text.endswith("Mi"):
                        total += float(text[:-2]) / 1024.0
    return total


def _platform_totals() -> dict:
    per_release: dict[str, dict] = {}
    total_cpu = 0.0
    total_mem = 0.0
    total_pvc_new = 0.0
    all_documents = []
    for release in PLATFORM_RELEASES + INFRA_RELEASES + ["vault", "substrate", "kagent", "agentregistry", "agentgateway"]:
        docs = _split_docs(_render_helm(release))
        all_documents.extend(docs)
        cpu, mem, detail = _workload_requests(docs)
        pvc = _pvc_gi(docs)
        per_release[release] = {"cpu": cpu, "mem_gi": mem, "pvc_gi": pvc, "detail": detail}
        total_cpu += cpu
        total_mem += mem
        total_pvc_new += pvc
    llmd_docs = _split_docs(_render_llmd_cached())
    llmd_cpu, llmd_mem, llmd_detail = _workload_requests(llmd_docs)
    llmd_pvc = _pvc_gi(llmd_docs)
    per_release["llmd"] = {"cpu": llmd_cpu, "mem_gi": llmd_mem, "pvc_gi": llmd_pvc, "detail": llmd_detail}
    total_cpu += llmd_cpu
    total_mem += llmd_mem
    total_pvc_new += llmd_pvc
    for path in list((ROOT / "infra/agentgateway/edai2").glob("*.yaml")) + [
            ROOT / "infra/kagent/edai2/worker-admission.yaml", ROOT / "infra/kagent/edai2/workerpool-scaledobject.yaml"]:
        all_documents.extend(_split_docs(path.read_text(encoding="utf-8")))
    generated = managed_projections(all_documents)
    gen_cpu, gen_mem, gen_detail = _workload_requests(generated)
    per_release["controller_generated"] = {"cpu": gen_cpu, "mem_gi": gen_mem, "pvc_gi": 0, "detail": gen_detail}
    total_cpu += gen_cpu
    total_mem += gen_mem
    return {
        "per_release": per_release,
        "total_cpu": total_cpu,
        "total_mem_gi": total_mem,
        "total_pvc_new_gi": total_pvc_new,
        "rendered_documents": all_documents + llmd_docs,
        "generated_documents": generated,
    }


def test_recorded_baseline_matches_grounded_table() -> None:
    assert abs(sum(v["cpu"] for v in RECORDED_LIVE_BASELINE.values()) - RECORDED_BASELINE_CPU) < 1e-6
    assert abs(sum(v["mem_gi"] for v in RECORDED_LIVE_BASELINE.values()) - RECORDED_BASELINE_MEM_GI) < 1e-3
    assert RECORDED_BASELINE_CPU == 3.2


def test_platform_cpu_fits_ceiling() -> None:
    totals = _platform_totals()
    total = totals["total_cpu"]
    headroom = CPU_CEILING - total
    per = {k: round(v["cpu"], 3) for k, v in totals["per_release"].items()}
    assert total <= CPU_CEILING, (
        f"platform aggregate CPU {total:.3f} exceeds {CPU_CEILING:.2f} ceiling. "
        f"per-release={per} headroom={headroom:.3f}"
    )
    assert headroom >= 0, f"headroom must be non-negative, got {headroom:.3f}"


def test_platform_mem_fits_ceiling() -> None:
    totals = _platform_totals()
    total = totals["total_mem_gi"]
    assert total <= MEM_CEILING_GI, (
        f"platform aggregate mem {total:.3f}Gi exceeds {MEM_CEILING_GI:.0f}Gi ceiling. "
        f"per-release={ {k: round(v['mem_gi'], 3) for k, v in totals['per_release'].items()} }"
    )


def test_remaining_components_do_not_have_unbounded_containers() -> None:
    missing = []
    for release in PLATFORM_RELEASES + INFRA_RELEASES + ["vault", "substrate", "kagent", "agentregistry", "agentgateway"]:
        for document in _split_docs(_render_helm(release)):
            if document.get("kind") not in ("Deployment", "StatefulSet", "DaemonSet"):
                continue
            for container in document["spec"]["template"]["spec"].get("containers", []):
                resources = container.get("resources", {})
                requests, limits = resources.get("requests", {}), resources.get("limits", {})
                for resource in ("cpu", "memory"):
                    if requests.get(resource, limits.get(resource)) is None:
                        missing.append(f"{release}/{document['metadata']['name']}/{container['name']}:{resource}")
    assert not missing, f"Remaining resource accounting is incomplete; unbounded containers: {missing}"


def test_tuning_adds_zero_new_pvc() -> None:
    # OUR tuning (resources.requests ONLY) adds ZERO new PVCs: tuned-scope new
    # 0Gi + 79Gi live = 79Gi <= 80Gi PASS. Full remaining new 26Gi
    # (prometheus 10 + loki 4 + tempo 4 + jenkins 8, pre-existing in values,
    # NOT introduced by tuning) is reported in
    # test_full_new_pvc_reported_as_residual_risk (not asserted) for the leased
    # agent to address via persistence disables for caches (outside LOCAL scope).
    totals = _platform_totals()
    tuned_scope_new = (
        totals["per_release"]["datahub"]["pvc_gi"]
        + totals["per_release"]["llmd"]["pvc_gi"]
        + totals["per_release"]["langfuse"]["pvc_gi"]
        + totals["per_release"]["grafana"]["pvc_gi"]
        + totals["per_release"]["alloy"]["pvc_gi"]
    )
    assert tuned_scope_new == 0, f"tuned scope must add zero PVC, got {tuned_scope_new}Gi"
    assert LIVE_PVC_GI + tuned_scope_new <= PVC_CEILING_GI, (
        f"PVC math blown: live {LIVE_PVC_GI}Gi + tuned-new {tuned_scope_new}Gi > {PVC_CEILING_GI}Gi"
    )


def test_full_new_pvc_reported_as_residual_risk() -> None:
    totals = _platform_totals()
    full_new = totals["total_pvc_new_gi"]
    # Informational only: full new includes pre-existing observability/jenkins
    # PVCs (prometheus/loki/tempo/jenkins) that cannot be fixed within LOCAL
    # resources.requests-only scope. Leased agent must disable persistence for
    # caches to fit 80Gi (no deletions, data retained). This test always passes
    # but records the numbers; the ceiling assertion lives in
    # test_tuning_adds_zero_new_pvc for the tuned scope.
    per_pvc = {k: v["pvc_gi"] for k, v in totals["per_release"].items() if v["pvc_gi"]}
    assert full_new >= 0, f"full new PVC must be non-negative, got {full_new}"
    assert per_pvc, f"expected pre-existing observability/jenkins PVCs in report, got none (full_new={full_new})"


def test_llmd_primary_tuned_to_1cpu_with_tradeoff() -> None:
    docs = _split_docs(_render_llmd_cached())
    primaries = [d for d in docs if d.get("kind") == "Deployment" and ((d.get("metadata") or {}).get("name") == "llmd-primary")]
    assert len(primaries) == 1, "expected exactly one llmd-primary Deployment"
    pod = (primaries[0].get("spec") or {}).get("template", {}).get("spec", {})
    containers = pod.get("containers") or []
    assert containers, "llmd-primary must carry containers"
    req = (containers[0].get("resources") or {}).get("requests") or {}
    assert str(req.get("cpu")) in ("1", "1000m"), f"llmd primary cpu must be tuned 2->1, got {req.get('cpu')!r}"
    assert str(req.get("memory")) == "4Gi", f"llmd primary mem must stay 4Gi, got {req.get('memory')!r}"
    comparisons = [d for d in docs if ((d.get("metadata") or {}).get("name") == "llmd-comparison")]
    for doc in comparisons:
        assert (doc.get("spec") or {}).get("replicas") == 0, "llmd comparison replicas 0 counts 0"


def test_opensearch_redpanda_clickhouse_tuned() -> None:
    totals = _platform_totals()
    per = totals["per_release"]
    assert abs(per["opensearch"]["cpu"] - 0.25) < 1e-6, f"opensearch must be 0.25 CPU, got {per['opensearch']['cpu']}"
    redpanda = _split_docs(_render_helm("redpanda"))
    main = next(c for d in redpanda if d.get("kind") == "StatefulSet"
                for c in d["spec"]["template"]["spec"]["containers"] if c["name"] == "redpanda")
    assert _parse_cpu(main["resources"]["requests"]["cpu"]) == 0.25
    assert per["redpanda"]["cpu"] >= 0.25  # Includes actual sidecars and init reservations.
    assert abs(per["clickhouse"]["cpu"] - 0.5) < 1e-6, f"clickhouse must be 0.25+0.25=0.5 CPU, got {per['clickhouse']['cpu']}"
    # Mem kept.
    assert per["clickhouse"]["mem_gi"] >= 1.0 - 1e-6, "clickhouse mem must stay 512Mi+512Mi"


def test_infra_releases_rendered_separately() -> None:
    for release in INFRA_RELEASES:
        manifest = _render_helm(release)
        assert manifest.strip(), f"infra release {release} must render"


def _remaining_pvc_gi() -> dict[str, float]:
    """Rendered PVC Gi for every remaining release, including the OCI charts.

    Remaining = not-yet-installed observability/jenkins/agentgateway/llmd.
    Already-live stores (postgres/valkey/redpanda/opensearch/clickhouse/airflow/
    feast/datahub) are in the RECORDED live base, NOT re-added here.
    """
    out: dict[str, float] = {}
    for release in REMAINING_RELEASES:
        out[release] = _pvc_gi(_split_docs(_render_helm(release)))
    out["llmd"] = _pvc_gi(_split_docs(_render_llmd_cached()))
    for name in REMAINING_OCI_RELEASES:
        out[name] = _pvc_gi(_split_docs(_render_helm(name)))
    return out


def test_full_pvc_orphan_adjusted_fits_80gi_ceiling() -> None:
    """Current live baseline plus every remaining rendered claim fits 80 GiB."""
    assert LIVE_PVC_GI == 71.0
    assert abs(ADJUSTED_LIVE_PVC_GI - 71.0) < 1e-6
    per = _remaining_pvc_gi()
    new_total = sum(per.values())
    total = ADJUSTED_LIVE_PVC_GI + new_total
    headroom = PVC_CEILING_GI - total
    assert total <= PVC_CEILING_GI, (
        f"current live PVC {ADJUSTED_LIVE_PVC_GI:.0f}Gi base + remaining-new "
        f"{new_total:.0f}Gi = {total:.0f}Gi exceeds {PVC_CEILING_GI:.0f}Gi ceiling. "
        f"per-release={per} headroom={headroom:.0f}Gi "
        f"(expect pre-fix ~95Gi FAIL; post-fix 79Gi PASS)"
    )
    assert headroom >= 1.0 - 1e-6, (
        f"must keep >=1Gi headroom (fragility: any future claim tips over), "
        f"got headroom={headroom:.1f}Gi total={total:.1f}Gi per={per}"
    )


def test_remaining_pvc_breakdown_telemetry_ephemeral_jenkins_8gi_zero_rest() -> None:
    """Breakdown: prometheus/loki/tempo 0 (ephemeral), jenkins 8Gi kept, rest 0.

    - prometheus 0 via `server.persistentVolume.enabled=false` (real key, helm
      show values prometheus-community/prometheus 29.36.1 server.persistentVolume
      enabled:true default -> emptyDir) + `alertmanager.persistence.enabled=false`
      (real key, alertmanager.persistence enabled:true/size 2Gi default -> emptyDir).
    - loki 0 via `singleBinary.persistence.enabled=false` (real key, helm show
      values grafana/loki 7.3.0 singleBinary.persistence enabled:true/size 10Gi
      default, NO emptyDir fallback -- false alone renders NO data volume) +
      `singleBinary.extraVolumes: [{name: storage, emptyDir: {}}]` /
      `singleBinary.extraVolumeMounts: [{name: storage, mountPath: /var/loki}]`
      (real keys, singleBinary.extraVolumes/extraVolumeMounts: []; live fix for
      CrashLoopBackOff `mkdir /var/loki: read-only file system`; template-proof
      emptyDir volume + mount, VCT None = 0 PVC, readOnlyRootFilesystem true
      kept).
    - tempo 0 via `persistence.enabled=false` (real key, helm show values
      grafana/tempo 1.24.4 persistence enabled:false/size 10Gi default; prior
      values enabled:true/size 4Gi rendered 4Gi VCT).
    - jenkins 8Gi KEPT via chart default `persistence.size=8Gi` (real key, helm
      show values jenkins/jenkins 5.9.68 persistence enabled:true/size 8Gi) —
      controller state for Topic 25, no edit.
    - grafana/alloy/langfuse/agentgateway-family/llmd 0 (defaults already
      ephemeral; grafana persistence.enabled:false, alloy no PVC, langfuse bundled
      stores deploy:false, llmd no claims).
    """
    per = _remaining_pvc_gi()
    assert per["prometheus"] == 0, f"prometheus must be ephemeral 0Gi, got {per['prometheus']}Gi"
    assert per["loki"] == 0, f"loki SingleBinary must be ephemeral 0Gi, got {per['loki']}Gi"
    assert per["tempo"] == 0, f"tempo must be ephemeral 0Gi, got {per['tempo']}Gi"
    assert per["grafana"] == 0, f"grafana must render 0 PVC, got {per['grafana']}Gi"
    assert per["alloy"] == 0, f"alloy must render 0 PVC, got {per['alloy']}Gi"
    assert per["langfuse"] == 0, f"langfuse (bundled stores disabled) must render 0 PVC, got {per['langfuse']}Gi"
    assert per["llmd"] == 0, f"llmd kustomize must render 0 PVC, got {per['llmd']}Gi"
    for name in REMAINING_OCI_RELEASES:
        assert per[name] == 0, f"{name} recorded-zero must be 0, got {per[name]}Gi"
    assert abs(per["jenkins"] - 8.0) < 1e-6, (
        f"jenkins persistence KEPT must render exactly 8Gi (chart default "
        f"persistence.size 8Gi), got {per['jenkins']}Gi"
    )
