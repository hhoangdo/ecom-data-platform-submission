"""Manifest-derived local drift API smoke client."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from vina_bim_shop.llm.section03_ingestion import Section03Loader


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--section03-manifest", required=True)
    parser.add_argument("--candidate-days", type=int, required=True)
    parser.add_argument("--id")
    parser.add_argument("--output", required=True)
    parser.add_argument("--status-output", required=True)
    args = parser.parse_args()
    manifest = Section03Loader(args.section03_manifest).verify_only().manifest
    baseline = date.fromisoformat(manifest["consumer_contract"]["feature_health"]["baseline_date"])
    candidate_end = date.fromisoformat(manifest["consumer_contract"]["feature_health"]["monitoring_end"]) + timedelta(days=1)
    candidate_start = candidate_end - timedelta(days=args.candidate_days)
    body = {"baseline_window": {"start": f"{baseline - timedelta(days=6)}T00:00:00Z", "end": f"{baseline + timedelta(days=1)}T00:00:00Z"}, "candidate_window": {"start": f"{candidate_start}T00:00:00Z", "end": f"{candidate_end}T00:00:00Z"}}
    if args.id: body["id"] = args.id
    request = Request(args.base_url.rstrip("/") + "/v1/drift/detect", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=5) as response: status, payload = response.status, response.read().decode()
    except HTTPError as error:
        status, payload = error.code, error.read().decode()
    Path(args.output).write_text(payload + "\n", encoding="utf-8")
    Path(args.status_output).write_text(str(status) + "\n", encoding="utf-8")
    return 0 if status in {200, 409} else 1


if __name__ == "__main__":
    raise SystemExit(main())
