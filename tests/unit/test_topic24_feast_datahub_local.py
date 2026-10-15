"""Topic 24 LOCAL feast+datahub platform wiring (no lease, client-side only).

PROBLEM A (live-proven, feast 0.45.0): feature-server CrashLoops
`MismatchedInputException: No content to map` (empty ApplicationProperties
from placeholder `gs://path/to/registry.db`) + transformation-service 403
on that bucket. Stub values/feast.yaml is a 4-line STUB whose top-level
keys (`service`, `postgres`, `valkey`, `resources`) do NOT exist in the real
chart (`helm show values feast-charts/feast --version 0.45.0` has ONLY
`feature-server`, `transformation-service`, `redis`, `global`).

Chart proof (pulled chart, metadata/template reads only):
- feast/values.yaml 14-23: ONLY `global.registry.path`
  (default `gs://path/to/registry.db`), `global.registry.cache_ttl_seconds`,
  `global.project`. NO postgres/offline keys anywhere.
- charts/feature-server/templates/configmap.yaml 13-34: generated config
  renders ONLY `feast.registry` (= global.registry.path),
  `transformationServiceEndpoint`, `activeStore: online`,
  `stores: [{name: online, type: REDIS, config: {host: <release>-redis-master,
  port: 6379}}]`. Online host is HARDCODED to bundled redis; NO password
  field; NO postgres/offline branch.
- charts/transformation-service/config/feature_store.yaml 1-5: ONLY
  `registry.path`, `provider: local`, `project`. NO offline store.
- charts/feature-server/values.yaml + README example: the ONLY documented
  online-store remap is `feature-server.application-override.yaml.feast.stores`
  (REDIS host/port). Used here to point at the CHART'S BUNDLED redis
  `feast-redis-master:6379` (upstream-tested path, chart-managed creds).
  Platform-valkey path ABANDONED: Java server consumes config VERBATIM (no
  `${ENV}` expansion; official java-demo README shows `password: [YOUR PASSWORD]`
  as a LITERAL) -> `password: ${REDIS_PASSWORD}` is sent literally -> WRONGPASS.
  No secret-safe injection into file values exists (secretKeyRef->env cannot
  inject; literals forbidden). In-repo precedent: values/airflow.yaml keeps
  chart-bundled redis for the Celery broker (self-contained, 1Gi).
结论: registry + offline CANNOT be wired to platform postgres (file-registry
chart; no DB keys). SQL path STOPPED (see PATH B verdict in the registry-delivery
investigation). Online uses BUNDLED redis via the documented override
(redis.enabled=true, usePassword=false, cluster off, persistence off);
generated config stays disabled to drop the GCS default (it ALSO hardcodes
feast-redis-master, but the override is the single source of truth).
Registry file IS delivered via PATH A: the chart-real
`feature-server.secrets` loop mounts pre-created Secret `feast-registry` at
`/etc/secrets/feast-registry`, and `global.registry.path` names the mounted
`registry.db` (helm template proof: dirname == mountPath, ZERO `gs://`).

PROBLEM B (datahub 1.1.6): defaults target `prerequisites-mysql/kafka`
(separate release NOT installed) + bundled-ES-style search. Wired here via
REAL keys (all in `helm show values datahub/datahub --version 1.1.6`):
- global.sql.datasource.{host,port,url,driver,database,username.secretRef/
  secretKey,password.secretRef/secretKey}: GMS deployment renders
  EBEAN_DATASOURCE_* with secretKeyRef when username/password are maps
  (subcharts/datahub-gms/templates/deployment.yaml EBEAN blocks) + the
  commented `## Use below for usage of PostgreSQL` block documents
  `jdbc:postgresql://...` + `org.postgresql.Driver`.
- global.kafka.bootstrap.server -> KAFKA_BOOTSTRAP_SERVER (same deployment).
- global.elasticsearch.host/port -> ELASTICSEARCH_HOST/PORT (same).
- datahub-gms.service.type + datahub-frontend.service.type = ClusterIP:
  both subcharts default LoadBalancer (subcharts/*/values.yaml
  `service.type: LoadBalancer`); private core forbids it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FEAST_VALUES = ROOT / "infra/helm/edai2/values/feast.yaml"
DATAHUB_VALUES = ROOT / "infra/helm/edai2/values/datahub.yaml"
POSTGRES_ES = ROOT / "infra/security/external-secrets/postgres.yaml"

FEAST_RELEASE = "feast"
FEAST_CHART_REF = "feast-charts/feast"
FEAST_VERSION = "0.45.0"

DATAHUB_RELEASE = "datahub"
DATAHUB_CHART_REF = "datahub/datahub"
DATAHUB_VERSION = "1.1.6"

# Real top-level keys per `helm show values` (see module docstring).
FEAST_ALLOWED_TOP = {"feature-server", "transformation-service", "redis", "global"}
DATAHUB_ALLOWED_TOP = {
    "datahub-gms",
    "datahub-frontend",
    "acryl-datahub-actions",
    "datahub-mae-consumer",
    "datahub-mce-consumer",
    "datahub-ingestion-cron",
    "elasticsearchSetupJob",
    "kafkaSetupJob",
    "mysqlSetupJob",
    "postgresqlSetupJob",
    "datahubUpgrade",
    "datahubSystemUpdate",
    "datahubSystemCronHourly",
    "global",
}

PLATFORM_POSTGRES_HOST = "postgres-postgresql.edai2"
PLATFORM_POSTGRES_PORT = "5432"
PLATFORM_POSTGRES_URL = "jdbc:postgresql://postgres-postgresql.edai2:5432/datahub"
PLATFORM_POSTGRES_DRIVER = "org.postgresql.Driver"
PLATFORM_POSTGRES_DB = "datahub"
POSTGRES_SECRET = "postgres"

PLATFORM_KAFKA_SERVER = "redpanda.edai2:9093"

PLATFORM_ES_HOST = "opensearch-cluster-master.edai2"
PLATFORM_ES_PORT = "9200"

FEAST_REGISTRY_PATH = "/etc/secrets/feast-registry/registry.db"
FEAST_REGISTRY_SECRET = "feast-registry"
FEAST_BUNDLED_HOST = "feast-redis-master"

_SIZE_RE = re.compile(r"^(\d+)Gi$")
_IMAGE_RE = re.compile(r"^\s*image:\s*[\"']?([^\"'\s]+)", re.MULTILINE)


def _load(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} must parse as a dict"
    return loaded


def _render(release: str, chart_ref: str, version: str, values: Path) -> str:
    proc = subprocess.run(
        ["helm", "template", release, chart_ref, "--version", version,
         "-n", "edai2", "-f", str(values), "--dry-run=client"],
        capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, f"helm template {release} failed: {proc.stderr[:2000]}"
    return proc.stdout


def _docs(manifest: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]


def _walk_literals(node: object, path: str, violations: list[str]) -> None:
    if isinstance(node, dict):
        for key, val in node.items():
            lkey = str(key).lower()
            # ${ENV} placeholders are secret REFS (Spring resolves from env
            # secretKeyRef), NOT literals. Allowlist them.
            is_placeholder = isinstance(val, str) and re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", val) is not None
            if lkey in {"password", "pass", "passwd"} and isinstance(val, str) and val:
                if not is_placeholder:
                    violations.append(f"{path}.{key}={val!r}")
            elif "password" in lkey and lkey not in {"secretkey", "secretkeys", "secretref"}:
                if isinstance(val, str) and val and val not in {"password"} and not is_placeholder:
                    violations.append(f"{path}.{key}={val!r}")
            if key == "value" and isinstance(val, str) and "://" in val and "@" in val:
                userinfo = val.split("://", 1)[1].split("@", 1)[0]
                if ":" in userinfo and not re.fullmatch(r"[^:]+:\$\([A-Za-z_][A-Za-z0-9_]*\)", userinfo):
                    violations.append(f"{path}.{key} carries password userinfo: {val!r}")
            _walk_literals(val, f"{path}.{key}", violations)
    elif isinstance(node, list):
        for idx, item in enumerate(node):
            _walk_literals(item, f"{path}[{idx}]", violations)


# --- feast values shape ---


def test_feast_values_top_level_keys_real() -> None:
    values = _load(FEAST_VALUES)
    unknown = set(values) - FEAST_ALLOWED_TOP
    assert not unknown, f"feast unknown top-level keys (stub keys?): {sorted(unknown)}"


def test_feast_values_has_no_stub_store_keys() -> None:
    values = _load(FEAST_VALUES)
    assert "postgres" not in values, "stub `postgres` key does not exist in feast chart"
    assert "valkey" not in values, "stub `valkey` key does not exist in feast chart"
    assert "service" not in values, "stub top-level `service` does not exist (use feature-server/transformation-service.service)"
    assert "resources" not in values, "stub top-level `resources` does not exist (use per-service resources)"


def test_feast_values_has_real_service_types() -> None:
    values = _load(FEAST_VALUES)
    assert ((values.get("feature-server") or {}).get("service") or {}).get("type") == "ClusterIP"
    # transformation-service.enabled=false (real key; broken image) -> its service block
    # is intentionally absent (disabled subchart renders nothing). Re-enable ONLY with
    # fixed upstream image (grpc_reflection present).
    tsvc = values.get("transformation-service") or {}
    assert tsvc.get("enabled") is False, "transformation-service.enabled must be false"
    if "service" in tsvc:
        assert (tsvc.get("service") or {}).get("type") == "ClusterIP"


def test_feast_values_has_single_replica() -> None:
    values = _load(FEAST_VALUES)
    assert (values.get("feature-server") or {}).get("replicaCount") == 1
    # transformation disabled (see above); replicaCount only matters when enabled.
    tsvc = values.get("transformation-service") or {}
    assert tsvc.get("enabled") is False
    if "replicaCount" in tsvc:
        assert tsvc.get("replicaCount") == 1


def test_feast_registry_is_blocked_file_placeholder() -> None:
    # PATH A delivery: secrets-loop mount of pre-created Secret feast-registry.
    # URI-vs-path fix: plain absolute path (no file:// scheme) — chart re-emits verbatim
    # (configmap.yaml:16+:40) and Java Paths.get() chokes on scheme prefix.
    values = _load(FEAST_VALUES)
    path = ((values.get("global") or {}).get("registry") or {}).get("path")
    assert path == FEAST_REGISTRY_PATH, f"global.registry.path must be {FEAST_REGISTRY_PATH!r}, got {path!r}"
    assert isinstance(path, str) and path.startswith("/") and "://" not in path, \
        f"registry path must be scheme-less absolute, got {path!r}"
    secrets = (values.get("feature-server") or {}).get("secrets") or []
    assert FEAST_REGISTRY_SECRET in secrets, \
        f"feature-server.secrets must mount {FEAST_REGISTRY_SECRET!r}"


def test_feast_online_store_is_bundled_redis() -> None:
    # Bundled path (upstream-tested, chart-managed creds): host == chart Service
    # feast-redis-master (configmap.yaml hardcodes {{ .Release.Name }}-redis-master;
    # redis-master-svc.yaml fullname-master), port 6379, NO password key
    # (redis.usePassword=false -> --protected-mode no). Java server consumes
    # config VERBATIM (no ${ENV} expansion) so platform-valkey password
    # placeholder would be sent literally -> WRONGPASS (abandoned).
    values = _load(FEAST_VALUES)
    override = (values.get("feature-server") or {}).get("application-override.yaml") or {}
    feast = override.get("feast") or {}
    stores = feast.get("stores") or []
    assert isinstance(stores, list) and len(stores) == 1
    assert stores[0].get("type") == "REDIS"
    assert (stores[0].get("config") or {}).get("host") == FEAST_BUNDLED_HOST
    assert (stores[0].get("config") or {}).get("port") == 6379
    assert "password" not in (stores[0].get("config") or {}), \
        "bundled redis must carry NO password key (usePassword=false)"
    gen = (values.get("feature-server") or {}).get("application-generated.yaml") or {}
    # Generated config ALSO hardcodes feast-redis-master (configmap.yaml 28-30)
    # but ALSO re-emits the GCS default registry path; disabled so the override
    # (bundled host + mounted registry path) is the single source of truth.
    assert gen.get("enabled") is False, "generated config must stay disabled (GCS default)"
    redis = values.get("redis") or {}
    assert redis.get("enabled") is True, "redis.enabled must be true (real umbrella key)"
    assert redis.get("usePassword") is False, "redis.usePassword must be false (real key)"
    assert ((redis.get("cluster") or {}).get("enabled") is False), \
        "redis.cluster.enabled must be false (real key; single master)"
    assert (((redis.get("master") or {}).get("persistence") or {}).get("enabled") is False), \
        "redis.master.persistence.enabled must be false (real key; ephemeral)"
    assert (((redis.get("slave") or {}).get("persistence") or {}).get("enabled") is False), \
        "redis.slave.persistence.enabled must be false (real key)"
    overrides = (values.get("feature-server") or {}).get("envOverrides") or {}
    assert "REDIS_PASSWORD" not in overrides, "no REDIS_PASSWORD env for bundled path"
    dumped = yaml.safe_dump(values)
    assert "valkey" not in dumped.lower(), "feast values must carry ZERO valkey refs"
    assert "${REDIS_PASSWORD}" not in dumped, "feast values must carry ZERO placeholder"


def test_feast_values_contains_no_literal_credential() -> None:
    violations: list[str] = []
    _walk_literals(_load(FEAST_VALUES), "$", violations)
    assert not violations, f"literal credential in feast.yaml: {violations}"


def test_feast_values_contains_no_gcs() -> None:
    dumped = yaml.safe_dump(_load(FEAST_VALUES))
    assert "gs://" not in dumped, "feast.yaml values must carry ZERO GCS dependency"


# --- feast render proofs ---


def test_feast_render_exit_zero() -> None:
    assert isinstance(_render(FEAST_RELEASE, FEAST_CHART_REF, FEAST_VERSION, FEAST_VALUES), str)


def test_feast_render_has_bundled_redis_no_gcs_no_valkey() -> None:
    manifest = _render(FEAST_RELEASE, FEAST_CHART_REF, FEAST_VERSION, FEAST_VALUES)
    assert "gs://" not in manifest, "render must carry ZERO GCS remnant"
    assert "file://" not in manifest, "render must carry ZERO file:// (plain path fix)"
    assert "${REDIS_PASSWORD}" not in manifest, "render must carry ZERO placeholder"
    assert FEAST_BUNDLED_HOST in manifest, "render must reference bundled feast-redis-master"
    assert "valkey-primary" not in manifest, "render must carry ZERO valkey refs"


def test_feast_render_services_private_single_replica() -> None:
    docs = _docs(_render(FEAST_RELEASE, FEAST_CHART_REF, FEAST_VERSION, FEAST_VALUES))
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in feast render"
    for svc in services:
        name = str((svc.get("metadata") or {}).get("name"))
        spec = svc.get("spec") or {}
        assert spec.get("type") == "ClusterIP", f"Service {name} must stay ClusterIP"
        assert not spec.get("externalIPs")
    for doc in docs:
        if doc.get("kind") == "Deployment":
            name = str((doc.get("metadata") or {}).get("name"))
            assert (doc.get("spec") or {}).get("replicas") == 1, f"Deployment {name} single-replica"


# --- datahub values shape ---


def test_datahub_values_top_level_keys_real() -> None:
    values = _load(DATAHUB_VALUES)
    unknown = set(values) - DATAHUB_ALLOWED_TOP
    assert not unknown, f"datahub unknown top-level keys: {sorted(unknown)}"


def test_datahub_values_has_no_stub_keys() -> None:
    values = _load(DATAHUB_VALUES)
    assert "existingSecret" not in values, "chart has no top-level `existingSecret` (stub key)"
    assert "opensearch" not in values, "chart has no top-level `opensearch` (stub key)"


def test_datahub_values_services_clusterip() -> None:
    values = _load(DATAHUB_VALUES)
    assert ((values.get("datahub-gms") or {}).get("service") or {}).get("type") == "ClusterIP"
    assert ((values.get("datahub-frontend") or {}).get("service") or {}).get("type") == "ClusterIP"


def test_datahub_sql_wired_to_platform_postgres() -> None:
    values = _load(DATAHUB_VALUES)
    ds = ((((values.get("global") or {}).get("sql") or {}).get("datasource")) or {})
    assert ds.get("host") == f"{PLATFORM_POSTGRES_HOST}:{PLATFORM_POSTGRES_PORT}"
    assert str(ds.get("port")) == PLATFORM_POSTGRES_PORT
    assert ds.get("url") == PLATFORM_POSTGRES_URL
    assert ds.get("driver") == PLATFORM_POSTGRES_DRIVER
    assert ds.get("database") == PLATFORM_POSTGRES_DB
    assert (ds.get("username") or {}).get("secretRef") == POSTGRES_SECRET
    assert (ds.get("username") or {}).get("secretKey") == "username"
    assert (ds.get("password") or {}).get("secretRef") == POSTGRES_SECRET
    assert (ds.get("password") or {}).get("secretKey") == "password"


def test_datahub_kafka_wired_to_redpanda() -> None:
    values = _load(DATAHUB_VALUES)
    server = ((((values.get("global") or {}).get("kafka") or {}).get("bootstrap")) or {}).get("server")
    assert server == PLATFORM_KAFKA_SERVER


def test_datahub_search_wired_to_platform_opensearch() -> None:
    values = _load(DATAHUB_VALUES)
    es = ((values.get("global") or {}).get("elasticsearch")) or {}
    assert es.get("host") == PLATFORM_ES_HOST
    assert str(es.get("port")) == PLATFORM_ES_PORT


def test_datahub_secret_refs_match_postgres_externalsecret() -> None:
    manifest = yaml.safe_load(POSTGRES_ES.read_text(encoding="utf-8"))
    spec = manifest.get("spec") or {}
    assert (spec.get("target") or {}).get("name") == POSTGRES_SECRET
    synced = {e.get("secretKey") for e in spec.get("data") or [] if isinstance(e, dict)}
    assert {"username", "password", "database"} <= synced
    values = _load(DATAHUB_VALUES)
    ds = ((((values.get("global") or {}).get("sql") or {}).get("datasource")) or {})
    for field in ("username", "password"):
        ref = ds.get(field) or {}
        assert ref.get("secretRef") == (spec.get("target") or {}).get("name")
        assert ref.get("secretKey") in synced


def test_datahub_values_contains_no_literal_credential() -> None:
    violations: list[str] = []
    _walk_literals(_load(DATAHUB_VALUES), "$", violations)
    # JDBC URL userinfo check is covered by walker; also forbid password-looking values.
    assert not violations, f"literal credential in datahub.yaml: {violations}"
    dumped = yaml.safe_dump(_load(DATAHUB_VALUES))
    assert "prerequisites-mysql" not in dumped
    assert "prerequisites-kafka" not in dumped
    assert "mysql-secrets" not in dumped


# --- datahub render proofs ---


def test_datahub_render_exit_zero() -> None:
    assert isinstance(_render(DATAHUB_RELEASE, DATAHUB_CHART_REF, DATAHUB_VERSION, DATAHUB_VALUES), str)


def test_datahub_render_env_wired_no_prerequisites() -> None:
    manifest = _render(DATAHUB_RELEASE, DATAHUB_CHART_REF, DATAHUB_VERSION, DATAHUB_VALUES)
    assert "prerequisites-mysql" not in manifest
    assert "prerequisites-kafka" not in manifest
    assert PLATFORM_POSTGRES_URL in manifest
    assert PLATFORM_KAFKA_SERVER in manifest
    assert PLATFORM_ES_HOST in manifest
    docs = _docs(manifest)
    found_sql = found_kafka = found_es = False
    for doc in docs:
        if doc.get("kind") not in ("Deployment", "Job", "CronJob"):
            continue
        spec = (doc.get("spec") or {}).get("template", {}).get("spec", {})
        if not spec.get("containers"):
            continue
        for container in spec.get("containers", []):
            by_name = {e.get("name"): e for e in (container.get("env") or []) if isinstance(e, dict)}
            if "EBEAN_DATASOURCE_URL" in by_name:
                assert by_name["EBEAN_DATASOURCE_URL"].get("value") == PLATFORM_POSTGRES_URL
                pw = by_name.get("EBEAN_DATASOURCE_PASSWORD") or {}
                ref = (pw.get("valueFrom") or {}).get("secretKeyRef") or {}
                assert ref.get("name") == POSTGRES_SECRET and ref.get("key") == "password"
                found_sql = True
            if "KAFKA_BOOTSTRAP_SERVER" in by_name:
                assert by_name["KAFKA_BOOTSTRAP_SERVER"].get("value") == PLATFORM_KAFKA_SERVER
                found_kafka = True
            if "ELASTICSEARCH_HOST" in by_name:
                assert by_name["ELASTICSEARCH_HOST"].get("value") == PLATFORM_ES_HOST
                found_es = True
    assert found_sql and found_kafka and found_es, "expected SQL/Kafka/ES env in workloads"


def test_datahub_render_services_private_only() -> None:
    docs = _docs(_render(DATAHUB_RELEASE, DATAHUB_CHART_REF, DATAHUB_VERSION, DATAHUB_VALUES))
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in datahub render"
    for svc in services:
        name = str((svc.get("metadata") or {}).get("name"))
        spec = svc.get("spec") or {}
        assert spec.get("type") == "ClusterIP", f"Service {name} must stay ClusterIP, got {spec.get('type')}"
        assert not spec.get("externalIPs")


def test_datahub_render_single_replica() -> None:
    docs = _docs(_render(DATAHUB_RELEASE, DATAHUB_CHART_REF, DATAHUB_VERSION, DATAHUB_VALUES))
    for doc in docs:
        if doc.get("kind") == "Deployment":
            name = str((doc.get("metadata") or {}).get("name"))
            assert (doc.get("spec") or {}).get("replicas") == 1, f"Deployment {name} single-replica"
