"""Topic 24 DEFECT 1: cert-manager values must use only real chart keys (local-only).

Live failure: `helm upgrade --install cert-manager jetstack/cert-manager
-n cert-manager -f infra/helm/edai2/values/cert-manager.yaml --version 1.18.2`
fails schema validation: `additional properties 'acme','service' not allowed`.

Schema source (inspected 2026-10-08, metadata-only, no cluster touch):
  `helm repo add jetstack https://charts.jetstack.io --force-update`
  `helm show values jetstack/cert-manager --version 1.18.2`
  + `values.schema.json` `$defs/helm-values/properties` has
  `additionalProperties: false` with NO `service` and NO `acme` keys.
Reproduced locally: `helm template testcm <pulled-chart>
-f infra/helm/edai2/values/cert-manager.yaml` errors with the same message.

Topic 24 is PRIVATE core (no public ingress; ACME/public belongs to
Topics 27/31 per tmp/edai2-plan/execution-v1/gcp/24-compact-platform-install.md).
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES_FILE = ROOT / "infra/helm/edai2/values/cert-manager.yaml"

# Top-level keys allowed by cert-manager v1.18.2 values.schema.json
# ($defs/helm-values/properties, additionalProperties: false).
# Source: `helm show values jetstack/cert-manager --version 1.18.2`
# + pulled chart values.schema.json (see task investigation log).
# This test pins only the keys the fix uses plus the two known-bad keys'
# absence; the full sorted property list is documented in the fix rationale.
ALLOWED_TOP_LEVEL_KEYS = {
    "global",
    "installCRDs",
    "crds",
    "replicaCount",
    "strategy",
    "podDisruptionBudget",
    "featureGates",
    "maxConcurrentChallenges",
    "image",
    "clusterResourceNamespace",
    "namespace",
    "serviceAccount",
    "enableCertificateOwnerRef",
    "config",
    "dns01RecursiveNameservers",
    "dns01RecursiveNameserversOnly",
    "disableAutoApproval",
    "approveSignerNames",
    "extraArgs",
    "extraEnv",
    "resources",
    "securityContext",
    "containerSecurityContext",
    "volumes",
    "volumeMounts",
    "podLabels",
    "hostAliases",
    "nodeSelector",
    "ingressShim",
    "affinity",
    "tolerations",
    "topologySpreadConstraints",
    "livenessProbe",
    "enableServiceLinks",
    "prometheus",
    "webhook",
    "cainjector",
    "acmesolver",
    "startupapicheck",
    "extraObjects",
    "creator",
    "enabled",
    "deploymentAnnotations",
    "podAnnotations",
    "podDnsConfig",
    "podDnsPolicy",
    "serviceAnnotations",
    "serviceIPFamilies",
    "serviceIPFamilyPolicy",
    "serviceLabels",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "fullnameOverride",
    "nameOverride",
}


def _load_values() -> dict:
    loaded = yaml.safe_load(VALUES_FILE.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), "cert-manager values must parse as a dict"
    return loaded


def test_cert_manager_values_parses_as_dict() -> None:
    assert VALUES_FILE.is_file()
    assert isinstance(_load_values(), dict)


def test_cert_manager_values_has_no_known_bad_keys() -> None:
    values = _load_values()
    assert "service" not in values, "chart has no top-level `service` key (schema rejects it)"
    assert "acme" not in values, "chart has no top-level `acme` key (schema rejects it; ACME belongs to Topics 27/31)"


def test_cert_manager_values_uses_only_real_chart_keys() -> None:
    values = _load_values()
    unknown = set(values) - ALLOWED_TOP_LEVEL_KEYS
    assert not unknown, f"unknown top-level keys not in chart schema: {sorted(unknown)}"


def test_cert_manager_values_is_minimal_private_install() -> None:
    values = _load_values()
    # crds.enabled=true: fail-fast `helm upgrade --install` installs CRDs
    # without a separate kubectl apply (chart default false would leave CRDs missing).
    assert values.get("crds", {}).get("enabled") is True
    # replicaCount=1: compact single replica for core capacity ceiling
    # (platform aggregate 3.00 CPU/18Gi; cf. plan Global Constraints).
    assert values.get("replicaCount") == 1
