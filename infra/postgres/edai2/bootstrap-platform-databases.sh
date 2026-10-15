#!/usr/bin/env bash
set -Eeuo pipefail
set +x
umask 077
fail() { printf 'topic24 postgres bootstrap: %s\n' "$1" >&2; exit 1; }
for required_tool in curl psql od tr mktemp cat rm; do
  command -v "$required_tool" >/dev/null 2>&1 || { printf 'topic24 postgres bootstrap: requires curl, psql, od, tr, mktemp, cat, and rm\n' >&2; exit 2; }
done
readonly vault_addr="http://vault.vault.svc.cluster.local:8200"
readonly kagent_vault_path="kv/data/edai2/kagent/database"
readonly pg_admin_user="postgres"
readonly pg_host="127.0.0.1"
readonly pg_port="5432"
readonly kagent_host="postgres-postgresql.edai2.svc.cluster.local"
work_dir="$(mktemp -d /tmp/topic24-pg-bootstrap.XXXXXX)" || fail "could not create private workspace"
readonly work_dir
trap 'unset VAULT_TOKEN PGPASSWORD admin_password registry_password decoded_kagent_password kagent_password kagent_url; rm -rf -- "$work_dir"' EXIT

admin_password_file="${POSTGRES_PASSWORD_FILE:-}"
[[ -n "$admin_password_file" && -r "$admin_password_file" ]] || fail "PostgreSQL admin password file is unavailable"
admin_password="$(<"$admin_password_file")"
[[ -n "$admin_password" ]] || fail "PostgreSQL admin password file is empty"
registry_password_file="/run/topic24/registry/api-token"
[[ -r "$registry_password_file" ]] || fail "mounted registry credential is unavailable"
registry_password="$(<"$registry_password_file")"
[[ -n "$registry_password" ]] || fail "mounted registry credential is empty"
export PGHOST="$pg_host" PGPORT="$pg_port" PGUSER="$pg_admin_user" PGDATABASE=postgres
unset PGPASSWORD

VAULT_TOKEN=""
IFS= read -r VAULT_TOKEN || true
[[ "$VAULT_TOKEN" =~ ^[A-Za-z0-9._/+=-]+$ ]] || fail "Vault admin token was not provided on stdin"
curl_config="$work_dir/curl.conf"
printf 'silent\nshow-error\nconnect-timeout = 5\nmax-time = 15\nheader = "X-Vault-Token: %s"\n' "$VAULT_TOKEN" > "$curl_config"
unset VAULT_TOKEN

vault_response="$work_dir/vault-response.json"
kagent_url_file="$work_dir/kagent-url"
parse_sql="$work_dir/parse-vault-json.sql"
pg_sql="$work_dir/bootstrap.sql"
pg_output="$work_dir/psql-output"
psql_admin() { PGPASSWORD="$admin_password" psql "$@"; }
vault_get_status="$(curl --config "$curl_config" --output "$vault_response" --write-out '%{http_code}' "$vault_addr/v1/$kagent_vault_path" 2>/dev/null)" || fail "Vault lookup failed"
kagent_password=""
kagent_url=""
case "$vault_get_status" in
  200)
    vault_json_hex="$(od -An -v -tx1 "$vault_response" | tr -d ' \n')"
    [[ "$vault_json_hex" =~ ^([0-9a-fA-F]{2})+$ ]] || fail "Vault response was not valid JSON input"
    printf "SELECT convert_from(decode('%s','hex'),'UTF8')::jsonb #>> '{data,data,url}';\n" "$vault_json_hex" > "$parse_sql"
    if ! psql_admin -XAtq --no-password -v ON_ERROR_STOP=1 -f "$parse_sql" > "$kagent_url_file" 2>/dev/null; then
      fail "Vault database URL could not be parsed"
    fi
    mapfile -t kagent_urls < "$kagent_url_file"
    [[ "${#kagent_urls[@]}" -eq 1 ]] || fail "Vault database URL was not a single value"
    kagent_url="${kagent_urls[0]}"
    [[ -n "$kagent_url" ]] || fail "Vault database URL is empty"
    ;;
  404)
    resource_state="$(psql_admin -XAtq --no-password -F '|' -v ON_ERROR_STOP=1 -c "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = 'kagent'), EXISTS (SELECT FROM pg_database WHERE datname = 'kagent');" 2>/dev/null)" || fail "PostgreSQL resource preflight failed"
    [[ "$resource_state" == "f|f" ]] || fail "Vault URL is absent but kagent role or database already exists"
    kagent_password="$(od -An -N32 -v -tx1 /dev/urandom | tr -d ' \n')"
    [[ "$kagent_password" =~ ^[0-9a-f]{64}$ ]] || fail "could not generate kagent database credential"
    kagent_url="postgresql://kagent:${kagent_password}@${kagent_host}:5432/kagent?sslmode=disable"
    printf '{"options":{"cas":0},"data":{"url":"%s"}}\n' "$kagent_url" > "$work_dir/kagent-vault-payload.json"
    vault_status="$(curl --config "$curl_config" --request PUT --header 'Content-Type: application/json' --data-binary "@$work_dir/kagent-vault-payload.json" --output /dev/null --write-out '%{http_code}' "$vault_addr/v1/$kagent_vault_path" 2>/dev/null)" || fail "Vault credential write failed"
    [[ "$vault_status" == "200" ]] || fail "Vault credential write returned an unexpected status"
    ;;
  *) fail "Vault lookup returned an unexpected status" ;;
