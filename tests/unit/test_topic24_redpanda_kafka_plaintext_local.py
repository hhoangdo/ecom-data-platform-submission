"""Topic 24 LOCAL redpanda-listener fix (no lease, client-side only).

GROUNDED DIAGNOSIS (live-proven + chart source, metadata/template reads only):
- datahub 1.1.6 system-update SQL phase SUCCEEDED (`Tables created: 1`;
  postgres bootstrap works, do NOT touch it). Kafka phase wedged: client
  dials `redpanda.edai2:9093` plaintext, broker demands TLS
  (`Wrong SSL Version number`), 6xError pods.
- redpanda-console 2/2 Running: the chart auto-wires TLS material into the
  console (projected cert volume + `kafka.tls {enabled:true, caFilepath}`),
  so SOME client path works. Datahub has no such wiring (plaintext
  `KAFKA_BOOTSTRAP_SERVER`, no TLS material keys) -> handshake fails.
- values/datahub.yaml sets `global.kafka.bootstrap.server`
  = `redpanda.edai2:9093` (real key, default `prerequisites-kafka:9092`;
  GMS Deployment + system-update Job render `KAFKA_BOOTSTRAP_SERVER` from it).

CHART SCHEMA (pinned, `helm show values redpanda/redpanda --version 26.2.4`
+ pulled chart templates, metadata/template reads only):
- `tls.enabled: true` (values.yaml line 206, global default for ALL listeners).
- `listeners:` (line 872) has EXACTLY five names: admin/kafka/rpc/http/
  schemaRegistry (values.schema.json `properties.listeners.properties` keys;
  NO second plaintext kafka listener key exists).
- `listeners.kafka.port: 9093` (line 906, single internal Kafka port;
  external `listeners.kafka.external.default.port: 9094`, line 918, is the
  NodePort/external path, NOT a plaintext internal alternative).
- `listeners.kafka.tls:` (lines 909-913): `{cert: default,
  requireClientAuth: false}` + commented `# enabled:` override
  (line 910-911 `Optional flag to override the global TLS enabled flag`).
  Per-key schema: values.schema.json
  `properties.listeners.properties.kafka.properties.tls.properties.enabled`
  `{type: boolean}` (OPTIONAL, not in tls `required: [cert,
  requireClientAuth]`); `properties.listeners.properties.kafka.required:
  [port, tls]`; global `properties.tls.properties.enabled {type: boolean}`.
- Template law (`templates/_values.go.tpl` line 1042
  `redpanda.InternalTLS.IsEnabled`): `IsEnabled = (t.enabled DEFAULT
  tls.enabled) AND (t.cert != "")` where `t = listeners.<name>.tls`.
  So `listeners.kafka.tls.enabled=false` disables TLS on the Kafka API
  listener ONLY while global `tls.enabled=true` keeps admin/rpc/
  schemaRegistry/http TLS. `templates/_configmap.go.tpl` lines 545-549
  (`kafka_api_tls` set ONLY if `ListenersTLS` non-empty) + lines 509-512
  (`broker_tls` set ONLY if `IsEnabled`) + `templates/_render_state.go.tpl`
  `RenderState.AsStaticConfigSource` (console `kafkaSpec.tls` set ONLY if
  `IsEnabled`) prove the toggle removes `kafka_api_tls`/`broker_tls`/console
  `kafka.tls` cleanly (console auto-switches to plaintext).
- Service (`templates/_service.internal.go.tpl` `redpanda.ServiceInternal`):
  internal Service ports come from `listeners.*.port` ONLY (not from
  `tls.enabled`), so the toggle keeps Service `redpanda` ports identical
  (kafka 9093 ClusterIP). Template proof below asserts it.
- Console working config (rendered, `helm template redpanda ...` with CURRENT
  values): ConfigMap `redpanda-console` `config.yaml` carries
  `kafka.brokers: [redpanda-0.redpanda.edai2.svc.cluster.local.:9093]` +
  `kafka.tls {enabled:true,
  caFilepath:/etc/tls/certs/secrets/redpanda-default-cert/ca.crt}` +
  `redpanda.adminApi {urls:[https://...:9644], tls.enabled:true}` +
  `schemaRegistry {urls:[https://...:8081], tls.enabled:true}`; Deployment
  mounts projected volume `redpanda-certificates` at `/etc/tls/certs`.
  Datahub mirrors NOTHING of this (no cert volume, no TLS env) -> must use
  a plaintext broker listener instead.
- Datahub TLS alternative REJECTED: chart `global.kafka` has NO simple TLS
  boolean; the only SSL path is commented `springKafkaConfigurationOverrides`
  JKS mounts (values.yaml lines 1436-1455) needing cert file mounts +
  password literals (forbidden). `global.kafka.schemaregistry.type: INTERNAL`
  default means GMS needs no external SR TLS for this path. SASL stays
  default-off both sides (`auth.sasl.enabled:false` chart default;
  `global.kafka.iam.enabled:false` datahub default) -> no SASL secret.

APPROVED DESIGN (host/port change preferred, but IMPOSSIBLE here -- SMALLEST
diff is the per-listener TLS toggle):
- NO second plaintext Kafka listener exists (single internal port 9093; 9094
  is the external NodePort path, Service `redpanda` exposes only 9093
  internally). Changing datahub to `:9092` would point at NOTHING (no 9092
  in Service/render). So the fallback becomes the fix:
  `infra/helm/edai2/values/redpanda.yaml` gains ONLY
  `listeners.kafka.tls {enabled:false, cert:default, requireClientAuth:false}`
  (cert/requireClientAuth repeat chart defaults verbatim to satisfy schema
  `required`; `enabled:false` is the single semantic change).
  datahub.yaml is UNCHANGED (`redpanda.edai2:9093` becomes plaintext).
- Everything else kept: global TLS stays on (other listeners TLS),
  `external.enabled:false` (private), ClusterIP-only, SASL-off, postgres +
  opensearch wiring untouched, NO image/version/repo changes, NO new PVCs.

RESIDUAL RISKS (stated plainly, same Topics-27/31 note as opensearch):
plaintext Kafka inside the private pod network until Topics 27/31 re-enable
TLS (ClusterIP-only, no public ingress; SASL still off -- if the broker
later enforces SASL, GMS Kafka client with no SASL env will auth-fail; watch
GMS logs for SASL/AUTH errors + `KAFKA_BOOTSTRAP_SERVER` connectivity).

LIVE CONFIRMATION (leased agent, cluster unreachable from here):
`kubectl get svc redpanda -n edai2` (expect headless ClusterIP None, kafka
9093) + `kubectl describe deploy redpanda-console -n edai2` (expect post-fix
console WITHOUT kafka tls block) belong to the leased agent; here we assert
the rendered template ports instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RP_VALUES = ROOT / "infra/helm/edai2/values/redpanda.yaml"
DH_VALUES = ROOT / "infra/helm/edai2/values/datahub.yaml"
CATALOG = ROOT / "infra/helm/edai2/releases.yaml"

RP_RELEASE = "redpanda"
RP_CHART = "redpanda/redpanda"
RP_VERSION = "26.2.4"

DH_RELEASE = "datahub"
DH_CHART = "datahub/datahub"
DH_VERSION = "1.1.6"

KAFKA_PORT = 9093
KAFKA_SERVER = f"redpanda.edai2:{KAFKA_PORT}"


def _load(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} must parse as a dict"
    return loaded


def _render(release: str, chart: str, version: str, values: Path) -> str:
    proc = subprocess.run(
        ["helm", "template", release, chart, "--version", version,
         "-n", "edai2", "-f", str(values), "--dry-run=client"],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"helm template {release} failed: {proc.stderr[:2000]}"
    return proc.stdout


def _docs(manifest: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]


def _rp_kafka_tls(values: dict) -> dict | None:
    listeners = values.get("listeners") or {}
    kafka = listeners.get("kafka") or {}
    tls = kafka.get("tls")
    assert isinstance(tls, dict), (
        "redpanda.yaml must define listeners.kafka.tls "
        "(real key per values.schema.json "
        "properties.listeners.properties.kafka.properties.tls; "
        "values.yaml lines 909-913 + override comment 910-911)"
    )
    return tls


# --- redpanda values shape ---


def test_redpanda_kafka_tls_disabled_plaintext() -> None:
    tls = _rp_kafka_tls(_load(RP_VALUES))
    assert tls.get("enabled") is False, (
        "listeners.kafka.tls.enabled must be false (per-listener override of "
        "global tls.enabled=true; schema optional boolean, template "
        "_values.go.tpl:1042 IsEnabled law). Current TLS-only 9093 FAILs here."
    )


def test_redpanda_kafka_tls_keeps_schema_required_keys() -> None:
    tls = _rp_kafka_tls(_load(RP_VALUES))
    assert tls.get("cert") == "default", (
        "listeners.kafka.tls.cert must stay `default` (schema required, "
        "values.yaml line 912 verbatim)"
    )
    assert tls.get("requireClientAuth") is False, (
        "listeners.kafka.tls.requireClientAuth must stay false (schema "
        "required, values.yaml line 913 verbatim)"
    )


def test_redpanda_keeps_global_tls_and_other_listeners_tls() -> None:
    values = _load(RP_VALUES)
    tls_global = values.get("tls") or {}
    assert tls_global.get("enabled") is not False, (
        "global tls.enabled must stay true/default (Kafka-only toggle; "
        "admin/rpc/schemaRegistry/http keep TLS)"
    )
    listeners = values.get("listeners") or {}
    assert set(listeners) <= {"admin", "kafka", "rpc", "http", "schemaRegistry"}, (
        f"listeners must carry ONLY chart-real names, got {sorted(listeners)}"
    )
    for name in ("admin", "rpc", "http", "schemaRegistry"):
        entry = listeners.get(name) or {}
        entry_tls = entry.get("tls") or {}
        assert entry_tls.get("enabled") is not False, (
            f"listeners.{name}.tls must NOT disable TLS (Kafka-only toggle)"
        )


def test_redpanda_single_internal_kafka_port_no_plaintext_alternative() -> None:
    values = _load(RP_VALUES)
    listeners = values.get("listeners") or {}
    kafka = listeners.get("kafka") or {}
    port = kafka.get("port", KAFKA_PORT)
    assert int(port) == KAFKA_PORT, (
        f"listeners.kafka.port must stay {KAFKA_PORT} (chart default "
        "values.yaml line 906; Service exposes this port)"
    )


# --- datahub values shape (plaintext intent, bootstrap matches broker) ---


def _dh_kafka_server(values: dict) -> str:
    server = ((((values.get("global") or {}).get("kafka") or {}).get("bootstrap")) or {}).get("server")
    assert isinstance(server, str) and server, "global.kafka.bootstrap.server must be a non-empty string"
    return server


def test_datahub_kafka_bootstrap_matches_plaintext_broker() -> None:
    dh_server = _dh_kafka_server(_load(DH_VALUES))
    rp_listeners = (_load(RP_VALUES).get("listeners") or {})
    rp_port = int((rp_listeners.get("kafka") or {}).get("port", KAFKA_PORT))
    assert rp_port == KAFKA_PORT, f"broker port must stay {KAFKA_PORT}, got {rp_port}"
    assert dh_server == KAFKA_SERVER, (
        f"global.kafka.bootstrap.server must be the proven-plaintext broker "
        f"{KAFKA_SERVER!r}, got {dh_server!r}"
    )
    tls = _rp_kafka_tls(_load(RP_VALUES))
    assert tls.get("enabled") is False, (
        "bootstrap 9093 is TLS-only until listeners.kafka.tls.enabled=false; "
        "NO 9093-TLS-only target unless TLS material is wired (datahub has "
        "none -- see no-TLS-material test). Current values FAIL here."
    )


def test_datahub_has_no_kafka_tls_material() -> None:
    values = _load(DH_VALUES)
    global_cfg = values.get("global") or {}
    assert "credentialsAndCertsSecrets" not in global_cfg, (
        "datahub must carry NO TLS cert handoff (plaintext intent; JKS/SSL "
        "mount path rejected -- literals forbidden)"
    )
    overrides = global_cfg.get("springKafkaConfigurationOverrides") or {}
    for key in overrides:
        assert "ssl" not in str(key).lower() and "security.protocol" not in str(key).lower(), (
            f"datahub must carry NO springKafka SSL override (plaintext), got {key!r}"
        )
    kafka = global_cfg.get("kafka") or {}
    iam = kafka.get("iam") or {}
    assert iam.get("enabled", False) is False, "kafka iam must stay default-off (SASL-off both sides)"


def test_releases_pins_unchanged() -> None:
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    charts = {str(e["name"]): str(e["version"]) for e in catalog.get("charts", [])}
    assert charts.get("redpanda") == RP_VERSION, f"redpanda pin must stay {RP_VERSION}"
    assert charts.get("datahub") == DH_VERSION, f"datahub pin must stay {DH_VERSION}"


def test_values_carry_no_literals_no_new_pvc() -> None:
    rp = _load(RP_VALUES)
    assert ((rp.get("storage") or {}).get("persistentVolume") or {}).get("size") == "8Gi"
    assert ((rp.get("statefulset") or {}).get("replicas")) == 1
    assert ((rp.get("external") or {}).get("enabled")) is False
    assert "image" not in rp, "redpanda values must not pin images"
    dumped = yaml.safe_dump(rp) + yaml.safe_dump(_load(DH_VALUES))
    assert "password" not in dumped.lower() or "secretKey" in dumped, (
        "values must carry no literal credentials"
    )


# --- render proofs ---


def test_redpanda_render_exit_zero() -> None:
    assert isinstance(_render(RP_RELEASE, RP_CHART, RP_VERSION, RP_VALUES), str)


def _rp_configmap_redpanda_yaml(manifest: str) -> dict:
    for doc in _docs(manifest):
        if doc.get("kind") == "ConfigMap" and str((doc.get("metadata") or {}).get("name")) == "redpanda":
            data = doc.get("data") or {}
            body = data.get("redpanda.yaml")
            assert isinstance(body, str) and body.strip(), "ConfigMap redpanda must carry redpanda.yaml"
            parsed = yaml.safe_load(body)
            assert isinstance(parsed, dict)
            return parsed
    raise AssertionError("render must contain ConfigMap/redpanda with redpanda.yaml")


def test_redpanda_render_kafka_plaintext() -> None:
    cfg = _rp_configmap_redpanda_yaml(_render(RP_RELEASE, RP_CHART, RP_VERSION, RP_VALUES))
    redpanda_cfg = cfg.get("redpanda") or {}
    kafka_api = redpanda_cfg.get("kafka_api") or []
    internal = [e for e in kafka_api if isinstance(e, dict) and e.get("name") == "internal"]
    assert internal and int(internal[0].get("port")) == KAFKA_PORT, (
        f"kafka_api internal must stay :{KAFKA_PORT}, got {kafka_api!r}"
    )
    tls_entries = redpanda_cfg.get("kafka_api_tls") or []
    assert not [e for e in tls_entries if isinstance(e, dict) and e.get("name") == "internal"], (
        f"kafka_api_tls must carry NO internal entry (plaintext), got {tls_entries!r}"
    )
    for client_key in ("pandaproxy_client", "schema_registry_client"):
        client = cfg.get("pandaproxy_client" if client_key == "pandaproxy_client" else "schema_registry_client") or {}
        assert "broker_tls" not in client, (
            f"{client_key} must carry NO broker_tls (plaintext broker), got {client!r}"
        )
    admin_tls = redpanda_cfg.get("admin_api_tls") or []
    assert [e for e in admin_tls if isinstance(e, dict) and e.get("name") == "internal"], (
        f"admin_api_tls must KEEP internal TLS entry, got {admin_tls!r}"
    )
    rpk_kafka = ((cfg.get("rpk") or {}).get("kafka_api")) or {}
    assert rpk_kafka.get("tls") in (None, {}), (
        f"rpk.kafka_api.tls must be absent/null (plaintext), got {rpk_kafka!r}"
    )


def test_redpanda_render_console_switches_to_plaintext() -> None:
    manifest = _render(RP_RELEASE, RP_CHART, RP_VERSION, RP_VALUES)
    cms = [d for d in _docs(manifest)
           if d.get("kind") == "ConfigMap"
           and str((d.get("metadata") or {}).get("name")) == "redpanda-console"]
    assert cms, "render must contain ConfigMap/redpanda-console"
    found = False
    for cm in cms:
        body = (cm.get("data") or {}).get("config.yaml")
        if not isinstance(body, str) or "brokers" not in body:
            continue
        parsed = yaml.safe_load(body)
        if not isinstance(parsed, dict):
            continue
        kafka = parsed.get("kafka") or {}
        brokers = kafka.get("brokers") or []
        assert brokers, "console kafka.brokers must stay rendered"
        assert any(str(b).endswith(f":{KAFKA_PORT}") for b in brokers), (
            f"console brokers must reference :{KAFKA_PORT}, got {brokers!r}"
        )
        tls = kafka.get("tls")
        assert tls is None or (isinstance(tls, dict) and tls.get("enabled") in (None, False)), (
            f"console kafka.tls must be absent/disabled after toggle (plaintext), got {tls!r}"
        )
        found = True
    assert found, "console config.yaml with kafka brokers must render"


def test_redpanda_render_service_keeps_kafka_9093_clusterip() -> None:
    docs = _docs(_render(RP_RELEASE, RP_CHART, RP_VERSION, RP_VALUES))
    svc = next((d for d in docs
                if d.get("kind") == "Service"
                and str((d.get("metadata") or {}).get("name")) == "redpanda"), None)
    assert svc is not None, "render must contain Service/redpanda"
    spec = svc.get("spec") or {}
    assert spec.get("type") == "ClusterIP", f"Service redpanda must stay ClusterIP, got {spec.get('type')!r}"
    ports = {p.get("name"): p.get("port") for p in (spec.get("ports") or []) if isinstance(p, dict)}
    assert ports.get("kafka") == KAFKA_PORT, f"Service kafka port must stay {KAFKA_PORT}, got {ports!r}"
    console = next((d for d in docs
                    if d.get("kind") == "Service"
                    and str((d.get("metadata") or {}).get("name")) == "redpanda-console"), None)
    assert console is not None, "render must contain Service/redpanda-console"
    assert (console.get("spec") or {}).get("type") == "ClusterIP"


def test_datahub_render_exit_zero() -> None:
    assert isinstance(_render(DH_RELEASE, DH_CHART, DH_VERSION, DH_VALUES), str)


def _env_by_name(container: dict) -> dict:
    return {e.get("name"): e for e in (container.get("env") or []) if isinstance(e, dict) and e.get("name")}


def test_datahub_render_job_and_gms_have_plaintext_bootstrap() -> None:
    docs = _docs(_render(DH_RELEASE, DH_CHART, DH_VERSION, DH_VALUES))
    jobs = [d for d in docs if d.get("kind") == "Job"]
    assert jobs, "render must contain the system-update Job"
    gms = [d for d in docs
           if d.get("kind") == "Deployment"
           and "gms" in str((d.get("metadata") or {}).get("name", ""))]
    assert gms, "render must contain the GMS Deployment"
    found_job = found_gms = False
    def _is_kafka_ssl_env(name: str) -> bool:
        upper = str(name).upper()
        return "KAFKA" in upper and (
            "SSL" in upper or "SECURITY" in upper or "TRUSTSTORE" in upper or "KEYSTORE" in upper
        )
    for job in jobs:
        for container in (((job.get("spec") or {}).get("template", {}).get("spec", {})).get("containers", [])):
            by_name = _env_by_name(container)
            if "KAFKA_BOOTSTRAP_SERVER" in by_name:
                assert by_name["KAFKA_BOOTSTRAP_SERVER"].get("value") == KAFKA_SERVER, (
                    f"Job {(job.get('metadata') or {}).get('name')}: "
                    f"KAFKA_BOOTSTRAP_SERVER must be {KAFKA_SERVER!r}"
                )
                assert not any(_is_kafka_ssl_env(k) for k in by_name), (
                    "Job must carry NO Kafka SSL env (plaintext; "
                    "ELASTICSEARCH_USE_SSL is ES scope, not Kafka)"
                )
                found_job = True
    for dep in gms:
        for container in (((dep.get("spec") or {}).get("template", {}).get("spec", {})).get("containers", [])):
            by_name = _env_by_name(container)
            if "KAFKA_BOOTSTRAP_SERVER" in by_name:
                assert by_name["KAFKA_BOOTSTRAP_SERVER"].get("value") == KAFKA_SERVER
                assert not any(_is_kafka_ssl_env(k) for k in by_name), (
                    "GMS must carry NO Kafka SSL env (plaintext)"
                )
                found_gms = True
    assert found_job, "system-update Job must render KAFKA_BOOTSTRAP_SERVER plaintext"
    assert found_gms, "GMS Deployment must render KAFKA_BOOTSTRAP_SERVER plaintext"


def test_datahub_render_services_clusterip() -> None:
    docs = _docs(_render(DH_RELEASE, DH_CHART, DH_VERSION, DH_VALUES))
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in datahub render"
    for svc in services:
        name = str((svc.get("metadata") or {}).get("name"))
        spec = svc.get("spec") or {}
        assert spec.get("type") == "ClusterIP", f"Service {name} must stay ClusterIP"
