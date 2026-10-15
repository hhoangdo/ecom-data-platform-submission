"""Create a deterministic allowlisted source archive and a suspended GKE build Job."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import difflib
import re
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "tmp/edai2-gcp/topic24-finalize"
SOURCE = SCRATCH / "src"
UPSTREAM_ARCHIVE = SCRATCH / "substrate-source.tar.gz"
UPSTREAM_LICENSE = next((SCRATCH / "upstream").glob("substrate-*/LICENSE"), None)
BUNDLE = SCRATCH / "substrate-source-topic24-finalize.tar.gz"
CHECKSUM = SCRATCH / "substrate-source-topic24-finalize.tar.gz.sha256"
SOURCE_MANIFEST = SCRATCH / "substrate-source-topic24-finalize.manifest.json"
PROVENANCE = SCRATCH / "remote-build-provenance.json"
JOB_FILE = SCRATCH / "topic24-builder-job.yaml"
KSA_FILE = SCRATCH / "topic24-builder-serviceaccount.yaml"
OPERATOR_STEPS = SCRATCH / "topic24-builder-operator-steps.md"
BUILD_OUTPUT = SCRATCH / "remote-build-output"
PATCH_FILE = ROOT / "infra/substrate/patches/standalone-valkey-0.0.6.patch"

GO_VERSION = "1.26.3"
GO_SHA256 = "2b2cfc7148493da5e73981bffbf3353af381d5f93e789c82c79aff64962eb556"
KO_VERSION = "0.19.1"
KO_SHA256 = "635ac6ea3fd376c935fee597fbb29ab2c2449f49ef1655085fe3aa9c25fed7a5"
KO_CHECKSUMS_SHA256 = "63e7608134e156f26e084f6f28e95698e3dd6a7ec16d9c2bf06141f52fee8dee"
GO_BUILDER_IMAGE = "docker.io/library/golang@sha256:3bf5b04541eb4a37fe62aa1bc9c98a1dec09db9d2e79c1d2eb54e3c9d08dbca9"
GO_BUILDER_INDEX = "sha256:386d475a660466863d9f8c766fec64d7fdad3edac2c6a05020c09534d71edb4b"
BASE_IMAGE = "gcr.io/distroless/static-debian13@sha256:a8a6666cb7b13df7d18fd65b4264c2edafbce92acc0f32c423b5470d7d717665"
BASE_IMAGE_INDEX = "sha256:58133991db06659feaabe0f4e97a35cebf15ef4ea08f8a4c6d2ee5f75e4aa6a0"
PROJECT_ID = "project-a7c45c4e-f589-4b40-b8b"
REGION = "us-central1"
AR_REPOSITORY = "edai2-coordinator"
IMAGE_NAME = "substrate-api-topic24"
PATCH_SOURCE_PATHS = (
    "cmd/ateapi/main.go",
    "cmd/ateapi/internal/store/ateredis/ateredis.go",
    "cmd/ateapi/redis_test.go",
)

EXCLUDED_COMPONENTS = {
    ".git", ".venv", "venv", "env", "environment", "credentials", "credential",
    "secrets", "secret", "state", "states", "datasets", "dataset", "model-cache",
    "models-cache", "terraform-data", "node_modules", "__pycache__",
}
EXCLUDED_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".jks", ".db", ".sqlite", ".sqlite3",
    ".safetensors", ".gguf", ".onnx", ".pt", ".pth", ".bin",
}
EXCLUDED_NAMES = {"kubeconfig", "application_default_credentials.json", "credentials.json", "token"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upstream_source_files() -> tuple[str, dict[str, bytes]]:
    if not UPSTREAM_ARCHIVE.is_file():
        raise SystemExit("immutable upstream source archive is missing")
    with tarfile.open(UPSTREAM_ARCHIVE, "r:gz") as archive:
        roots = {name.split("/", 1)[0] for name in archive.getnames() if "/" in name}
        if len(roots) != 1:
            raise SystemExit("upstream source archive does not have exactly one root")
        root = roots.pop()
        prefix = f"{root}/"
        files = {
            member.name[len(prefix):]: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile() and member.name.startswith(prefix)
        }
    return root, files


def source_patch(upstream_files: dict[str, bytes]) -> tuple[bytes, dict[str, dict[str, str | None]]]:
    patch_parts: list[str] = []
    records: dict[str, dict[str, str | None]] = {}
    for path in PATCH_SOURCE_PATHS:
        current_path = SOURCE / path
        if not current_path.is_file():
            raise SystemExit(f"expected patched source file is missing: {path}")
        current = current_path.read_bytes()
        original = upstream_files.get(path, b"")
        records[path] = {
            "upstream_sha256": digest(original) if path in upstream_files else None,
            "patched_sha256": digest(current),
        }
        patch_parts.extend(difflib.unified_diff(
            original.decode("utf-8").splitlines(keepends=True),
            current.decode("utf-8").splitlines(keepends=True),
            fromfile=f"a/{path}" if path in upstream_files else "/dev/null",
            tofile=f"b/{path}",
        ))
    for path, original in upstream_files.items():
        if path.startswith(("cmd/", "internal/", "pkg/")) and path.endswith(".go"):
            current_path = SOURCE / path
            if current_path.is_file() and path not in PATCH_SOURCE_PATHS:
                if current_path.read_bytes() != original:
                    raise SystemExit(f"unexpected patched Go file outside durable patch set: {path}")
    return "".join(patch_parts).encode("utf-8"), records


def source_files() -> list[tuple[str, bytes]]:
    if not all((SOURCE / name).is_file() for name in ("go.mod", "go.sum", ".ko.yaml")):
        raise SystemExit("patched substrate source tree is incomplete")
    if UPSTREAM_LICENSE is None or not UPSTREAM_LICENSE.is_file():
        raise SystemExit("upstream LICENSE file is missing")
    files: list[tuple[str, bytes]] = []
    for root_name in ("cmd", "internal", "pkg"):
        source_root = SOURCE / root_name
        if not source_root.is_dir():
            raise SystemExit(f"required source directory is missing: {root_name}")
        for path in sorted(source_root.rglob("*")):
            if path.is_symlink():
                raise SystemExit(f"source bundle refuses symlink: {path.relative_to(SOURCE)}")
            if not path.is_file():
                continue
            rel = path.relative_to(SOURCE)
            if {part.casefold() for part in rel.parts} & EXCLUDED_COMPONENTS:
                continue
            if path.name.casefold() in EXCLUDED_NAMES or path.suffix.casefold() in EXCLUDED_SUFFIXES:
                continue
            if path.name.casefold().startswith((".env", "id_rsa", "id_ed25519")):
                continue
            files.append((f"src/{rel.as_posix()}", path.read_bytes()))

    ko_text = (SOURCE / ".ko.yaml").read_text(encoding="utf-8")
    ko_text, base_count = re.subn(
        r"(?m)^defaultBaseImage:\s*gcr\.io/distroless/static-debian13(?:@[^\s]+)?\s*$",
        f"defaultBaseImage: {BASE_IMAGE}", ko_text, count=1)
    ko_text, platform_count = re.subn(
        r"(?ms)^defaultPlatforms:\s*\r?\n(?:[ \t]+-[^\r\n]*\r?\n)+",
        "defaultPlatforms:\n  - linux/amd64\n", ko_text, count=1)
    if base_count != 1 or platform_count != 1:
        raise SystemExit("upstream .ko.yaml does not match the expected distroless/platform contract")
    files.extend([
        ("src/.ko.yaml", ko_text.encode("utf-8")),
        ("src/go.mod", (SOURCE / "go.mod").read_bytes()),
        ("src/go.sum", (SOURCE / "go.sum").read_bytes()),
        ("src/LICENSE", UPSTREAM_LICENSE.read_bytes()),
    ])
    files.sort()
    names = [name for name, _ in files]
    if len(names) != len(set(names)) or not {"src/.ko.yaml", "src/go.mod", "src/go.sum", "src/LICENSE"} <= set(names):
        raise SystemExit("source archive has duplicate or missing root inputs")
    go_files = {name.removeprefix("src/"): data for name, data in files if name.endswith(".go")}
    local_imports: set[str] = set()
    for data in go_files.values():
        local_imports.update(
            match.decode("utf-8")
            for match in re.findall(rb'"github\.com/agent-substrate/substrate/([^"\s]+)"', data)
        )
    for import_path in local_imports:
        package_dir = import_path.replace(".", "/")
        if not any(path.startswith(f"{package_dir}/") and path.endswith(".go") for path in go_files):
            raise SystemExit(f"source bundle is missing local Go import package: {package_dir}")
    _, upstream_files = upstream_source_files()
    source_patch(upstream_files)
    return files


def archive_bytes(files: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for name, data in files:
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return output.getvalue()


def job_manifest(bundle_hash: str) -> dict:
    tag = f"topic24-{bundle_hash[:16]}"
    image_repo = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/{AR_REPOSITORY}/{IMAGE_NAME}"
    command = f"""set -euo pipefail
