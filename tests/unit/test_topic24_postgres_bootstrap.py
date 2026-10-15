from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / "infra/helm/edai2/values/postgres.yaml"
BOOTSTRAP = ROOT / "infra/postgres/edai2/bootstrap-platform-databases.sh"
KUSTOMIZATION = ROOT / "infra/postgres/edai2/kustomization.yaml"


def test_postgres_primary_mounts_readonly_bootstrap_and_registry_sources():
    values = yaml.safe_load(VALUES.read_text(encoding="utf-8"))
    assert values["auth"]["existingSecret"] == "postgres"
    assert values["primary"]["persistence"]["size"] == "16Gi"
    assert values["primary"]["service"]["type"] == "ClusterIP"

    volumes = {volume["name"]: volume for volume in values["primary"]["extraVolumes"]}
    mounts = {mount["name"]: mount for mount in values["primary"]["extraVolumeMounts"]}
    assert volumes["topic24-bootstrap-script"]["configMap"] == {
        "name": "edai2-platform-db-bootstrap",
        "defaultMode": 365,
        "items": [{"key": "script", "path": "script"}],
    }
    assert mounts["topic24-bootstrap-script"]["mountPath"] == "/run/topic24/bootstrap"
    assert mounts["topic24-bootstrap-script"]["readOnly"] is True
    assert volumes["topic24-registry-api-token"]["secret"] == {
        "secretName": "agentregistry",
        "defaultMode": 288,
        "items": [{"key": "api-token", "path": "api-token"}],
    }
    assert mounts["topic24-registry-api-token"]["mountPath"] == "/run/topic24/registry"
    assert mounts["topic24-registry-api-token"]["readOnly"] is True


def test_bootstrap_configmap_generator_uses_checked_in_script():
    kustomization = yaml.safe_load(KUSTOMIZATION.read_text(encoding="utf-8"))
    generator = next(item for item in kustomization["configMapGenerator"]
                     if item["name"] == "edai2-platform-db-bootstrap")
    assert generator["files"] == ["script=bootstrap-platform-databases.sh"]
    assert (KUSTOMIZATION.parent / "bootstrap-platform-databases.sh").is_file()


def test_bootstrap_keeps_credentials_out_of_command_arguments_and_output():
    script = BOOTSTRAP.read_text(encoding="utf-8")
    assert script.index("for required_tool in") < script.index("admin_password_file=")
    assert "curl psql od tr mktemp cat rm" in script
    assert 'IFS= read -r VAULT_TOKEN' in script
    assert 'header = "X-Vault-Token: %s"' in script
    assert '--config "$curl_config"' in script
    assert '--data-binary "@$work_dir/kagent-vault-payload.json"' in script
    assert 'PGPASSWORD="$admin_password" psql "$@"' in script
    assert "export PGHOST=" in script and "unset PGPASSWORD" in script
    assert 'PGPASSWORD="$password" psql' in script
    assert "CREATE ROLE" in script and "IF NOT EXISTS (SELECT FROM pg_roles" in script
    assert "ALTER ROLE" not in script and "DROP ROLE" not in script
    assert "database owner check failed" in script
    assert "existing role password check failed" in script
    assert "-v password=" not in script
    assert 'od -An -N32 -v -tx1 /dev/urandom' in script
    assert 'printf \'topic24 postgres bootstrap: kagent role/database verified\\n\'' in script
    assert 'kagent_url="postgresql://kagent:${kagent_password}@${kagent_host}:5432/kagent?sslmode=disable"' in script
    assert "set +x" in script
    assert "X-Vault-Token:" not in script.split("curl_config=", 1)[1].split("unset VAULT_TOKEN", 1)[1]
    assert script.index('vault_get_status="$(curl') < script.index("ensure_role_database kagent")
    assert script.index('vault_status="$(curl') < script.index("ensure_role_database kagent")
    assert '"options":{"cas":0},"data":{"url":"%s"}' in script
