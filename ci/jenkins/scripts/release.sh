#!/usr/bin/env bash
set -euo pipefail

readonly TRIVY_VERSION="trivy_0.70.0"
readonly TRIVY_SHA256="8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9"
readonly CRANE_VERSION="crane_0.21.7"
readonly CRANE_SHA256="1a57bc98207fa1c0d04bf760699099e26f8383499bfd55b99c1b919a928a7230"

require_commit() {
  [[ "${GIT_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]] || { echo "full lowercase GIT_COMMIT is required" >&2; exit 1; }
}

require_workload_identity() {
  [[ -n "${KUBERNETES_SERVICE_HOST:-}" ]] || { echo "Workload Identity requires a Kubernetes service account" >&2; exit 1; }
  [[ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]] || { echo "static registry credentials are forbidden" >&2; exit 1; }
}

verify_download() {
  local archive="$1" expected="$2"
  echo "${expected}  ${archive}" | sha256sum --check --status
}

install_tools() {
  local tools_dir="${TOOLS_DIR:-$PWD/.ci-tools}"
  local trivy_archive="${tools_dir}/trivy.tar.gz"
  local crane_archive="${tools_dir}/crane.tar.gz"
  mkdir -p "$tools_dir/bin"
  curl --fail --silent --show-error --location "https://github.com/aquasecurity/trivy/releases/download/v0.70.0/trivy_0.70.0_Linux-64bit.tar.gz" --output "$trivy_archive"
  verify_download "$trivy_archive" "$TRIVY_SHA256"
  tar --extract --gzip --file "$trivy_archive" --directory "$tools_dir/bin" trivy
  curl --fail --silent --show-error --location "https://github.com/google/go-containerregistry/releases/download/v0.21.7/go-containerregistry_Linux_x86_64.tar.gz" --output "$crane_archive"
  verify_download "$crane_archive" "$CRANE_SHA256"
  tar --extract --gzip --file "$crane_archive" --directory "$tools_dir/bin" crane
  export PATH="$tools_dir/bin:$PATH"
}

archive_path() { printf 'artifacts/%s.tar' "$1"; }
archive_sha256() { sha256sum "$(archive_path "$1")" | awk '{print $1}'; }
archive_manifest_digest() { crane digest --tarball "$(archive_path "$1")"; }

scan_archive() {
  local job="$1" archive
  archive="$(archive_path "$job")"
  install_tools
  mkdir -p reports
  find "${TRIVY_DB_DIR:?}" -type f -mmin -1440 -print -quit | grep -q . || { echo "Trivy database is older than 24 hours" >&2; exit 1; }
  trivy image --input "$archive" --scanners vuln,secret,license --severity CRITICAL --exit-code 1 --format json --output "reports/${job}-trivy.json"
  trivy image --input "$archive" --scanners vuln,secret,license --format cyclonedx --output "reports/${job}-trivy.cdx.json"
  ! grep -E 'GPL-3\\.0|AGPL-3\\.0' "reports/${job}-trivy.json"
  printf '%s\n' "$(archive_sha256 "$job")" > "reports/${job}-archive-sha256.txt"
  printf '%s\n' "$(archive_manifest_digest "$job")" > "reports/${job}-archive-manifest-digest.txt"
}

push_archive() {
  local job="$1" archive_sha remote_manifest_digest
  require_commit
  require_workload_identity
  install_tools
  archive_sha="$(archive_sha256 "$job")"
  crane push "$(archive_path "$job")" "${AR_LOCATION:?}-docker.pkg.dev/${GCP_PROJECT_ID:?}/${job}:${GIT_COMMIT}"
  remote_manifest_digest="$(crane digest "${AR_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/${job}:${GIT_COMMIT}")"
  [[ "$(archive_manifest_digest "$job")" == "$remote_manifest_digest" ]] || { echo "archive and remote manifest digests differ" >&2; exit 1; }
  printf '%s\n' "$archive_sha" > "reports/${job}-archive-sha256.txt"
  printf '%s\n' "$remote_manifest_digest" > "reports/${job}-remote-manifest-digest.txt"
}

helm_atomic() {
  local job="$1" chart_kind="$2" values_file="$3" workload_name="$4" repository="$5"
  require_commit
  test -s "reports/${job}-remote-manifest-digest.txt"
  [[ -n "${EDAI2_KUBECONFIG:-}" && -n "${EDAI2_KUBE_CONTEXT:-}" ]] || { echo "explicit kubeconfig and context are required" >&2; exit 1; }
  [[ -f "$values_file" ]] || { echo "release values file is missing" >&2; exit 1; }
  local substrate_args=()
  case "${job}:${chart_kind}:${values_file}:${workload_name}:${repository}" in
    edai2-rag-index:worker:infra/helm/edai2/worker/values.yaml:rag-index:edai2-rag-index|edai2-feast-offline-writer:worker:infra/helm/edai2/worker/values.yaml:feast-offline-writer:edai2-feast-offline-writer|edai2-feast-online-writer:worker:infra/helm/edai2/worker/values.yaml:feast-online-writer:edai2-feast-online-writer) ;;
    edai2-retrieval-agent:service-agent:infra/helm/edai2/values/retrieval-agent.yaml:retrieval-agent:edai2-retrieval-agent|edai2-drift-agent:service-agent:infra/helm/edai2/values/drift-agent.yaml:drift-agent:edai2-drift-agent|edai2-coordinator:service-agent:infra/helm/edai2/values/coordinator-agent.yaml:coordinator:edai2-coordinator)
      [[ -n "${SUBSTRATE_BUCKET_NAME:-}" ]] || { echo "SUBSTRATE_BUCKET_NAME is required" >&2; exit 1; }
      substrate_args=(--set-string "substrate.bucketName=${SUBSTRATE_BUCKET_NAME}")
      ;;
    *) echo "unknown chart or release metadata" >&2; exit 1 ;;
  esac
  helm upgrade --install "$job" "infra/helm/edai2/${chart_kind}" --atomic --wait --kubeconfig "$EDAI2_KUBECONFIG" --kube-context "$EDAI2_KUBE_CONTEXT" -f "$values_file" --set-string "image.repository=${AR_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/${repository}" --set-string "image.tag=${GIT_COMMIT}" --set-string "workload.name=${workload_name}" "${substrate_args[@]}"
}

smoke_eval() { test -s "reports/$1-remote-manifest-digest.txt"; }
rollback_proof() { test -s "reports/$1-archive-manifest-digest.txt"; }

case "${1:-}" in
  helm_atomic) helm_atomic "${2:?job is required}" "${3:?chart kind is required}" "${4:?values file is required}" "${5:?workload name is required}" "${6:?repository is required}" ;;
  scan_archive|push_archive|smoke_eval|rollback_proof) "$1" "${2:?job is required}" ;;
  *) echo "usage: $0 {scan_archive|push_archive|helm_atomic|smoke_eval|rollback_proof} job" >&2; exit 2 ;;
esac