mkdir -p /workspace/tmp /workspace/bin /workspace/toolchain /workspace/source /workspace/gopath /workspace/gomodcache /workspace/gocache /workspace/sbom /workspace/docker
export TMPDIR=/workspace/tmp GOPATH=/workspace/gopath GOENV=off GOMODCACHE=/workspace/gomodcache GOCACHE=/workspace/gocache GOTOOLCHAIN=local GOFLAGS="-buildvcs=false -p=1" GOMAXPROCS=1 CGO_ENABLED=0 GOOS=linux GOARCH=amd64 DOCKER_CONFIG=/workspace/docker
command -v curl tar sha256sum grep cut >/dev/null
unset GOOGLE_APPLICATION_CREDENTIALS CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE
until [ -f /workspace/READY ]; do sleep 2; done
cd /workspace
test \"$(cut -d' ' -f1 substrate-source-topic24-finalize.tar.gz.sha256)\" = \"$SOURCE_BUNDLE_SHA256\"
sha256sum -c substrate-source-topic24-finalize.tar.gz.sha256
curl -fsSL 'https://go.dev/dl/go{GO_VERSION}.linux-amd64.tar.gz' -o go.tar.gz
printf '%s  %s\\n' '{GO_SHA256}' go.tar.gz | sha256sum -c -
tar -xzf go.tar.gz -C /workspace/toolchain
export GOROOT=/workspace/toolchain/go PATH=/workspace/toolchain/go/bin:/workspace/bin:$PATH
curl -fsSL 'https://github.com/ko-build/ko/releases/download/v{KO_VERSION}/ko_{KO_VERSION}_Linux_x86_64.tar.gz' -o ko.tar.gz
printf '%s  %s\\n' '{KO_SHA256}' ko.tar.gz | sha256sum -c -
tar -xzf ko.tar.gz -C /workspace/bin ko
test \"$(go version)\" = 'go version go{GO_VERSION} linux/amd64'
ko version
curl -fsS -H 'Metadata-Flavor: Google' -o /dev/null 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
tar -xzf substrate-source-topic24-finalize.tar.gz -C /workspace/source
cd /workspace/source/src
grep -F 'defaultBaseImage: {BASE_IMAGE}' .ko.yaml
go test ./cmd/ateapi ./cmd/ateapi/internal/store/ateredis
go build -o /workspace/ateapi-size-check ./cmd/ateapi
test "$(wc -c < /workspace/ateapi-size-check)" -le 536870912
export KO_DOCKER_REPO='{image_repo}'
export CGO_ENABLED=0
unset GOOS GOARCH
ko build --bare --platform=linux/amd64 --tags='{tag}' --sbom=spdx --sbom-dir=/workspace/sbom --image-refs=/workspace/image-refs.txt ./cmd/ateapi | tee /workspace/ko-build.log
sha256sum /workspace/substrate-source-topic24-finalize.tar.gz /workspace/go.tar.gz /workspace/ko.tar.gz > /workspace/verified-inputs.sha256
go version > /workspace/remote-tool-versions.txt
ko version >> /workspace/remote-tool-versions.txt
printf 'KO_DOCKER_REPO=%s\\nBUILD_TAG=%s\\nBASE_IMAGE=%s\\n' \"$KO_DOCKER_REPO\" '{tag}' '{BASE_IMAGE}' >> /workspace/remote-tool-versions.txt
cat /workspace/image-refs.txt
touch /workspace/BUILD_SUCCEEDED
until [ -f /workspace/COLLECTED ]; do sleep 2; done
"""
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "topic24-substrate-api-build", "namespace": "edai2",
                     "labels": {"app.kubernetes.io/name": "topic24-substrate-api-build", "app.kubernetes.io/managed-by": "topic24-local-preparation"}},
        "spec": {
            "suspend": True, "backoffLimit": 0, "activeDeadlineSeconds": 5400,
            "template": {"metadata": {"labels": {"app.kubernetes.io/name": "topic24-substrate-api-build"}},
                         "spec": {
                             "serviceAccountName": "topic24-builder", "automountServiceAccountToken": False,
                             "restartPolicy": "Never", "terminationGracePeriodSeconds": 30,
                             "nodeSelector": {"kubernetes.io/arch": "amd64"},
                             "securityContext": {"runAsNonRoot": True, "runAsUser": 65532, "runAsGroup": 65532, "fsGroup": 65532,
                                                 "seccompProfile": {"type": "RuntimeDefault"}},
                             "containers": [{
                                 "name": "build", "image": GO_BUILDER_IMAGE, "imagePullPolicy": "IfNotPresent",
                                 "command": ["/bin/bash", "-ceu"], "args": [command],
                                 "env": [{"name": "BUILD_TAG", "value": tag},
                                         {"name": "SOURCE_BUNDLE_SHA256", "value": bundle_hash},
                                         {"name": "KO_DOCKER_REPO", "value": image_repo}],
                                 "resources": {"requests": {"cpu": "1", "memory": "4Gi", "ephemeral-storage": "8Gi"},
                                               "limits": {"cpu": "1", "memory": "4Gi", "ephemeral-storage": "8Gi"}},
                                 "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                                     "capabilities": {"drop": ["ALL"]}},
                                 "volumeMounts": [{"name": "workspace", "mountPath": "/workspace"}],
                             }],
                             "volumes": [{"name": "workspace", "emptyDir": {"sizeLimit": "8Gi"}}],
                         }},
        },
    }


def write_generated(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def operator_steps(bundle_hash: str, tag: str) -> str:
    bundle_source = BUNDLE.relative_to(ROOT).as_posix()
    checksum_source = CHECKSUM.relative_to(ROOT).as_posix()
    return f"""# Topic 24 builder handoff (prepared only)

