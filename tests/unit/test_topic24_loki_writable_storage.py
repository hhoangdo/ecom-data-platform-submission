"""Topic 24 LOCAL loki fix (no lease, client-side only).

LIVE-PROVEN FAILURE (accept live findings): `loki/loki-0` CrashLoopBackOff
`mkdir /var/loki: read-only file system / error initialising module:
ruler-storage`.

Cause: values set `singleBinary.persistence.enabled=false`, which in
grafana/loki 7.3.0 renders NO data volume at all (volumes = tmp/config/
runtime-config/sc-rules-volume only, no /var/loki mount, VCT None),
combined with `readOnlyRootFilesystem: true` (loki.containerSecurityContext).
Prior assumption ("false -> emptyDir") is WRONG for singleBinary in this
chart version (unlike write.persistence.volumeClaimsEnabled=false ->
dataVolumeParameters.emptyDir).

Mechanism verdict (schema source `helm show values grafana/loki --version
7.3.0`):
- (a) CHOSEN: `singleBinary.extraVolumes` (line ~1515) +
  `singleBinary.extraVolumeMounts` (line ~1513) with
  `{name: storage, emptyDir: {}}` mounted at `/var/loki`. Renders
  emptyDir volume + mount, VCT None (0 PVC), readOnlyRootFilesystem stays
  true (mount is writable despite read-only rootfs). Template-proven.
- (b) REJECTED: `singleBinary.persistence.enabled:true` + small size.
  Renders `storage` mount at /var/loki + VCT (functional) BUT breaches
  80Gi: 71Gi adjusted base + 8Gi jenkins + 4Gi = 83Gi (>80); +2Gi = 81Gi
  breach; +1Gi = 80Gi exactly headroom 0 (fails >=1Gi headroom rule).
  Nothing else gives (alertmanager already off; tempo/prom off; jenkins 8
  fixed). Math reported, not breached.
- (c) REJECTED (last resort, not used): `loki.containerSecurityContext.
  readOnlyRootFilesystem:false` exists (line ~117) but weakens container
  hardening and is unnecessary since (a) works. Recorded loudly here.

Method: `helm template loki grafana/loki -n edai2
-f infra/helm/edai2/values/loki.yaml --version 7.3.0 --dry-run=client`
(local chart cache only, no cluster).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES_FILE = ROOT / "infra/helm/edai2/values/loki.yaml"


def _render_loki() -> str:
    cmd = [
        "helm", "template", "loki", "loki",
        "--repo", "https://grafana.github.io/helm-charts",
        "--version", "7.3.0",
        "-n", "edai2",
        "-f", str(VALUES_FILE),
        "--dry-run=client",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, f"helm template loki failed: {proc.stderr[:2000]}"
    return proc.stdout


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


def _loki_statefulset(docs: list[dict]) -> dict:
    found = [
        d for d in docs
        if d.get("kind") == "StatefulSet"
        and ((d.get("metadata") or {}).get("name") == "loki")
    ]
    assert len(found) == 1, f"expected exactly one loki StatefulSet, got {len(found)}"
    return found[0]


def test_loki_var_loki_has_writable_volume() -> None:
    """Rendered loki StatefulSet must mount a WRITABLE /var/loki.

    Accept: emptyDir volume named `storage` mounted at /var/loki (preferred,
    0 PVC) OR a small PVC (<=1Gi) keeping orphan-adjusted total <=80Gi.
    Pre-fix FAIL: no /var/loki mount at all (volumes tmp/config/
    runtime-config/sc-rules-volume only) -> mkdir /var/loki crashes on
    read-only rootfs.
    """
    docs = _split_docs(_render_loki())
    sts = _loki_statefulset(docs)
    pod = (sts.get("spec") or {}).get("template", {}).get("spec", {})
    volumes = {v.get("name"): v for v in (pod.get("volumes") or [])}
    containers = pod.get("containers") or []
    loki_containers = [c for c in containers if c.get("name") == "loki"]
    assert loki_containers, "expected a container named loki"
    mounts = {
        m.get("mountPath"): m.get("name")
        for m in (loki_containers[0].get("volumeMounts") or [])
    }
    assert "/var/loki" in mounts, (
        f"loki container must mount /var/loki (live CrashLoopBackOff "
        f"mkdir /var/loki: read-only file system), got mounts={mounts}"
    )
    vol = volumes.get(mounts["/var/loki"])
    assert vol is not None, f"mount /var/loki refers to missing volume {mounts['/var/loki']!r}"
    if "emptyDir" in vol:
        return  # preferred: 0 PVC, writable despite readOnlyRootFilesystem
    if "persistentVolumeClaim" in vol or vol.get("ephemeral"):
        vct = (sts.get("spec") or {}).get("volumeClaimTemplates") or []
        sizes: list[float] = []
        for claim in vct:
            size = ((((claim.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", ""))
            text = str(size)
            if text.endswith("Gi"):
                sizes.append(float(text[:-2]))
            elif text.endswith("Mi"):
                sizes.append(float(text[:-2]) / 1024.0)
        assert sizes and max(sizes) <= 1.0, (
            f"PVC-backed /var/loki must be <=1Gi to keep 71+8+size<=80Gi, got {sizes}"
        )
        assert 71.0 + 8.0 + sum(sizes) <= 80.0, "PVC math must fit 80Gi ceiling"
        return
    raise AssertionError(
        f"/var/loki volume must be emptyDir (preferred) or small PVC, got {vol!r}"
    )


def test_loki_readonly_rootfs_stays_true() -> None:
    """Container hardening must stay: readOnlyRootFilesystem=true.

    The fix adds a mounted writable /var/loki; it must NOT flip the
    read-only rootfs flag (mechanism (c) rejected).
    """
    docs = _split_docs(_render_loki())
    sts = _loki_statefulset(docs)
    pod = (sts.get("spec") or {}).get("template", {}).get("spec", {})
    loki_containers = [c for c in (pod.get("containers") or []) if c.get("name") == "loki"]
    assert loki_containers, "expected a container named loki"
    sec = (loki_containers[0].get("securityContext") or {})
    assert sec.get("readOnlyRootFilesystem") is True, (
        f"readOnlyRootFilesystem must stay true, got {sec!r}"
    )


def test_loki_single_replica_clusterip_no_large_pvc() -> None:
    """Single-replica + ClusterIP + no new large PVC (<=1Gi, 0 preferred)."""
    docs = _split_docs(_render_loki())
    sts = _loki_statefulset(docs)
    assert (sts.get("spec") or {}).get("replicas") == 1, "loki must stay single-replica"
    services = [
        d for d in docs
        if d.get("kind") == "Service" and ((d.get("metadata") or {}).get("name") == "loki")
    ]
    assert services, "expected Service loki"
    assert (services[0].get("spec") or {}).get("type") == "ClusterIP", (
        f"loki Service must stay ClusterIP, got {(services[0].get('spec') or {}).get('type')!r}"
    )
    total = 0.0
    for doc in docs:
        if doc.get("kind") == "PersistentVolumeClaim":
            size = (((doc.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
            text = str(size)
            if text.endswith("Gi"):
                total += float(text[:-2])
            elif text.endswith("Mi"):
                total += float(text[:-2]) / 1024.0
        if doc.get("kind") == "StatefulSet":
            for claim in (doc.get("spec") or {}).get("volumeClaimTemplates") or []:
                # Count only the loki StatefulSet's claims for this scoped test.
                if ((doc.get("metadata") or {}).get("name") != "loki"):
                    continue
                size = (((claim.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
                text = str(size)
                if text.endswith("Gi"):
                    total += float(text[:-2])
                elif text.endswith("Mi"):
                    total += float(text[:-2]) / 1024.0
    assert total <= 1.0, f"loki rendered PVC must be <=1Gi (0 preferred), got {total}Gi"
