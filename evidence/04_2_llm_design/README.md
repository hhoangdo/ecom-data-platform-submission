# EDAI2 Evidence Bundle

Canonical, self-consistent evidence for EDAI2 (Topics 22–32) at deployment revision
`4f36cb1d770586fb51bdc065ac9dce0d88b24420`.

## Status

- Overall: **24 pass / 10 missing / 0 pending / 0 fail / 34 total**.
- T27: **Completed, 16/16 screenshots**.
- T31: teardown verified — nodes 0, ingress 0, load balancers 0, forwarding rules 0,
  node pools zero, lease absent.
- Missing screenshots are documented exceptions: T22 (2), T26 (2), T28 (2), T29 (4).
- T25 (Jenkins provenance) and T30 (spot/backup/accessors) retain non-screenshot
  exceptions; they do not change the 34-image count.

## Layout

- `run_manifest.json` — the single canonical manifest. Its `bundle` section lists every
  file in this directory except the manifest itself.
- `screenshots/` — 23 UI screenshots, `ui_manifest.json`, visual review, and Topic 32 source.
  The 24th approved screenshot is Section 03's
  `section03_config_and_training_join.png`, referenced by hash in `external_references`.
- `completion/` — completion records for Topics 22–32.
- `gke/`, `cicd/`, `gateway/`, `observability/`, `rag/`, `tests/`, `security/`,
  `streaming/`, `evaluation/`, `section03/`, `rollbacks/` — supporting machine evidence.

## Verification

```powershell
python scripts/qa/verify_evidence_bundle.py
python scripts/qa/check_ui_manifest_links.py
python scripts/qa/check_ui_manifest_secrets.py
```

After any evidence change, reseal the manifest so the bundle hashes stay valid:

```powershell
python scripts/qa/seal_evidence_bundle.py
```

## Integrity notes

- `bundle.bundle_sha256` is the SHA-256 of the canonical lines
  `path\0sha256\0size\n` sorted by path, for every file except `run_manifest.json`.
- The manifest's own SHA-256 is recorded outside the bundle (cleanup report and
  continuation plan) to avoid a self-referential hash.
- The previous manifest SHA-256 was
  `B5855972E81264B207373F784D20BEF49FE915F6F4F86D40938182270CC7D312`.
  The pre-cleanup state is preserved by the local tag
  `backup/edai2-pre-cleanup-2026-10-23`.

## Historical scope

The trial project was torn down on 2026-10-22. Project IDs, registry paths, bucket
names, and command transcripts in completion records are historical. A new trial must
use a new project, bucket, registry, and credentials; do not reuse the recorded ones.