The Job is suspended and has not been applied. The source archive is {BUNDLE.name}, SHA-256 {bundle_hash}; it is built from the finalized source tree and excludes credential, state, model-cache, dataset, and environment content. The Job waits for /workspace/READY, then checks the archive checksum before the remote tests and ko build. After writing BUILD_SUCCEEDED, the Job waits for COLLECTED so its Pod remains Running while results are copied.

Grant direct Workload Identity Federation access on only the existing {AR_REPOSITORY} repository to:

    principal://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/{PROJECT_ID}.svc.id.goog/subject/ns/edai2/sa/topic24-builder

Use the already-authorized operator environment to resolve PROJECT_NUMBER, set PRINCIPAL to the URI above, and run:

    gcloud artifacts repositories add-iam-policy-binding {AR_REPOSITORY} --location={REGION} --project={PROJECT_ID} --member="$PRINCIPAL" --role=roles/artifactregistry.writer

No service-account key, ADC file, or credential Secret belongs in this Job.

Run these relative-path copy commands from the repository root. After the lease and prerequisites are satisfied, apply the KSA and suspended Job manifests. Start the waiting Job, copy the archive and checksum into the Pod, then touch /workspace/READY last. Use the explicit absolute kubeconfig and edai2-gke context:

    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp {bundle_source} topic24-substrate-api-build-<pod-suffix>:/workspace/substrate-source-topic24-finalize.tar.gz
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp {checksum_source} topic24-substrate-api-build-<pod-suffix>:/workspace/substrate-source-topic24-finalize.tar.gz.sha256
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 exec topic24-substrate-api-build-<pod-suffix> -- touch /workspace/READY

