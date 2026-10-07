from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

DEFAULT_LEASE_FILE = "tmp/edai2-gcp/topic23-lease.json"
EXPECTED_CONTEXT = "edai2-gke"


def parse_ttl(value: str) -> int:
    if not value.endswith("h") or not value[:-1].isdigit():
        raise ValueError("TTL must use non-negative whole-hour h notation")
    hours = int(value[:-1])
    if not 0 < hours <= 6:
        raise ValueError("TTL must be between 1h and 6h")
    return hours


def render_profile(profiles: dict, profile: str, ttl: str | None, *, dry_run: bool) -> dict:
    if profile not in profiles["profiles"]:
        raise ValueError("unknown profile")
    if not dry_run:
        raise ValueError("only --dry-run is available in Topic 17")
    if profile == "suspended":
        if ttl is not None:
            raise ValueError("suspended does not accept TTL")
        ttl_hours = 0
    else:
        if ttl is None:
            raise ValueError("active profiles require TTL")
        ttl_hours = parse_ttl(ttl)
    return {"dry_run": True, "profile": profile, "ttl_hours": ttl_hours, "resources": profiles["profiles"][profile]}


def acquire_lease(lease_file: str | Path, *, owner: str, profile: str, ttl_hours: int, commit_sha: str) -> dict:
    """Record the sole runtime lease; refuse when another lease is held."""
    path = Path(lease_file)
    if path.exists():
        raise ValueError("a session lease is already held")
    if not owner or not re_fullmatch_sha(commit_sha):
        raise ValueError("owner and 40-hex commit SHA are mandatory")
    lease = {"owner": owner, "profile": profile, "ttl_hours": ttl_hours,
             "commit_sha": commit_sha, "acquired_at_utc": datetime.now(UTC).isoformat()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lease, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lease


def release_lease(lease_file: str | Path, *, owner: str, evidence_manifest: str | None = None) -> None:
    """Release the lease only for its owner and an existing evidence manifest."""
    path = Path(lease_file)
    if not path.exists():
        raise ValueError("no session lease is held")
    lease = json.loads(path.read_text(encoding="utf-8"))
    if lease.get("owner") != owner:
        raise ValueError("lease owner mismatch")
    if evidence_manifest is not None and not Path(evidence_manifest).exists():
        raise ValueError("required evidence manifest is missing")
    path.unlink()


def re_fullmatch_sha(value: str) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def check_kube_target(kubeconfig: str, context: str) -> None:
    """Refuse anything but the dedicated kubeconfig context; never touch the default."""
    if context != EXPECTED_CONTEXT:
        raise ValueError(f"only context {EXPECTED_CONTEXT} is authorized")
    text = Path(kubeconfig).read_text(encoding="utf-8")
    if EXPECTED_CONTEXT not in text:
        raise ValueError("kubeconfig does not contain the authorized context")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=("suspended", "core", "rubric-evidence"))
    parser.add_argument("--ttl")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--kubeconfig")
    parser.add_argument("--context")
    parser.add_argument("--stage", choices=("vault", "platform"))
    parser.add_argument("--owner")
    parser.add_argument("--commit-sha")
    parser.add_argument("--lease-file", default=DEFAULT_LEASE_FILE)
    parser.add_argument("--acquire-session-lease", action="store_true")
    parser.add_argument("--release-session-lease", action="store_true")
    parser.add_argument("--require-evidence-manifest")
    args = parser.parse_args(argv)
    try:
        if args.kubeconfig or args.context:
            if not (args.kubeconfig and args.context):
                raise ValueError("kubeconfig and context are required together")
            check_kube_target(args.kubeconfig, args.context)
        if args.acquire_session_lease:
            if args.ttl is None or not args.owner or not args.commit_sha:
                raise ValueError("lease acquisition requires --ttl, --owner, and --commit-sha")
            lease = acquire_lease(args.lease_file, owner=args.owner, profile=args.profile,
                                  ttl_hours=parse_ttl(args.ttl), commit_sha=args.commit_sha)
            print(json.dumps({"lease_acquired": True, **lease}, sort_keys=True))
            return 0
        if args.release_session_lease:
            if not args.owner:
                raise ValueError("lease release requires --owner")
            release_lease(args.lease_file, owner=args.owner,
                          evidence_manifest=args.require_evidence_manifest)
            print(json.dumps({"lease_released": True, "owner": args.owner}, sort_keys=True))
            return 0
        profiles = yaml.safe_load(Path("configs/gke/profiles.yaml").read_text(encoding="utf-8"))
        rendered = render_profile(profiles, args.profile, args.ttl, dry_run=args.dry_run)
        if args.stage:
            rendered["stage"] = args.stage
        print(json.dumps(rendered, sort_keys=True))
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