esac

url_prefix="postgresql://kagent:"
url_suffix="@${kagent_host}:5432/kagent?sslmode=disable"
[[ "$kagent_url" == "$url_prefix"*"${url_suffix}" ]] || fail "Vault database URL target did not match kagent"
encoded_kagent_password="${kagent_url#"$url_prefix"}"
encoded_kagent_password="${encoded_kagent_password%"$url_suffix"}"
[[ -n "$encoded_kagent_password" && "$encoded_kagent_password" =~ ^[A-Za-z0-9._~%-]+$ ]] || fail "Vault kagent password encoding is invalid"
remaining_encoded="$encoded_kagent_password"
while [[ "$remaining_encoded" == *%* ]]; do
  encoded_suffix="${remaining_encoded#*%}"
  [[ "$encoded_suffix" =~ ^[0-9A-Fa-f]{2} ]] || fail "Vault kagent password escape is invalid"
  remaining_encoded="${encoded_suffix:2}"
done
decode_format="${encoded_kagent_password//%/\\x}"
decoded_kagent_password="$(printf '%b' "$decode_format")"
[[ -n "$decoded_kagent_password" ]] || fail "Vault kagent password is empty"

ensure_role_database() {
  local role="$1" database="$2" password="$3" password_hex
  local role_state database_state owner_state login_database
  case "$role:$database" in
    langfuse:langfuse|agentregistry:agentregistry|kagent:kagent) ;;
    *) fail "unsupported database identity" ;;
  esac
  local resource_state
  resource_state="$(psql_admin -XAtq --no-password -F '|' -v ON_ERROR_STOP=1 \
    -c "SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = '$role'), EXISTS (SELECT FROM pg_database WHERE datname = '$database'), COALESCE((SELECT pg_get_userbyid(datdba) = '$role' FROM pg_database WHERE datname = '$database'), true);" \
    2>/dev/null)" || fail "PostgreSQL resource preflight failed for $role"
  IFS='|' read -r role_state database_state owner_state <<< "$resource_state"
  [[ "$owner_state" == "t" ]] || fail "database owner check failed for $database"
  if [[ "$role_state" == "t" ]]; then
    login_database="postgres"
    [[ "$database_state" == "t" ]] && login_database="$database"
    if ! PGPASSWORD="$password" psql -XAtq --no-password -h "$pg_host" -p "$pg_port" \
      -U "$role" -d "$login_database" -v ON_ERROR_STOP=1 \
      -c "SELECT current_user = '$role';" > "$pg_output" 2>/dev/null; then
      fail "existing role password check failed for $role"
    fi
    [[ "$(<"$pg_output")" == "t" ]] || fail "existing role identity check failed for $role"
  fi
  password_hex="$(printf '%s' "$password" | od -An -v -tx1 | tr -d ' \n')"
  [[ -n "$password_hex" && "$password_hex" =~ ^([0-9a-f]{2})+$ ]] || fail "database credential encoding failed"
  cat > "$pg_sql" <<SQL
DO \$topic24\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$role') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$role', convert_from(decode('$password_hex','hex'),'UTF8'));
  END IF;
END
\$topic24\$;
SELECT format('CREATE DATABASE %I OWNER %I', '$database', '$role')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')
\gexec
DO \$topic24\$
BEGIN
  IF NOT EXISTS (
    SELECT FROM pg_database
    WHERE datname = '$database' AND pg_get_userbyid(datdba) = '$role'
  ) THEN
    RAISE EXCEPTION 'database owner validation failed';
  END IF;
END
\$topic24\$;
SQL
  if ! psql_admin -Xq --no-password -v ON_ERROR_STOP=1 -f "$pg_sql" > /dev/null 2>/dev/null; then
    fail "role or database creation/ownership check failed for $role"
  fi
  if ! PGPASSWORD="$password" psql -XAtq --no-password -h "$pg_host" -p "$pg_port" -U "$role" -d "$database" -v ON_ERROR_STOP=1 -c "SELECT CASE WHEN current_user = '$role' AND current_database() = '$database' THEN 'ok' ELSE 'invalid' END;" > "$pg_output" 2>/dev/null; then
    fail "password connection check failed for $role"
  fi
  [[ "$(<"$pg_output")" == "ok" ]] || fail "password connection identity check failed for $role"
}

ensure_role_database langfuse langfuse "$admin_password"
printf 'topic24 postgres bootstrap: langfuse role/database verified\n'
ensure_role_database agentregistry agentregistry "$registry_password"
printf 'topic24 postgres bootstrap: agentregistry role/database verified\n'
ensure_role_database kagent kagent "$decoded_kagent_password"
printf 'topic24 postgres bootstrap: kagent role/database verified\n'