Wait for /workspace/BUILD_SUCCEEDED while the Pod remains Running, create `{BUILD_OUTPUT.relative_to(ROOT).as_posix()}`, then retrieve ko-build.log, image-refs.txt, remote-tool-versions.txt, verified-inputs.sha256, and the SPDX SBOM directory there. These exact files are required by the strict live evidence collector. Only after successful copies, signal COLLECTED so the Job can complete:

    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp topic24-substrate-api-build-<pod-suffix>:/workspace/ko-build.log "{BUILD_OUTPUT.relative_to(ROOT).as_posix()}/ko-build.log"
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp topic24-substrate-api-build-<pod-suffix>:/workspace/image-refs.txt "{BUILD_OUTPUT.relative_to(ROOT).as_posix()}/image-refs.txt"
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp topic24-substrate-api-build-<pod-suffix>:/workspace/remote-tool-versions.txt "{BUILD_OUTPUT.relative_to(ROOT).as_posix()}/remote-tool-versions.txt"
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp topic24-substrate-api-build-<pod-suffix>:/workspace/verified-inputs.sha256 "{BUILD_OUTPUT.relative_to(ROOT).as_posix()}/verified-inputs.sha256"
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 cp topic24-substrate-api-build-<pod-suffix>:/workspace/sbom "{BUILD_OUTPUT.relative_to(ROOT).as_posix()}/sbom"
    kubectl --kubeconfig <absolute-kubeconfig> --context edai2-gke -n edai2 exec topic24-substrate-api-build-<pod-suffix> -- touch /workspace/COLLECTED

