"""Minimal immutable model-cache prefetch for EDAI2 Topic 23 (study-only).

Reads the exact pinned revisions from configs/llm/models.yaml, runs one
Workload-Identity GKE Job that downloads only those revisions (no Hub
fallback), uploads create-only blobs guarded by if_generation_match=0, and
reads each object back at its recorded generation. Evidence is a canonical
manifest plus per-object generations/hashes with no credential.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

CACHE_CAP_BYTES = 5 * 1024 * 1024 * 1024

def dir_manifest(root: str | Path) -> dict[str, str]:
    """Map relative file paths to SHA-256 for every file under root."""
    out: dict[str, str] = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _adoption_identical(refit: str | Path, work: str | Path) -> bool:
    """True when the extracted existing tree matches the fresh tree after top-dir strip."""
    try:
        work_manifest = dir_manifest(work)
        if not work_manifest:
            return False
        children = list(Path(refit).iterdir())
        if len(children) == 1 and children[0].is_dir():
            return dir_manifest(children[0]) == work_manifest
        return dir_manifest(refit) == work_manifest
    except Exception:
        return False


WORKER_PREAMBLE = """\
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from huggingface_hub import snapshot_download
from google.cloud import storage
from google.api_core.exceptions import PreconditionFailed
"""


WORKER_FLOW = """\
gcs_uri = sys.argv[2]
pins = json.loads(sys.argv[3])
bucket_name = gcs_uri.split("/")[2]
prefix = "/".join(gcs_uri.split("/")[3:]).rstrip("/") + "/"
client = storage.Client()
bucket = client.bucket(bucket_name)
entries = []
for pin in pins:
    work = Path(tempfile.mkdtemp())
    snapshot_download(pin["model"], revision=pin["revision"], local_dir=str(work))
    archive = work.parent / (work.name + ".tar.zst")
    subprocess.run(["tar", "--sort=name", "--mtime=@0", "--owner=0", "--group=0", "--numeric-owner",
                    "--zstd", "-cf", str(archive), "-C", str(work.parent), work.name], check=True)
    fresh_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    fresh_bytes = archive.stat().st_size
    blob = bucket.blob(prefix + pin["name"] + ".tar.zst")
    try:
        blob.upload_from_filename(str(archive), if_generation_match=0)
        adopted = False
    except PreconditionFailed:
        existing = work.parent / (work.name + ".existing.tar.zst")
        with open(existing, "wb") as handle:
            blob.download_to_file(handle)
        refit = work.parent / (work.name + ".existing")
        refit.mkdir()
        subprocess.run(["tar", "-xf", str(existing), "-C", str(refit)], check=True)
        if not _adoption_identical(refit, work):
            raise RuntimeError("existing object bytes mismatch for " + pin["name"])
        adopted = True
    blob.reload()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    entries.append({"name": pin["name"], "revision": pin["revision"],
                    "sha256": digest, "bytes": fresh_bytes,
                    "generation": str(blob.generation), "adopted": adopted})
manifest = {"objects": entries}
print(json.dumps(manifest, sort_keys=True))
"""


def worker_source() -> str:
    """Assemble the remote worker from tested helpers (single source of truth)."""
    helpers = "import hashlib\nfrom pathlib import Path\n\n" + inspect.getsource(dir_manifest) + inspect.getsource(_adoption_identical)
    return WORKER_PREAMBLE + helpers + WORKER_FLOW

JOB_TEMPLATE = """\
apiVersion: batch/v1
kind: Job
metadata:
  name: edai2-model-prefetch
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: {ksa}
      containers:
      - name: prefetch
        image: python:3.12-slim
        command:
          - /bin/sh
          - -c
          - |
            {command}
