"""Topic 24 LOCAL feast registry/auth fix (bundled redis, TDD RED first).

Proves chart-real wiring for feast 0.45.0 CrashLoops:
- transformation-service stays DISABLED via real key
  `transformation-service.enabled=false` (broken upstream image).
- feature-server online store reverted to the CHART'S BUNDLED redis
  (upstream-tested path, chart-managed credentials, zero user secrets).
  Rationale: official feast docs (java-demo README) show REDIS
  `password: [YOUR PASSWORD]` as a LITERAL consumed VERBATIM by the Java
  server (NO `${ENV}` expansion) -> `password: ${REDIS_PASSWORD}` is sent
  LITERALLY -> live WRONGPASS. No secret-safe path to platform Valkey
  exists (secretKeyRef->env cannot inject into file values; literals
  forbidden). In-repo precedent: values/airflow.yaml keeps chart-bundled
  redis for the Celery broker (self-contained, 1Gi).
- minimal registry generator dir (no binary committed).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FEAST_VALUES = ROOT / "infra/helm/edai2/values/feast.yaml"
REGISTRY_DIR = ROOT / "infra/feast-registry"

BUNDLED_REDIS_HOST = "feast-redis-master"
BUNDLED_REDIS_PORT = 6379

FEAST_RELEASE = "feast"
FEAST_CHART_REF = "feast-charts/feast"
FEAST_VERSION = "0.45.0"


def _load(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} must parse as dict"
    return loaded


def _render() -> str:
    proc = subprocess.run(
        ["helm", "template", FEAST_RELEASE, FEAST_CHART_REF, "--version", FEAST_VERSION,
         "-n", "edai2", "-f", str(FEAST_VALUES), "--dry-run=client"],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, f"helm template failed: {proc.stderr[:2000]}"
    return proc.stdout


def _docs(manifest: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]


def test_transformation_service_disabled_via_real_key() -> None:
    # REAL chart key: umbrella requirements.yaml condition
    # `transformation-service.enabled` (feast/values.yaml `transformation-service.enabled: true`
    # default). Disabled because image
    # `feastdev/feature-transformation-server:0.45.0` CrashLoops image-internally:
    # `feast/transformation_server.py:7` unconditionally imports `grpc_reflection`,
    # absent from base Requires-Dist (packaging bug, also in 0.46.0; no 0.45.x hotfix).
    # Nothing in core consumes transformation-service (no clients, zero feature views).
    # RE-ENABLE CONDITION (exact): set `transformation-service.enabled: true` ONLY when
    # the upstream image ships `grpc_reflection` (fixed transformation-server image tag).
    values = _load(FEAST_VALUES)
    svc = values.get("transformation-service") or {}
    assert svc.get("enabled") is False, \
        "transformation-service.enabled must be false (real chart key; image is broken)"


def test_feature_server_bundled_redis_no_password() -> None:
    # REAL keys: feature-server.application-override.yaml.feast.stores (README
    # example) + feature-server.envOverrides (subchart values envOverrides: {}).
    # Bundled path: host == chart Service feast-redis-master (configmap.yaml
    # hardcodes `host: {{ .Release.Name }}-redis-master`; redis-master-svc.yaml
    # `name: {{ template "redis.fullname" . }}-master` -> feast-redis-master),
    # port 6379, NO password key (redis.usePassword=false -> --protected-mode no,
    # no Secret; secret.yaml `if and .Values.usePassword` renders nothing).
    # Java server consumes config VERBATIM (no ${ENV} expansion) so any
    # `${REDIS_PASSWORD}` placeholder would be sent literally -> WRONGPASS.
    values = _load(FEAST_VALUES)
    override = (values.get("feature-server") or {}).get("application-override.yaml") or {}
    stores = ((override.get("feast") or {}).get("stores") or [])
    assert isinstance(stores, list) and len(stores) == 1, \
        f"override must carry exactly one REDIS store, got {stores!r}"
    assert stores[0].get("type") == "REDIS"
    config = stores[0].get("config") or {}
    assert config.get("host") == BUNDLED_REDIS_HOST, \
        f"online host must be bundled {BUNDLED_REDIS_HOST!r}, got {config.get('host')!r}"
    assert config.get("port") == BUNDLED_REDIS_PORT
    assert "password" not in config, \
        f"bundled redis (usePassword=false) must carry NO password key, got {config!r}"
    overrides = (values.get("feature-server") or {}).get("envOverrides") or {}
    assert "REDIS_PASSWORD" not in overrides, \
        "bundled path must NOT wire REDIS_PASSWORD env (no user secret)"


def test_feast_has_no_valkey_wiring() -> None:
    # Valkey platform path abandoned for feast: no secret-safe injection into
    # file values exists. Values (comments stripped) + raw text must carry ZERO
    # valkey refs and ZERO ${REDIS_PASSWORD} placeholder.
    values = _load(FEAST_VALUES)
    dumped = yaml.safe_dump(values)
    assert "valkey" not in dumped.lower(), \
        f"feast values must carry ZERO valkey refs, got {dumped[:500]!r}"
    assert "${REDIS_PASSWORD}" not in dumped, \
        "feast values must carry ZERO ${REDIS_PASSWORD} placeholder (verbatim WRONGPASS)"
    raw = FEAST_VALUES.read_text(encoding="utf-8")
    # Raw scan would hit comments documenting the abandoned path; enforce on
    # parsed dump (real wiring) + forbid secretKeyRef-to-valkey in parsed tree.
    def _walk(node: object) -> list[str]:
        hits: list[str] = []
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, dict) and "secretKeyRef" in v:
                    ref = v.get("secretKeyRef") or {}
                    if isinstance(ref, dict) and ref.get("name") == "valkey":
                        hits.append(f"{k}->valkey")
                hits.extend(_walk(v))
        elif isinstance(node, list):
            for item in node:
                hits.extend(_walk(item))
        return hits
    assert not _walk(values), f"feast must carry NO secretKeyRef-to-valkey, got {_walk(values)!r}"


def test_registry_generator_dir() -> None:
    assert (REGISTRY_DIR / "feature_store.yaml").is_file(), "generator feature_store.yaml missing"
    assert (REGISTRY_DIR / "entities.py").is_file(), "generator entities.py missing"
    assert (REGISTRY_DIR / "generate.py").is_file(), "generator generate.py missing"
    assert (REGISTRY_DIR / "README.md").is_file(), "generator README.md missing"
    assert not (REGISTRY_DIR / "registry.db").exists(), "must NOT commit binary registry.db"
    fs = _load(REGISTRY_DIR / "feature_store.yaml")
    assert fs.get("project") == "default", "generator project must match chart global.project default"
    assert fs.get("provider") == "local", "generator provider must be local"
    dumped = yaml.safe_dump(fs)
    assert "gs://" not in dumped, "generator must carry ZERO GCS"
    entities = (REGISTRY_DIR / "entities.py").read_text(encoding="utf-8")
    assert "Entity" in entities, "generator must define one entity"
    assert "FeatureView" not in entities, "generator must define ZERO feature views (honest empty state)"
    gen = (REGISTRY_DIR / "generate.py").read_text(encoding="utf-8")
    assert "feast apply" in gen.lower() or "FeatureStore" in gen, "generate.py must run feast apply"
    assert "REGISTRY_BASE64" in gen, "generate.py must document REGISTRY_BASE64"
    assert "registry.db" in gen, "generate.py must reference registry.db"


def test_render_transformation_absent_when_disabled() -> None:
    # Same re-enable condition as above: upstream image with grpc_reflection present.
    docs = _docs(_render())
    for doc in docs:
        name = str((doc.get("metadata") or {}).get("name", ""))
        assert "transformation" not in name, \
            f"disabled transformation-service must render ZERO workloads, got {doc.get('kind')}/{name}"


def test_bundled_redis_enabled_ephemeral_via_real_keys() -> None:
    # REAL umbrella keys (feast Chart.yaml condition `redis.enabled`, feast
    # values.yaml `redis:{enabled,usePassword}`, stable/redis 10.5.6 values):
    # - redis.enabled=true (default false) installs the bundled subchart.
    # - redis.usePassword=false (subchart default true; umbrella default false)
    #   -> no auth, no Secret, chart-managed (nothing for user to supply).
    # - redis.cluster.enabled=false (subchart default true, slaveCount 2) ->
    #   single master only (slave-statefulset `if .Values.cluster.enabled`).
    # - redis.master.persistence.enabled=false (subchart default true 8Gi;
    #   master-statefulset 361-382 `if .Values.master.persistence.enabled`
    #   guards volumeClaimTemplates, else emptyDir) -> ZERO PVC, ephemeral
    #   online cache. slave persistence likewise disabled (moot when cluster
    #   off, kept explicit).
    values = _load(FEAST_VALUES)
    redis = values.get("redis") or {}
    assert redis.get("enabled") is True, \
        "redis.enabled must be true (real umbrella condition key; bundled path)"
    assert redis.get("usePassword") is False, \
        "redis.usePassword must be false (real key; no auth, chart-managed)"
    cluster = redis.get("cluster") or {}
    assert cluster.get("enabled") is False, \
        "redis.cluster.enabled must be false (real key; single master, minimal footprint)"
    master_p = (redis.get("master") or {}).get("persistence") or {}
    assert master_p.get("enabled") is False, \
        "redis.master.persistence.enabled must be false (real key; ephemeral emptyDir, ZERO PVC)"
    slave_p = (redis.get("slave") or {}).get("persistence") or {}
    assert slave_p.get("enabled") is False, \
        "redis.slave.persistence.enabled must be false (real key; explicit, moot when cluster off)"


def test_render_bundled_redis_no_valkey_no_placeholder() -> None:
    docs = _docs(_render())
    for doc in docs:
        if doc.get("kind") != "Deployment":
            continue
        name = str((doc.get("metadata") or {}).get("name"))
        if "feature-server" not in name:
            continue
        pod = (doc.get("spec") or {}).get("template", {}).get("spec", {})
        for container in pod.get("containers", []):
            for env in container.get("env") or []:
                assert env.get("name") != "REDIS_PASSWORD", \
                    "rendered feature-server must NOT carry REDIS_PASSWORD env (bundled, no auth)"
                ref = ((env.get("valueFrom") or {}).get("secretKeyRef") or {})
                assert ref.get("name") != "valkey", \
                    f"rendered feature-server must NOT secretKeyRef valkey, got {ref!r}"
    manifest = _render()
    assert BUNDLED_REDIS_HOST in manifest, \
        f"render must reference bundled {BUNDLED_REDIS_HOST}"
    assert "valkey-primary" not in manifest, \
        "render must carry ZERO valkey refs (platform path abandoned)"
    assert "${REDIS_PASSWORD}" not in manifest, \
        "render must carry ZERO ${REDIS_PASSWORD} placeholder (verbatim WRONGPASS)"
    assert "gs://" not in manifest


def test_render_images_and_no_registry_literal() -> None:
    docs = _docs(_render())
    images = set()
    for doc in docs:
        if doc.get("kind") == "Deployment":
            for container in (doc.get("spec") or {}).get("template", {}).get("spec", {}).get("containers", []):
                if container.get("image"):
                    images.add(container["image"])
    assert "feastdev/feature-server-java:0.45.0" in images
    # transformation-service.enabled=false -> its broken image must NOT render.
    # Re-enable ONLY with fixed upstream image (grpc_reflection present).
    assert "feastdev/feature-transformation-server:0.45.0" not in images, \
        "disabled transformation image must be absent from render"


# PATH A (secrets-loop mount): feature-server delivers registry.db via the
# chart-real `feature-server.secrets` loop mounting pre-created Secret
# `feast-registry` at /etc/secrets/feast-registry, with
# global.registry.path pointing at the mounted file.
def test_feature_server_secrets_references_precreated_registry() -> None:
    values = _load(FEAST_VALUES)
    secrets = (values.get("feature-server") or {}).get("secrets") or []
    assert "feast-registry" in secrets, \
        "feature-server.secrets must mount pre-created Secret feast-registry"


def test_global_registry_path_points_at_secrets_mount() -> None:
    # URI-vs-path fix: chart re-emits global.registry.path VERBATIM into JVM config
    # (feature-server/templates/configmap.yaml:16 + :40 `registry: {{ .Values.global.registry.path }}`),
    # and feast 0.45.0 LocalRegistryFile.java:38 passes the FULL string to Paths.get() —
    # `Paths.get("file:///etc/...")` normalizes to literal `file:/etc/...` -> NoSuchFileException.
    # FIX: plain absolute path (no scheme); dirname must equal secrets-mount path.
    values = _load(FEAST_VALUES)
    path = ((values.get("global") or {}).get("registry") or {}).get("path") or ""
    assert path == "/etc/secrets/feast-registry/registry.db", \
        f"global.registry.path must be plain absolute path at secrets mount, got {path!r}"
    assert not path.startswith("file://") and path.startswith("/"), \
        f"registry path must be scheme-less absolute, got {path!r}"
    import posixpath as _p
    assert _p.dirname(path) == "/etc/secrets/feast-registry", \
        f"registry dirname must equal secrets mountPath, got {_p.dirname(path)!r}"


def test_render_feature_server_registry_mount_aligned() -> None:
    docs = _docs(_render())
    found_volume = found_mount = False
    registry_value = ""
    for doc in docs:
        if doc.get("kind") == "ConfigMap":
            data = doc.get("data") or {}
            override = data.get("application-override.yaml") or ""
            for line in override.splitlines():
                s = line.strip()
                if s.startswith("registry:"):
                    registry_value = s.split(":", 1)[1].strip()
        if doc.get("kind") != "Deployment":
            continue
        name = str((doc.get("metadata") or {}).get("name"))
        if "feature-server" not in name:
            continue
        pod = (doc.get("spec") or {}).get("template", {}).get("spec", {})
        for vol in pod.get("volumes") or []:
            secret = (vol.get("secret") or {}).get("secretName")
            if secret == "feast-registry":
                found_volume = True
        for container in pod.get("containers", []):
            for mount in container.get("volumeMounts") or []:
                if mount.get("mountPath") == "/etc/secrets/feast-registry":
                    found_mount = True
    assert found_volume, "rendered feature-server must carry volume secretName feast-registry"
    assert found_mount, "rendered feature-server must mount at /etc/secrets/feast-registry"
    assert registry_value == "/etc/secrets/feast-registry/registry.db", \
        f"registry dirname must equal secrets mountPath, got {registry_value!r}"
    assert not registry_value.startswith("file://"), \
        f"rendered registry must be plain path (no scheme), got {registry_value!r}"


def test_render_registry_delivery_has_no_literals() -> None:
    manifest = _render()
    assert "gs://" not in manifest, "render must carry ZERO gs://"
    assert "file://" not in manifest, "render must carry ZERO file:// (plain path fix)"
    assert "/etc/secrets/feast-registry/registry.db" in manifest
    assert "file:///etc/feast/registry.db" not in manifest, \
        "old BLOCKED placeholder path must be gone"
    assert "file:///etc/secrets/feast-registry/registry.db" not in manifest, \
        "scheme-prefixed registry path must be gone (URI-vs-path fix)"
    dumped_values = FEAST_VALUES.read_text(encoding="utf-8")
    # Comments may document the old file:// path + Java Paths.get bug; scan parsed
    # values (comments stripped) for a REAL registry string.
    import io as _io2  # local import to avoid top-level churn
    parsed_dump = yaml.safe_dump(_load(FEAST_VALUES))
    assert "file://" not in parsed_dump, "feast values must carry ZERO file:// registry string"
    docs = _docs(manifest)
    for doc in docs:
        if doc.get("kind") == "Deployment":
            name = str((doc.get("metadata") or {}).get("name"))
            pod = (doc.get("spec") or {}).get("template", {}).get("spec", {})
            for container in pod.get("containers", []):
                for env in container.get("env") or []:
                    assert "value" not in env or "REGISTRY_BASE64" not in str(env.get("name")), \
                        "REGISTRY_BASE64 must be secretKeyRef, never literal"
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services and all((d.get("spec") or {}).get("type") == "ClusterIP" for d in services), \
        "all Services must stay ClusterIP"
    deployments = [d for d in docs if d.get("kind") == "Deployment"]
    assert deployments and all((d.get("spec") or {}).get("replicas") == 1 for d in deployments), \
        "all Deployments must stay single-replica"


def test_generate_py_emits_secret_mount_key() -> None:
    gen = (REGISTRY_DIR / "generate.py").read_text(encoding="utf-8")
    assert "REGISTRY_BASE64" in gen, "generate.py must emit REGISTRY_BASE64"
    assert "registry.db" in gen, "generate.py must reference registry.db bytes"
    code_lines = [ln for ln in gen.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert not any(ln.strip() == "store.apply([])" for ln in code_lines), \
        "generate.py must NOT apply an empty list (writes zero-entity registry)"
    assert "store.apply(repo_entities)" in gen, \
        "generate.py must apply the repo entities"
    assert "registry.db: " in gen and "REGISTRY_BASE64: " in gen, \
        "generate.py must emit both data.registry.db and stringData.REGISTRY_BASE64 keys"


def test_no_sql_registry_wiring() -> None:
    # PATH B guard: chart 0.45.0 has NO SQL-registry support; values + render
    # must carry ZERO registry_type/sql/jdbc/postgres keys (setting them is fake).
    # Comments may name platform hosts to document the non-wiring; scan the
    # parsed values (comments stripped) instead of raw text.
    import io as _io

    values = _load(FEAST_VALUES)
    dumped = yaml.safe_dump(values).lower()
    for token in ("registry_type", "jdbc:", "postgresql://", "postgres-postgresql"):
        assert token not in dumped, f"feast values must not fake SQL wiring via {token!r}"
    manifest = _render().lower()
    for token in ("registry_type", "jdbc:", "postgresql://"):
        assert token not in manifest, f"render must not carry SQL registry token {token!r}"


def _parse_gi(size: str) -> float:
    assert size.endswith("Gi"), f"expected Gi size, got {size!r}"
    return float(size[:-2])


def test_bundled_redis_footprint_and_capacity_headroom() -> None:
    # Footprint (helm template proof): 1 Deployment (feature-server) +
    # 1 StatefulSet (feast-redis-master, single master since cluster.enabled=false)
    # + master Service + headless Service; ZERO slave workloads; ZERO new PVCs
    # (emptyDir). Capacity: live Bound 69Gi edai2 + 10Gi vault = 79Gi; ceiling
    # 80Gi -> headroom 1Gi. Rendered NEW claim sizes must be <=1Gi (here 0Gi).
    import re as _re
    docs = _docs(_render())
    kinds = [d.get("kind") for d in docs]
    assert "StatefulSet" in kinds, "bundled redis master StatefulSet must render"
    names = [str((d.get("metadata") or {}).get("name", "")) for d in docs]
    assert any("redis-master" in n for n in names), \
        f"expected feast-redis-master workload/service, got {sorted(names)!r}"
    assert not any("redis-slave" in n for n in names), \
        f"cluster.enabled=false must render ZERO slave workloads, got {sorted(names)!r}"
    # Persistence disabled-or-<=1Gi via REAL keys (values-level guard lives in
    # test_bundled_redis_enabled_ephemeral_via_real_keys; here prove render).
    new_claim_gi = 0.0
    for doc in docs:
        if doc.get("kind") == "PersistentVolumeClaim":
            size = (((doc.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
            new_claim_gi += _parse_gi(str(size))
        if doc.get("kind") in ("StatefulSet",):
            for claim in (doc.get("spec") or {}).get("volumeClaimTemplates") or []:
                size = (((claim.get("spec") or {}).get("resources") or {}).get("requests") or {}).get("storage", "")
                if size:
                    # Values-level test already forces ephemeral; any rendered
                    # claim must still fit headroom.
                    assert _parse_gi(str(size)) <= 1, \
                        f"bundled redis claim {size!r} exceeds 1Gi headroom"
                    new_claim_gi += _parse_gi(str(size))
    assert new_claim_gi <= 1, \
        f"rendered NEW claim sizes must be <=1Gi (79Gi live + new <=80Gi), got {new_claim_gi}Gi"
    # Values-level persistence sizes (if ever re-enabled) must also fit.
    values = _load(FEAST_VALUES)
    redis = values.get("redis") or {}
    for section in ("master", "slave"):
        p = (redis.get(section) or {}).get("persistence") or {}
        if p.get("enabled") is True:
            assert _parse_gi(str(p.get("size", "8Gi"))) <= 1, \
                f"redis.{section}.persistence.size must be <=1Gi when enabled, got {p.get('size')!r}"


# EDAI2 Topic 24 — LOCAL feast redis-image fix (bitnami purge, NO lease).
# Chart-key rationale (verified via pulled chart metadata-only):
# - feast 0.45.0 bundles stable/redis 10.5.6 (feast/Chart.yaml
#   `name: redis version: 10.5.6 repository: https://charts.helm.sh/stable`,
#   condition redis.enabled). Subchart values.yaml top-level `image:`
#   `{registry: docker.io, repository: bitnami/redis,
#   tag: 5.0.7-debian-10-r32, pullPolicy: IfNotPresent}`.
# - Helper `redis.image` (charts/redis/templates/_helpers.tpl:70-85)
#   renders `"%s/%s:%s" registry/repository:tag`
#   (registry=.Values.image.registry, repo=.Values.image.repository,
#   tag=.Values.image.tag; global.imageRegistry override absent here).
#   Consumers: redis-master-statefulset.yaml:71
#   `image: "{{ template "redis.image" . }}"` (+ slave :77 when enabled).
# - Hence the ONLY real override keys under the umbrella are
#   `redis.image.repository` + `redis.image.tag`
#   (optionally `redis.image.registry`, default docker.io — left unset).
#   `redis.master.image.*` does NOT exist (no such path in subchart
#   values/templates); `redis.image.repository/tag` cited exactly, not assumed.
# Chosen tag: 5.0.7-r56 under `bitnamilegacy/redis`
# - WHY newest rN of same 5.0.7: same upstream redis 5.0.7 + Bitnami layout
#   (/run.sh entrypoint, /opt/bitnami paths) as the purged
#   `bitnami/redis:5.0.7-debian-10-r32`; only the revision-naming changed
#   (`-debian-10-r32` suffix dropped, `-rN` retained). Closest possible
#   fidelity without crossing majors (6.2.x/8.x forbidden silently;
#   official `redis:7.2` lacks Bitnami layout for run.sh).
# - EXISTENCE evidence (Docker Hub API, 2026-10-09):
#   `bitnamilegacy/redis` tags `?name=5.0.7` count=53, next=null;
#   numeric-max + latest last_updated is `5.0.7-r56`
#   (last_updated 2025-07-18T10:53:08.277763Z,
#   digest sha256:a5068e1175505ff69c3f096e62a8280d0b8e986c3d04c754c9b3af984a5c8bfa);
#   `?name=5.0.7-debian-10` count=0 (NO -debian-10-suffixed 5.0.7 tags exist);
#   `bitnami/redis` `?name=5.0.7-debian-10-r32` count=0 (bundled tag GONE).
#   Live pullability remains live-provable only (kubelet pull proves
#   retrievability; API proves existence only).
EXPECTED_REDIS_REPOSITORY = "bitnamilegacy/redis"
EXPECTED_REDIS_TAG = "5.0.7-r56"
EXPECTED_REDIS_IMAGE = "docker.io/bitnamilegacy/redis:5.0.7-r56"
EXPECTED_FULL_IMAGE_SET = frozenset({
    "feastdev/feature-server-java:0.45.0",
    EXPECTED_REDIS_IMAGE,
})


def test_redis_image_override_uses_real_subchart_keys() -> None:
    # REAL keys: redis.image.repository + redis.image.tag (stable/redis 10.5.6
    # values.yaml `image:` block + _helpers.tpl `redis.image` triple).
    # `redis.master.image.*` must NOT exist. Registry stays default docker.io
    # (unset) so the edit is repository+tag ONLY.
    values = _load(FEAST_VALUES)
    redis = values.get("redis") or {}
    image = redis.get("image") or {}
    assert image.get("repository") == EXPECTED_REDIS_REPOSITORY, \
        f"redis.image.repository must be {EXPECTED_REDIS_REPOSITORY!r}, got {image.get('repository')!r}"
    assert str(image.get("tag")) == EXPECTED_REDIS_TAG, \
        f"redis.image.tag must be {EXPECTED_REDIS_TAG!r}, got {image.get('tag')!r}"
    assert "master" not in redis or "image" not in (redis.get("master") or {}), \
        "redis.master.image.* must NOT exist (fake key; real keys are redis.image.*)"


def test_render_redis_statefulset_image_exact() -> None:
    docs = _docs(_render())
    sts = [d for d in docs if d.get("kind") == "StatefulSet"
           and "redis-master" in str((d.get("metadata") or {}).get("name", ""))]
    assert len(sts) == 1, \
        f"expected exactly one feast-redis-master StatefulSet, got {[str((d.get('metadata') or {}).get('name')) for d in docs if d.get('kind') == 'StatefulSet']!r}"
    containers = ((sts[0].get("spec") or {}).get("template", {}).get("spec", {}).get("containers", []))
    assert containers and containers[0].get("image") == EXPECTED_REDIS_IMAGE, \
        f"redis StatefulSet image must be {EXPECTED_REDIS_IMAGE!r}, got {(containers[0].get('image') if containers else None)!r}"


def test_render_zero_bitnami_and_zero_latest() -> None:
    manifest = _render()
    assert "docker.io/bitnami/redis" not in manifest, \
        "render must carry ZERO docker.io/bitnami/redis refs (purged tag)"
    # `bitnami/redis` (no registry prefix) would also match the purged path;
    # `bitnamilegacy/redis` does NOT contain substring `bitnami/redis`, so this
    # guard stays green after the fix while catching any rollback.
    assert "bitnami/redis:" not in manifest.replace("bitnamilegacy/redis:", ""), \
        "render must carry ZERO bitnami/redis refs"
    assert ":latest" not in manifest, \
        "render must carry ZERO :latest tags"


def test_render_full_image_list_no_drift() -> None:
    # Full rendered image list (Deployments + StatefulSets only — the only
    # workload kinds this chart renders with containers). Records NO other
    # image drift: exactly feature-server-java:0.45.0 + fixed redis image.
    docs = _docs(_render())
    images: set[str] = set()
    for doc in docs:
        if doc.get("kind") in ("Deployment", "StatefulSet"):
            pod = (doc.get("spec") or {}).get("template", {}).get("spec", {})
            for container in pod.get("containers", []) or []:
                if container.get("image"):
                    images.add(str(container["image"]))
            for container in pod.get("initContainers", []) or []:
                if container.get("image"):
                    images.add(str(container["image"]))
    assert images == set(EXPECTED_FULL_IMAGE_SET), \
        f"full rendered image list drifted, expected {sorted(EXPECTED_FULL_IMAGE_SET)!r}, got {sorted(images)!r}"
