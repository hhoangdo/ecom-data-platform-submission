from __future__ import annotations

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location("capture", Path("scripts/qa/capture_edai2_evidence.py"))
assert spec and spec.loader
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

manifest = json.loads(Path("evidence/04_2_llm_design/screenshots/ui_manifest.json").read_text(encoding="utf-8"))
for entry in manifest:
    for linked in entry.get("linked_machine_evidence", []):
        payload = json.loads(Path(linked["path"]).read_text(encoding="utf-8"))
        if capture._has_secret(payload):
            print("SECRET", entry["path"], linked["path"])
            text = json.dumps(payload)
            print("matches", capture._SECRET.findall(text)[:10])
        else:
            print("OK", entry["path"], linked["path"])
