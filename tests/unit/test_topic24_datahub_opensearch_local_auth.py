"""Topic 24 LOCAL datahub<->opensearch FALLBACK: security plugin DISABLED (no lease, client-side only).

GROUNDED VERDICT (do NOT relitigate, VERIFY mechanics):
- `plugins.security.*` keys in opensearch.yml (INCLUDING http-off) trigger the
  demo-installer Quit (`opensearch.yml seems to be already configured for
  Security. Quit.`); zero such keys -> installer writes FULL demo (TLS
  everywhere) which datahub cannot use (no trust path, `insecure` does not
  propagate to GMS). Full-TLS-for-datahub is unwinnable with chart-real keys.

APPROVED FALLBACK (private ClusterIP-only study core; Topics 27/31 own
public/HTTPS and WILL re-harden; record plainly): run OpenSearch with the
security plugin DISABLED -- plaintext HTTP + no auth inside the private pod
network. DataHub then needs no TLS/auth (its secretRefs stay as harmless
wiring for the re-hardening).

MECHANISM VERDICT (chart-real, 2.38.0 pulled chart + image entrypoint):
- (a) env `DISABLE_INSTALL_DEMO_CONFIG=true` via chart-real `extraEnvs`
  (values.yaml 102-111 documents extraEnvs; statefulset.yaml 435-437 renders
  it verbatim into container env:) PREVENTS the demo installer from running
  at all, so NO Quit check can fire. Entrypoint
  `opensearch-docker-entrypoint-2.x.sh` setupSecurityPlugin: if
  DISABLE_INSTALL_DEMO_CONFIG=true -> echo "Disabling execution of
  install_demo_configuration.sh" and SKIP; else run
  `install_demo_configuration.sh -y -i -s`. Docker README confirms:
  "DISABLE_INSTALL_DEMO_CONFIG ... disables running of
  install_demo_configuration.sh". Docs 2.19 (debian): same flag prevents demo
  setup.
- (b) `plugins.security.disabled: true` in `config.opensearch.yml`
  (values.yaml 35-49 config map; configmap.yaml 2,10 verbatim render;
  statefulset.yaml 510-514 mount) starts the node WITHOUT the security
  plugin (docs disable-enable-security; entrypoint adds the identical
  `-Eplugins.security.disabled=true` when DISABLE_SECURITY_PLUGIN=true).
  With the installer skipped, opensearch.yml can STILL carry this key safely:
  the Quit lives INSIDE the Installer Java class invoked ONLY by
  install_demo_configuration.sh -- if the entrypoint never runs that script,
  no Installer process exists, so no parsed-YAML Quit is possible.
- (c) No other chart default fights a disabled-security node:
  `securityConfig.enabled: true` (values.yaml 330-331) only gates
  volumeMounts WHEN secrets/data are defined (statefulset.yaml 456-502; with
  defaults all empty + data {} nothing mounts; securityconfig.yaml 1 gates
  Secret on data) -> harmless, leave default. `plugins.enabled: false`
  (values.yaml 490-491) keeps the default ENTRYPOINT (statefulset.yaml
  364-383 overrides command only when true) -> REQUIRED false so the
  entrypoint honors DISABLE_INSTALL_DEMO_CONFIG. `protocol: https`
  (values.yaml 281) is consumed ONLY by the masterTerminationFix sidecar curl
  (statefulset.yaml 545) which is disabled by default (values.yaml 424) ->
  harmless.

USERNAME EXCEPTION (explicit): `admin` is the well-known DEFAULT OpenSearch
Security Plugin admin account NAME -- an identifier, NOT a credential. With
the plugin DISABLED it is entirely unused (no auth enforced); datahub keeps
rendering it as harmless wiring for the 27/31 re-hardening. No password,
token, or key material appears here or in any values file; the password
travels ONLY via secretKeyRef to the ExternalSecret-synced `opensearch`
secret. The no-literal tests below therefore allowlist exactly
`username: admin` while forbidding every `value:` literal under auth.password
and every password-looking scalar. NOTE: opensearch `extraEnvs`
DISABLE_INSTALL_DEMO_CONFIG uses a NON-credential `value: "true"` flag
(distinct from any password literal; see
test_opensearch_extraenvs_has_demo_disable_and_admin_retained).

SCHEMA SOURCES (pinned, metadata/template reads only):
- opensearch 2.38.0 / app 2.19.6 (Chart.yaml 2,16: appVersion 2.19.6,
  version 2.38.0; releases.yaml pin UNCHANGED):
  `config:` map (values.yaml 35) of `<filename>: |` strings,
  `opensearch.yml: |` default (values.yaml 49, active lines
  `cluster.name: opensearch-cluster` + `network.host: 0.0.0.0`);
  `extraEnvs: []` (values.yaml 105) + OPENSEARCH_INITIAL_ADMIN_PASSWORD
  comment (108-111); `protocol: https` (281, masterTerminationFix-only);
  `securityConfig.enabled: true` (330-331); `plugins.enabled: false`
  (490-491). Templates: configmap.yaml 2,10 (verbatim render into
  `<release>-config` ConfigMap); statefulset.yaml 510-514 (mount),
  431-433 (singleNode via `discovery.type` env), 435-437 (extraEnvs verbatim),
  364-383 (plugins.enabled command override), 456-502 (securityConfig mounts
  only with secrets), 18-22 (singleNode forces replicas 1).
- datahub 1.1.6 (`helm show values datahub/datahub --version 1.1.6`):
  `global.elasticsearch.host` (line 724, default `opensearch-cluster-master`),
  `port` (725), `skipcheck` (729, default `"false"`),
  `insecure` (730, default `"false"` -- NOT rendered into GMS),
  `useSSL` (731, default `"false"`), commented `# auth:` (750-757).
  Templates: _upgrade.tpl 59-81, _helpers.tpl 624-663,
  deployment.yaml 268-296 (all render HOST/PORT/SKIP/USE_SSL/auth, no
  ELASTICSEARCH_INSECURE). Values UNCHANGED in this fallback: secretRefs
  render but are unenforced against the no-auth backend (harmless wiring).
- Secret cross-assert: infra/security/external-secrets/opensearch.yaml target
  `opensearch`, data keys {username, password} from Vault
  `edai2/platform/opensearch` -- RETAINED unenforced for 27/31 re-hardening.

RESIDUAL RISKS (stated plainly): OPEN search tier (no auth, plaintext HTTP)
inside the private pod network ONLY until Topics 27/31 re-harden with TLS +
auth; NO public ingress (ClusterIP-only retained); Vault `opensearch` secret
retained but UNENFORCED (needed at re-hardening -- do NOT delete); redpanda
SASL-off unchanged; old 8Gi PVC carries secured-era system indices that are
unreadable/incompatible -- fresh volume MANDATORY at leased install (see
leased-agent block in task).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OS_VALUES = ROOT / "infra/helm/edai2/values/opensearch.yaml"
DH_VALUES = ROOT / "infra/helm/edai2/values/datahub.yaml"
OS_ES_MANIFEST = ROOT / "infra/security/external-secrets/opensearch.yaml"

OS_RELEASE = "opensearch"
OS_CHART = "opensearch"  # bare name + --repo (repo convention, cf. test_topic24_opensearch_password.py)
OS_REPO = "https://opensearch-project.github.io/helm-charts"
OS_VERSION = "2.38.0"

DH_RELEASE = "datahub"
DH_CHART = "datahub/datahub"  # alias form via registered repo (cf. test_topic24_feast_datahub_local.py)
DH_VERSION = "1.1.6"

ES_HOST = "opensearch-cluster-master.edai2"
ES_PORT = "9200"
ES_USERNAME = "admin"  # identifier exception, see module docstring (unenforced while plugin disabled)
ES_SECRET = "opensearch"
ES_SECRET_KEY = "password"
SECURITY_DISABLED_RE = re.compile(
    r"plugins\.security\.disabled\s*:\s*true", re.IGNORECASE
)
HTTP_SSL_OFF_RE = re.compile(
    r"plugins\.security\.ssl\.http\.enabled\s*:\s*false", re.IGNORECASE
)
# Demo-cert markers that must be ABSENT entirely (fallback carries NO demo
# filepaths at all -- neither active nor commented -- because the installer
# never runs and the plugin is disabled; any hit means leftover TLS thinking).
DEMO_MARKERS_RAW = (
    "pemcert_filepath",
    "pemkey_filepath",
    "pemtrustedcas_filepath",
    "esnode.pem",
    "esnode-key.pem",
    "root-ca.pem",
    "allow_unsafe_democertificates",
    "allow_default_init_securityindex",
    "enforce_hostname_verification",
)


def _load(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} must parse as a dict"
    return loaded


def _render_os() -> str:
    proc = subprocess.run(
        ["helm", "template", OS_RELEASE, OS_CHART, "--repo", OS_REPO,
         "--version", OS_VERSION, "-n", "edai2", "-f", str(OS_VALUES),
         "--dry-run=client"],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"helm template {OS_RELEASE} failed: {proc.stderr[:2000]}"
    return proc.stdout


def _render_dh() -> str:
    proc = subprocess.run(
        ["helm", "template", DH_RELEASE, DH_CHART,
         "--version", DH_VERSION, "-n", "edai2", "-f", str(DH_VALUES),
         "--dry-run=client"],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"helm template {DH_RELEASE} failed: {proc.stderr[:2000]}"
    return proc.stdout


def _docs(manifest: str) -> list[dict]:
    return [d for d in yaml.safe_load_all(manifest) if isinstance(d, dict)]


def _os_config_text(values: dict) -> str:
    config = values.get("config") or {}
    assert isinstance(config, dict) and "opensearch.yml" in config, (
        "opensearch.yaml must define config['opensearch.yml'] override "
        "(real chart key `config:`, opensearch/opensearch 2.38.0 values line 35)"
    )
    text = config["opensearch.yml"]
    assert isinstance(text, str) and text.strip(), (
        "config['opensearch.yml'] must be a non-empty YAML literal string"
    )
    return text


# --- opensearch values shape (FALLBACK: plugin DISABLED, installer SKIPPED) ---


def test_opensearch_config_disables_security_plugin() -> None:
    """Fallback core: `plugins.security.disabled: true` ACTIVE, http-off ABSENT."""
    text = _os_config_text(_load(OS_VALUES))
    assert SECURITY_DISABLED_RE.search(text), (
        "config['opensearch.yml'] must contain "
        "`plugins.security.disabled: true` (fallback: plugin DISABLED)"
    )
    assert not HTTP_SSL_OFF_RE.search(text), (
        "config['opensearch.yml'] must NOT contain "
        "`plugins.security.ssl.http.enabled: false` (moot without plugin -- remove it)"
    )
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    assert _lookup_setting(parsed, "plugins.security.disabled") is True, (
        "plugins.security.disabled must be ACTIVE (parsed YAML true)"
    )
    assert _lookup_setting(parsed, "plugins.security.ssl.http.enabled") is None, (
        "http-SSL-off must be ABSENT from parsed YAML (moot without plugin)"
    )


def test_opensearch_security_plugin_disabled_leaves_chart_defaults_alone() -> None:
    """No other chart default may fight the disabled-security node."""
    values = _load(OS_VALUES)
    text = _os_config_text(values)
    assert SECURITY_DISABLED_RE.search(text), "disabled key must be present"
    sec = values.get("securityConfig") or {}
    assert sec.get("enabled") is not False, (
        "securityConfig.enabled must stay true/default (harmless without "
        "secrets: statefulset.yaml 456-502 mounts nothing when all secrets "
        "empty; do NOT set false)"
    )
    plugins = values.get("plugins") or {}
    assert plugins.get("enabled") is not True, (
        "plugins.enabled must stay false/default (true would override the "
        "container command at statefulset.yaml 364-383; false keeps the "
        "default entrypoint which honors DISABLE_INSTALL_DEMO_CONFIG)"
    )


def test_opensearch_has_no_compat_flag_native_2x() -> None:
    """Native 2.x needs NO compat flag: `compatibility.*` must be ABSENT.

    Record (2026-10-09 re-pin 3.9.0 -> 2.38.0): DataHub 1.1.6 version-detects
    `OpenSearch expected 2.x`, so the chart is natively 2.x and no
    version-override flag is needed. The 3.x-era workaround
    (`compatibility.override_main_response_version`, removed in 3.0 -- would
    CrashLoop on 3.x) must NOT appear in values or the render; on native 2.x
    it is meaningless.
    """
    values = _load(OS_VALUES)
    dumped = yaml.safe_dump(values)
    assert "compatibility" not in dumped.lower(), (
        "opensearch.yaml must carry NO compatibility/compat flag (native 2.x)"
    )
    assert "override_main_response_version" not in dumped, (
        "opensearch.yaml must not set override_main_response_version (native 2.x)"
    )
    manifest = _render_os()
    assert "override_main_response_version" not in manifest, (
        "rendered manifests must not contain override_main_response_version"
    )


def test_opensearch_config_keeps_chart_defaults() -> None:
    text = _os_config_text(_load(OS_VALUES))
    assert "cluster.name: opensearch-cluster" in text, (
        "override REPLACES the chart-default opensearch.yml string, so it must "
        "retain `cluster.name: opensearch-cluster`"
    )
    assert "network.host: 0.0.0.0" in text, (
        "override must retain `network.host: 0.0.0.0` (chart default active line)"
    )


# --- Topic 24 LOCAL fallback: installer SKIPPED + plugin DISABLED ---
# GROUNDED VERDICT (do NOT relitigate): any `plugins.security.*` key in
# opensearch.yml (INCLUDING http-off) triggers the demo-installer Quit; zero
# such keys -> installer writes FULL demo TLS which datahub cannot use.
# Fallback: DISABLE_INSTALL_DEMO_CONFIG=true (installer never runs, no Quit
# possible) + plugins.security.disabled:true (node starts without plugin).
# Chart-default commented demo block is REMOVED entirely (NO demo filepaths
# at all) because it is moot without the plugin/installer.
_TRANSPORT_DEMO_REQUIRED = {
    "plugins.security.ssl.transport.pemcert_filepath": "esnode.pem",
    "plugins.security.ssl.transport.pemkey_filepath": "esnode-key.pem",
    "plugins.security.ssl.transport.pemtrustedcas_filepath": "root-ca.pem",
    "plugins.security.ssl.http.pemcert_filepath": "esnode.pem",
    "plugins.security.ssl.http.pemkey_filepath": "esnode-key.pem",
    "plugins.security.ssl.http.pemtrustedcas_filepath": "root-ca.pem",
    "plugins.security.allow_unsafe_democertificates": True,
}


def _lookup_setting(parsed: dict, dotted: str):
    """Lookup supporting BOTH flat (`a.b.c: v`) and nested (`a: b: c: v`)."""
    if not isinstance(parsed, dict):
        return None
    if dotted in parsed:
        value = parsed[dotted]
        return value if not isinstance(value, dict) else None
    cur: object = parsed
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if not isinstance(cur, dict) else None


def _active_lines(text: str) -> list[str]:
    """Non-comment, non-empty lines (comments are inert for YAML/installer)."""
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(raw)
    return out


def _os_parsed_config(text: str) -> dict:
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict), "config['opensearch.yml'] must parse as a YAML map"
    return parsed


def test_opensearch_config_has_no_demo_filepaths_and_no_httpoff() -> None:
    """Fallback guard: NO demo filepaths at all + NO http-off flat key.

    With the installer SKIPPED (DISABLE_INSTALL_DEMO_CONFIG=true) and the
    plugin DISABLED, the chart-default commented demo block is removed
    entirely: raw text must contain NONE of the demo-cert markers (neither
    active nor commented), and parsed YAML must contain NONE of the demo
    keys. Any hit means leftover TLS thinking that either re-triggers the
    Quit (if installer ever ran) or confuses the 27/31 re-hardening.
    """
    text = _os_config_text(_load(OS_VALUES))
    for marker in DEMO_MARKERS_RAW:
        assert marker not in text, (
            f"config['opensearch.yml'] must NOT contain demo marker {marker!r} "
            "(fallback carries NO demo filepaths -- commented block removed)"
        )
    assert not HTTP_SSL_OFF_RE.search(text), (
        "config['opensearch.yml'] must NOT contain http-off flat key "
        "(moot without plugin -- remove it)"
    )
    parsed = _os_parsed_config(text)
    for dotted, expected in _TRANSPORT_DEMO_REQUIRED.items():
        got = _lookup_setting(parsed, dotted)
        assert got is None, (
            f"config['opensearch.yml'] must NOT carry ACTIVE {dotted}; "
            f"got {got!r} (expected-absent value was {expected!r})"
        )
    assert _lookup_setting(parsed, "plugins.security.ssl.http.enabled") is None
    active = "\n".join(_active_lines(text))
    for marker in ("pemcert_filepath", "pemkey_filepath",
                   "pemtrustedcas_filepath", "esnode.pem", "root-ca.pem",
                   "allow_unsafe_democertificates"):
        assert marker not in active


def test_opensearch_extraenvs_has_demo_disable_and_admin_retained() -> None:
    """extraEnvs: DISABLE_INSTALL_DEMO_CONFIG=true + admin-password retained.

    DISABLE_INSTALL_DEMO_CONFIG=true (chart-real extraEnvs, statefulset.yaml
    435-437) SKIPS the demo installer so NO Quit can fire. The
    OPENSEARCH_INITIAL_ADMIN_PASSWORD secretKeyRef is RETAINED harmlessly
    (unenforced while the plugin is disabled) because Topics 27/31 need it
    at re-hardening -- do NOT delete the Vault secret or ExternalSecret.
    """
    values = _load(OS_VALUES)
    extra = values.get("extraEnvs") or []
    assert isinstance(extra, list) and extra, "extraEnvs must be a non-empty list"
    dis = next(
        (e for e in extra
         if isinstance(e, dict) and e.get("name") == "DISABLE_INSTALL_DEMO_CONFIG"),
        None,
    )
    assert dis is not None, (
        "extraEnvs must contain DISABLE_INSTALL_DEMO_CONFIG=true "
        "(chart-real extraEnvs skips the demo installer)"
    )
    assert str(dis.get("value")).lower() == "true", (
        f"DISABLE_INSTALL_DEMO_CONFIG must be value 'true', got {dis!r}"
    )
    assert "valueFrom" not in dis, "demo-disable flag is a plain value, not a secretRef"
    admin = next(
        (e for e in extra
         if isinstance(e, dict) and e.get("name") == "OPENSEARCH_INITIAL_ADMIN_PASSWORD"),
        None,
    )
    assert admin is not None, (
        "prior admin-password extraEnvs wiring must be RETAINED (harmless "
        "while disabled, needed at 27/31 re-hardening)"
    )
    assert "value" not in admin, "admin password must use valueFrom, never literal"
    ref = (admin.get("valueFrom") or {}).get("secretKeyRef") or {}
    assert ref.get("name") == ES_SECRET and ref.get("key") == ES_SECRET_KEY


def test_opensearch_render_has_disabled_no_demo_no_httpoff() -> None:
    """Render proof: disabled + NO demo + NO http-off."""
    docs = _docs(_render_os())
    cms = [d for d in docs
           if d.get("kind") == "ConfigMap"
           and str((d.get("metadata") or {}).get("name", "")).endswith("-config")]
    assert cms, "render must contain the <release>-config ConfigMap (config: override)"
    found = False
    for cm in cms:
        data = cm.get("data") or {}
        for _name, body in data.items():
            if not isinstance(body, str) or "cluster.name" not in body:
                continue
            if not SECURITY_DISABLED_RE.search(body):
                continue
            if HTTP_SSL_OFF_RE.search(body):
                continue
            if any(m in body for m in DEMO_MARKERS_RAW):
                continue
            parsed = yaml.safe_load(body)
            if not isinstance(parsed, dict):
                continue
            disabled = _lookup_setting(parsed, "plugins.security.disabled")
            http_off = _lookup_setting(parsed, "plugins.security.ssl.http.enabled")
            any_active_demo = any(
                _lookup_setting(parsed, k) is not None
                for k in _TRANSPORT_DEMO_REQUIRED
            )
            if disabled is True and http_off is None and not any_active_demo:
                found = True
    assert found, (
        "rendered ConfigMap opensearch.yml must carry the FALLBACK content: "
        "plugins.security.disabled:true + NO http-off + NO demo filepaths"
    )


def test_opensearch_retains_private_single_replica() -> None:
    values = _load(OS_VALUES)
    assert (values.get("service") or {}).get("type") == "ClusterIP"
    assert values.get("singleNode") is True
    assert values.get("replicas") == 1
    assert ((values.get("persistence") or {}).get("size")) == "8Gi", (
        "persistence.size must stay 8Gi"
    )
    extra = values.get("extraEnvs") or []
    entry = next(
        (e for e in extra
         if isinstance(e, dict) and e.get("name") == "OPENSEARCH_INITIAL_ADMIN_PASSWORD"),
        None,
    )
    assert entry is not None, "prior admin-password extraEnvs wiring must be kept"
    ref = (entry.get("valueFrom") or {}).get("secretKeyRef") or {}
    assert ref.get("name") == ES_SECRET and ref.get("key") == ES_SECRET_KEY


# --- opensearch render proofs ---


def test_opensearch_render_exit_zero() -> None:
    assert isinstance(
        _render_os(), str
    )


def test_opensearch_render_has_disabled_config() -> None:
    docs = _docs(_render_os())
    cms = [d for d in docs
           if d.get("kind") == "ConfigMap"
           and str((d.get("metadata") or {}).get("name", "")).endswith("-config")]
    assert cms, "render must contain the <release>-config ConfigMap (config: override)"
    found = False
    for cm in cms:
        data = cm.get("data") or {}
        for _name, body in data.items():
            if isinstance(body, str) and SECURITY_DISABLED_RE.search(body):
                assert not HTTP_SSL_OFF_RE.search(body), (
                    "rendered config must NOT carry http-off (moot without plugin)"
                )
                for marker in ("esnode.pem", "root-ca.pem", "pemcert_filepath"):
                    assert marker not in body, (
                        f"rendered config must NOT carry demo marker {marker!r}"
                    )
                found = True
    assert found, "rendered ConfigMap opensearch.yml must carry plugins.security.disabled:true"


def test_opensearch_render_private_single_replica() -> None:
    docs = _docs(_render_os())
    services = [d for d in docs if d.get("kind") == "Service"]
    assert services, "expected Services in opensearch render"
    for svc in services:
        name = str((svc.get("metadata") or {}).get("name"))
        spec = svc.get("spec") or {}
        if spec.get("clusterIP") == "None":
            # Headless discovery service (no type field by construction);
            # private: must expose nothing external.
            assert not spec.get("externalIPs"), f"headless Service {name} must stay private"
            continue
        assert spec.get("type") == "ClusterIP", (
            f"Service {name} must stay ClusterIP"
        )
    sts = [d for d in docs if d.get("kind") == "StatefulSet"]
    assert sts, "expected StatefulSet in opensearch render"
    for st in sts:
        assert (st.get("spec") or {}).get("replicas") == 1, "must stay single-replica"


# --- datahub values shape (UNCHANGED: secretRefs harmless against no-auth backend) ---


def _es(values: dict) -> dict:
    es = ((values.get("global") or {}).get("elasticsearch")) or {}
    assert isinstance(es, dict), "global.elasticsearch must be a map"
    return es


def test_datahub_es_auth_username_is_admin_identifier() -> None:
    es = _es(_load(DH_VALUES))
    auth = es.get("auth") or {}
    assert auth.get("username") == ES_USERNAME, (
        f"global.elasticsearch.auth.username must be {ES_USERNAME!r} "
        "(well-known default account NAME -- identifier, not credential; "
        "UNENFORCED while opensearch plugin disabled, retained for 27/31 "
        "re-hardening; exception recorded in module docstring)"
    )


def test_datahub_es_password_is_secret_ref() -> None:
    es = _es(_load(DH_VALUES))
    auth = es.get("auth") or {}
    pw = auth.get("password") or {}
    assert isinstance(pw, dict), "auth.password must be a secretRef map (never a literal)"
    assert "value" not in pw, "auth.password must use secretRef, never a literal `value:`"
    assert pw.get("secretRef") == ES_SECRET, (
        f"auth.password.secretRef must be {ES_SECRET!r} (chart key "
        "global.elasticsearch.auth.password.secretRef)"
    )
    assert pw.get("secretKey") == ES_SECRET_KEY, (
        f"auth.password.secretKey must be {ES_SECRET_KEY!r} (chart key "
        "global.elasticsearch.auth.password.secretKey)"
    )
    assert set(pw) <= {"secretRef", "secretKey"}, (
        f"auth.password must carry ONLY secretRef/secretKey refs, got {sorted(pw)}"
    )


def test_datahub_es_keeps_plaintext_intent() -> None:
    es = _es(_load(DH_VALUES))
    assert es.get("host") == ES_HOST
    assert str(es.get("port")) == ES_PORT
    assert str(es.get("skipcheck")).lower() == "false", (
        "skipcheck must stay false (skipping checks is NOT a fix)"
    )
    assert str(es.get("useSSL")).lower() == "false", (
        "useSSL must stay false (http:// plaintext inside private net)"
    )


def test_datahub_es_auth_matches_opensearch_externalsecret() -> None:
    manifest = yaml.safe_load(OS_ES_MANIFEST.read_text(encoding="utf-8"))
    spec = manifest.get("spec") or {}
    assert (spec.get("target") or {}).get("name") == ES_SECRET
    synced = {e.get("secretKey") for e in spec.get("data") or [] if isinstance(e, dict)}
    assert ES_SECRET_KEY in synced, f"ExternalSecret must sync key {ES_SECRET_KEY!r}"
    es = _es(_load(DH_VALUES))
    pw = ((es.get("auth") or {}).get("password")) or {}
    assert pw.get("secretRef") == (spec.get("target") or {}).get("name"), (
        "values secretRef must EXACTLY equal manifest target.name"
    )
    assert pw.get("secretKey") in synced, (
        "values secretKey must EXACTLY equal a manifest secretKey"
    )


def test_datahub_es_auth_carries_no_literal_credential() -> None:
    """Only exception: `username: admin` (identifier, see module docstring)."""
    es = _es(_load(DH_VALUES))
    auth = es.get("auth") or {}
    assert auth.get("username") == ES_USERNAME, "only `admin` username is allowlisted"
    pw = auth.get("password") or {}
    for key, val in pw.items():
        assert not (isinstance(val, str) and val and key == "value"), (
            f"literal credential at auth.password.{key}"
        )
    dumped = yaml.safe_dump({"auth": auth})
    assert ES_SECRET_KEY in dumped  # key NAME reference, not a literal value


# --- datahub render proofs (UNCHANGED: still renders secretRefs, harmless no-auth) ---


def _es_env_by_name(container: dict) -> dict:
    return {e.get("name"): e for e in (container.get("env") or [])
            if isinstance(e, dict) and e.get("name")}


def _assert_es_secret_auth(container: dict, owner: str) -> bool:
    by_name = _es_env_by_name(container)
    if "ELASTICSEARCH_USERNAME" not in by_name or "ELASTICSEARCH_PASSWORD" not in by_name:
        return False
    user = by_name["ELASTICSEARCH_USERNAME"]
    assert user.get("value") == ES_USERNAME, f"{owner}: USERNAME must be {ES_USERNAME!r}"
    pw = by_name["ELASTICSEARCH_PASSWORD"]
    assert "value" not in pw, f"{owner}: PASSWORD must not carry a literal `value:`"
    ref = (pw.get("valueFrom") or {}).get("secretKeyRef") or {}
    assert ref.get("name") == ES_SECRET, f"{owner}: rendered secret name: {ref}"
    assert ref.get("key") == ES_SECRET_KEY, f"{owner}: rendered secret key: {ref}"
    skip = by_name.get("SKIP_ELASTICSEARCH_CHECK") or {}
    assert str(skip.get("value")).lower() == "false", (
        f"{owner}: SKIP_ELASTICSEARCH_CHECK must stay false, got {skip.get('value')!r}"
    )
    ssl = by_name.get("ELASTICSEARCH_USE_SSL")
    if ssl is not None:
        assert str(ssl.get("value")).lower() == "false", (
            f"{owner}: ELASTICSEARCH_USE_SSL must stay false, got {ssl.get('value')!r}"
        )
    return True


def test_datahub_render_exit_zero() -> None:
    assert isinstance(
        _render_dh(), str
    )


def test_datahub_render_job_and_gms_have_es_secret_auth() -> None:
    """Template proofs: system-update Job (_upgrade.tpl 71-81) AND GMS
    Deployment (deployment.yaml 278-289) render secretKeyRef, no literal.

    Fallback note: against the no-auth backend these envs are UNENFORCED but
    harmless; they are retained so Topics 27/31 re-harden without a values
    change to datahub.
    """
    docs = _docs(_render_dh())
    jobs = [d for d in docs if d.get("kind") == "Job"]
    assert jobs, "render must contain the system-update Job"
    gms = [d for d in docs
           if d.get("kind") == "Deployment"
           and "gms" in str((d.get("metadata") or {}).get("name", ""))]
    assert gms, "render must contain the GMS Deployment"
    found_job = found_gms = False
    for job in jobs:
        containers = ((job.get("spec") or {}).get("template", {}).get("spec", {})
                      .get("containers", []))
        for container in containers:
            if _assert_es_secret_auth(
                    container, f"Job {(job.get('metadata') or {}).get('name')}"):
                found_job = True
    for dep in gms:
        containers = ((dep.get("spec") or {}).get("template", {}).get("spec", {})
                      .get("containers", []))
        for container in containers:
            if _assert_es_secret_auth(
                    container, f"Deployment {(dep.get('metadata') or {}).get('name')}"):
                found_gms = True
    assert found_job, "system-update Job must render ES secretKeyRef auth (no literal)"
    assert found_gms, "GMS Deployment must render ES secretKeyRef auth (no literal)"


def test_datahub_render_keeps_http_url() -> None:
    manifest = _render_dh()
    assert ES_HOST in manifest
    assert "https://opensearch-cluster-master" not in manifest, (
        "render must keep http:// (no https host switch)"
    )
