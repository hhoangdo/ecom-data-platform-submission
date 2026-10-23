from __future__ import annotations

import hashlib
import json
from pathlib import Path

manifest = json.loads(Path("evidence/04_2_llm_design/screenshots/ui_manifest.json").read_text(encoding="utf-8"))
for entry in manifest:
    for linked in entry.get("linked_machine_evidence", []):
        path = Path(linked["path"])
        exists = path.is_file()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if exists else None
        if not exists or digest != linked["sha256"]:
            print("BAD", entry["path"], linked["path"], "exists", exists, "expected", linked["sha256"], "actual", digest)
        else:
            print("OK", entry["path"], linked["path"])