"""


def load_pins(config: dict) -> list[dict]:
    """Return exactly the pinned, fallback-forbidden model revisions."""
    models = (config or {}).get("models") or {}
    pins = []
    for name in ("primary", "comparison", "embedding"):
        entry = models.get(name) or {}
        revision = str(entry.get("hub_revision") or entry.get("tokenizer_revision") or "")
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(f"mutable or missing revision for {name}")
        if entry.get("fallback") != "forbidden":
            raise ValueError(f"hub fallback must be forbidden for {name}")
        pins.append({"name": name, "model": str(entry.get("model")), "revision": revision,
                       "fallback": str(entry.get("fallback"))})
    if len(pins) != 3:
        raise ValueError("exactly three pinned models are required")
    return pins


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def manifest_entry(name: str, revision: str, sha256: str, byte_count: int, generation: str, adopted: bool = False) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("cache object hash must be SHA-256")
    entry = {"bytes": byte_count, "generation": generation, "name": name,
             "revision": revision, "sha256": sha256}
    if adopted:
        entry["adopted"] = True
    entry["entry_sha256"] = hashlib.sha256(canonical(entry).encode("utf-8")).hexdigest()
    return entry


def build_cache_evidence(gcs_uri: str, pins: list[dict], describes: list[dict], hashes: list[str]) -> dict:
    """Build immutable cache evidence from live GCS describes (pure; no I/O)."""
    entries = [
        manifest_entry(
            p["name"], p["revision"], h,
            int(d.get("size", d.get("bytes"))), str(d["generation"]),
        )
        for p, d, h in zip(pins, describes, hashes)
    ]
    if len(entries) != 3:
        raise ValueError("exactly three cached model objects are required")
    total = sum(entry["bytes"] for entry in entries)
    if total > CACHE_CAP_BYTES:
        raise ValueError(f"model cache {total} exceeds 5Gi cap")
    return {
        "gcs_uri": gcs_uri,
        "objects": entries,
        "total_bytes": total,
        "pins": pins,
        "manifest_sha256": hashlib.sha256(canonical({"objects": entries}).encode()).hexdigest(),
    }


def extract_manifest(logs: str | None) -> dict | None:
    """Return the last log line that parses as a manifest object, else None."""
    for line in reversed((logs or "").strip().splitlines()):
        try:
            candidate = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("objects"), list):
            return candidate
    return None


def render_job_yaml(ksa: str, gcs_uri: str, pins_json: str) -> str:
    """Render the prefetch Job with all placeholders substituted (no shell variables left)."""
    import base64
    worker_b64 = base64.b64encode(worker_source().encode("utf-8")).decode("ascii")
    command = (
        "apt-get update -qq && apt-get install -y -qq zstd && pip install -q google-cloud-storage huggingface_hub && python -c "
        + '"import base64,sys;exec(base64.b64decode(sys.argv[1]).decode())" '
        + worker_b64 + ' "' + gcs_uri + '" ' + "'" + pins_json + "'"
    )
    return (JOB_TEMPLATE.replace("{ksa}", ksa).replace("{command}", command))


def _resolve_binary(name: str) -> str:
    """Resolve a binary via PATH (handles Windows .cmd/.exe); fail closed when missing."""
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"{name} not found on PATH; install it and retry")
    return resolved


def _run(*args: str) -> str:
    if not args:
        raise RuntimeError("no command supplied")
    resolved = _resolve_binary(args[0])
    proc = subprocess.run([resolved, *args[1:]], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:4])} failed: {proc.stderr[-500:]}")
    return proc.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default="edai2")
    parser.add_argument("--config", default="configs/llm/models.yaml")
    parser.add_argument("--gcs-uri", required=True)
    parser.add_argument("--ksa", default="edai2-prefetch")
    parser.add_argument("--if-generation-match-zero", action="store_true")
    parser.add_argument("--submit-gke-job", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    if not args.if_generation_match_zero or not args.submit_gke_job:
        print("create-only guarded GKE Job submission is mandatory", file=sys.stderr)
        return 2
    output = Path(args.output)
    if output.exists():
        print("refusing to overwrite existing evidence", file=sys.stderr)
        return 2
    pins = load_pins(yaml.safe_load(Path(args.config).read_text(encoding="utf-8")))
    pins_json = json.dumps(pins)
    job_yaml = render_job_yaml(args.ksa, args.gcs_uri, pins_json)
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        handle.write(job_yaml)
        job_path = handle.name
    base = ["kubectl", "--kubeconfig", args.kubeconfig, "--context", args.context, "-n", args.namespace]
    try:
        _run(*base, "apply", "-f", job_path)
        manifest = None
        for _ in range(60):
            status = json.loads(_run(*base, "get", "job/edai2-model-prefetch", "-o", "json"))
            succeeded = (status.get("status") or {}).get("succeeded", 0)
            failed = (status.get("status") or {}).get("failed", 0)
            if succeeded == 1 or failed:
                break
            time.sleep(60)
        else:
            raise RuntimeError("prefetch job did not finish within 60 minutes")
        status = json.loads(_run(*base, "get", "job/edai2-model-prefetch", "-o", "json"))
        if (status.get("status") or {}).get("succeeded", 0) != 1:
            print("prefetch job failed; job retained for inspection", file=sys.stderr)
            return 3
        logs = _run(*base, "logs", "job/edai2-model-prefetch")
        manifest = extract_manifest(logs)
        if manifest is None:
            print("prefetch job produced no manifest; job retained for inspection", file=sys.stderr)
            return 3
        objects = manifest.get("objects") or []
        if len(objects) != 3:
            raise RuntimeError(f"expected 3 prefetched objects, got {len(objects)}")
        total = 0
        entries = []
        for item in objects:
            describe = json.loads(_run("gcloud", "storage", "objects", "describe",
                                       f"{args.gcs_uri.rstrip('/')}/{item['name']}.tar.zst",
                                       "--format=json"))
            if str(describe.get("generation")) != str(item["generation"]):
                raise RuntimeError(f"generation mismatch for {item['name']}")
            total += int(item["bytes"])
            entries.append(manifest_entry(item["name"], item["revision"],
                                          item["sha256"], int(item["bytes"]), str(item["generation"]),
                                          bool(item.get("adopted", False))))
        if total > CACHE_CAP_BYTES:
            raise RuntimeError(f"model cache {total} exceeds 5Gi cap")
        payload = {"gcs_uri": args.gcs_uri, "objects": entries,
                   "total_bytes": total, "pins": pins,
                   "manifest_sha256": hashlib.sha256(canonical({"objects": entries}).encode()).hexdigest()}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _run(*base, "delete", "job", "edai2-model-prefetch", "--ignore-not-found")
    finally:
        Path(job_path).unlink(missing_ok=True)
    print("MODEL_CACHE=OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