The build targets only ./cmd/ateapi on linux/amd64 and gives the image a source-hash-derived tag `{tag}`.
"""


def main() -> None:
    files = source_files()
    upstream_root, upstream_files = upstream_source_files()
    patch, patch_records = source_patch(upstream_files)
    archive = archive_bytes(files)
    bundle_hash = digest(archive)
    manifest = {
        "schema_version": 1, "source_root": SOURCE.relative_to(ROOT).as_posix(),
        "upstream_source_directory": UPSTREAM_LICENSE.parent.name,
        "allowlisted_roots": ["src/cmd", "src/internal", "src/pkg", "src/go.mod", "src/go.sum", "src/.ko.yaml", "src/LICENSE"],
        "excluded_content_classes": sorted(EXCLUDED_COMPONENTS | EXCLUDED_NAMES | EXCLUDED_SUFFIXES),
        "file_count": len(files), "uncompressed_bytes": sum(len(data) for _, data in files),
        "module_import_packages": sorted({
            match.decode("utf-8")
            for name, data in files if name.endswith(".go")
            for match in re.findall(rb'"github\.com/agent-substrate/substrate/([^"\s]+)"', data)
        }),
        "files": [{"path": name, "bytes": len(data), "sha256": digest(data)} for name, data in files],
        "archive": BUNDLE.name, "archive_bytes": len(archive), "archive_sha256": bundle_hash,
    }
    write_generated(BUNDLE, archive)
    write_generated(CHECKSUM, f"{bundle_hash}  {BUNDLE.name}\n".encode("ascii"))
    write_generated(SOURCE_MANIFEST, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    write_generated(PATCH_FILE, patch)

    job = job_manifest(bundle_hash)
    job_yaml = yaml.safe_dump(job, sort_keys=False, allow_unicode=True).encode("utf-8")
    write_generated(JOB_FILE, job_yaml)
    ksa_yaml = yaml.safe_dump({
        "apiVersion": "v1", "kind": "ServiceAccount",
        "metadata": {"name": "topic24-builder", "namespace": "edai2",
                     "labels": {"app.kubernetes.io/managed-by": "topic24-local-preparation"}},
        "automountServiceAccountToken": False,
    }, sort_keys=False).encode("utf-8")
    write_generated(KSA_FILE, ksa_yaml)

    revision_path = upstream_root
    revision_match = re.search(r"substrate-([0-9a-f]{40})$", revision_path)
    tag = job["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"]
    provenance = {
        "schema_version": 1, "prepared_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workspace_revision": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
        "upstream_source_revision": revision_match.group(1) if revision_match else None,
        "upstream_source_archive_sha256": digest(UPSTREAM_ARCHIVE.read_bytes()),
        "durable_patch": {"path": PATCH_FILE.relative_to(ROOT).as_posix(), "sha256": digest(patch),
                          "files": patch_records},
        "source_manifest_sha256": digest(SOURCE_MANIFEST.read_bytes()), "source_bundle_sha256": bundle_hash,
        "go": {"version": GO_VERSION, "linux_amd64_archive_sha256": GO_SHA256, "official_source": "https://go.dev/dl/"},
        "ko": {"version": KO_VERSION, "linux_amd64_archive_sha256": KO_SHA256, "checksums_file_sha256": KO_CHECKSUMS_SHA256,
               "official_source": "https://github.com/ko-build/ko/releases/tag/v0.19.1"},
        "builder_image": {"reference": GO_BUILDER_IMAGE, "multiarch_index_digest": GO_BUILDER_INDEX, "source": "Docker Hub OCI Distribution API"},
        "base_image": {"reference": BASE_IMAGE, "multiarch_index_digest": BASE_IMAGE_INDEX, "source": "gcr.io OCI Distribution API"},
        "target": {"project_id": PROJECT_ID, "region": REGION, "artifact_registry_repository": AR_REPOSITORY,
                   "image_name": IMAGE_NAME, "tag": tag},
        "identity": {"kubernetes_service_account": "edai2/topic24-builder",
                     "iam_principal_template": "principal://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/PROJECT_ID.svc.id.goog/subject/ns/edai2/sa/topic24-builder",
                     "artifact_registry_role_scope": f"{REGION}/{AR_REPOSITORY}", "role": "roles/artifactregistry.writer",
                     "credential_files_or_adc": False, "direct_gke_workload_identity": True},
        "job": {"manifest": JOB_FILE.name, "initially_suspended": True, "cpu": "1", "memory": "4Gi",
                "emptydir_limit": "8Gi", "active_deadline_seconds": 5400, "backoff_limit": 0,
                "platform": "linux/amd64", "sbom": "SPDX"},
        "execution": {"published": False, "job_applied": False, "cloud_build_used": False, "docker_used": False},
    }
    write_generated(PROVENANCE, (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode())

    steps = operator_steps(bundle_hash, tag)
    write_generated(OPERATOR_STEPS, steps.encode("utf-8"))
    print(json.dumps({"bundle": BUNDLE.name, "bundle_sha256": bundle_hash, "file_count": len(files),
                      "job": JOB_FILE.name, "suspended": True, "published": False}, sort_keys=True))


if __name__ == "__main__":
    main()
