from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_substrate_uses_private_authenticated_standalone_valkey_and_real_jwt_issuer():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/substrate.yaml").read_text())

    assert values["redis"] == {
        "clusterAddress": "valkey-primary.edai2.svc.cluster.local:6379",
        "mode": "standalone",
        "useIAMAuth": False,
        "passwordFile": "/run/valkey-auth/password",
        "passwordSecretName": "valkey",
        "passwordSecretKey": "password",
    }
    assert values["auth"]["mode"] == "jwt"
    assert values["auth"]["jwt"]["issuer"] == (
        "https://container.googleapis.com/v1/projects/project-a7c45c4e-f589-4b40-b8b/"
        "locations/us-central1-a/clusters/edai2"
    )
    assert values["auth"]["jwt"]["audience"] == "api.edai2.svc"

    api_env = yaml.safe_load((ROOT / "infra/substrate/edai2/api-env.yaml").read_text())
    assert api_env["data"] == {
        "ATE_API_REDIS_MODE": "standalone",
        "ATE_API_REDIS_PASSWORD_FILE": "/run/valkey-auth/password",
    }
    source = (ROOT / "infra/substrate/patches/standalone-valkey-0.0.6.patch").read_text()
    assert 'pflag.String("redis-mode", "cluster"' in source
    assert 'pflag.String("redis-password-file", ""' in source
    assert 'strings.TrimRight(string(passwordBytes), "\\r\\n")' in source
    assert "cannot be enabled together" in source


def test_kagent_uses_narrow_vault_database_role_and_private_gateway():
    values = yaml.safe_load((ROOT / "infra/helm/edai2/values/kagent.yaml").read_text())
    annotations = values["controller"]["podAnnotations"]
    assert values["controller"]["env"] == [
        {"name": "SSL_CERT_DIR", "value": "/etc/edai2-ca"}
    ]
    ca_volume = values["controller"]["volumes"][0]
    assert ca_volume["configMap"]["name"] == "kagent-ateapi-ca"
    assert ca_volume["configMap"]["items"] == [{"key": "ca.crt", "path": "ca.crt"}]
    ca_mount = values["controller"]["volumeMounts"][0]
    assert ca_mount["mountPath"] == "/etc/edai2-ca"
    assert "subPath" not in ca_mount

    assert annotations["vault.hashicorp.com/role"] == "kagent"
    assert annotations["vault.hashicorp.com/agent-inject-secret-kagent-postgres-url"] == (
        "kv/data/edai2/kagent/database"
    )
    assert "{{ .Data.data.url }}" in annotations[
        "vault.hashicorp.com/agent-inject-template-kagent-postgres-url"
    ]
    assert values["database"]["postgres"]["urlFile"] == "/vault/secrets/kagent-postgres-url"
    assert values["proxy"]["url"] == "http://edai2-private-gateway.edai2.svc.cluster.local:8080"

    policy = (ROOT / "infra/security/vault/policies/kagent.hcl").read_text().strip()
    assert policy == 'path "kv/data/edai2/kagent/database" { capabilities = ["read"] }'
