from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence" / "04_2_llm_design"
MANIFEST = EVIDENCE / "run_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_digest(files: list[dict[str, object]]) -> str:
    canonical = "".join(
        f"{entry['path']}\0{entry['sha256']}\0{entry['size_bytes']}\n"
        for entry in sorted(files, key=lambda item: str(item["path"]))
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> int:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bundle = manifest.get("bundle")
    if not isinstance(bundle, dict):
        print("ERROR: manifest has no bundle section")
        return 1

    files = bundle.get("files")
    if not isinstance(files, list):
        print("ERROR: bundle.files is missing")
        return 1

    seen: set[str] = set()
    for entry in files:
        rel = str(entry.get("path", ""))
        if rel in seen:
            errors.append(f"duplicate entry: {rel}")
            continue
        seen.add(rel)
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing: {rel}")
            continue
        actual = sha256(path)
        if actual != entry.get("sha256"):
            errors.append(f"sha mismatch: {rel}")
        if path.stat().st_size != entry.get("size_bytes"):
            errors.append(f"size mismatch: {rel}")

    manifest_rel = MANIFEST.relative_to(ROOT).as_posix()
    for path in EVIDENCE.rglob("*"):
        if not path.is_file() or path.resolve() == MANIFEST.resolve():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel not in seen:
            errors.append(f"not indexed: {rel}")

    if bundle.get("file_count") != len(files):
        errors.append("bundle.file_count mismatch")
    if bundle.get("total_size_bytes") != sum(int(entry["size_bytes"]) for entry in files):
        errors.append("bundle.total_size_bytes mismatch")
    if bundle.get("bundle_sha256") != bundle_digest(files):
        errors.append("bundle_sha256 mismatch")

    for entry in manifest.get("external_references", []):
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path", ""))
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"external missing: {rel}")
        elif sha256(path) != entry.get("sha256") or path.stat().st_size != entry.get("size_bytes"):
            errors.append(f"external mismatch: {rel}")

    if errors:
        print(f"FAIL: {len(errors)} problem(s)")
        for error in errors:
            print(" -", error)
        return 1
    print(
        "OK: "
        f"{len(files)} files, {bundle['total_size_bytes']} bytes, "
        f"bundle_sha256={bundle['bundle_sha256']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
