"""Generate a REAL registry.db + feast-registry Secret (leased agent runs at install).

Steps (run from this directory):
  pip install "feast[redis]==0.45.*"  # redis extra REQUIRED: repo online_store
                                      # is redis, and apply loads its config
  feast apply                    # writes data/registry.db (protobuf bytes)
  python generate.py --emit-secret  # writes feast-registry-secret.yaml

Why no binary is committed: registry.db is a build artifact (protobuf bytes with
fresh version_id/last_updated per apply); reviewing binary is meaningless and
env-specific. Regenerate at install time; keep only the minimal repo definition.

Secret layout (PATH A): the single pre-created Secret `feast-registry` carries
BOTH keys from the same registry.db bytes:
  - stringData.REGISTRY_BASE64 = base64(registry.db): transformation-service
    env (secretKeyRef feast-registry/REGISTRY_BASE64).
  - data.registry.db = base64(registry.db): feature-server secrets-mount file
    /etc/secrets/feast-registry/registry.db (secretKeyRef-free volume mount;
    K8s decodes base64 on mount so raw protobuf bytes land on disk).
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description="feast apply + emit feast-registry Secret")
    parser.add_argument("--emit-secret", action="store_true", help="write feast-registry-secret.yaml")
    parser.add_argument("--registry", default="data/registry.db", help="registry path from feature_store.yaml")
    args = parser.parse_args()

    # Lazy import: only the leased agent needs feast installed.
    # `feast apply` equivalent: load repo and write registry proto.
    from feast import Entity, FeatureStore

    import entities

    store = FeatureStore(repo_path=str(HERE.resolve()))
    # feast apply: registers the repo's entities (one entity, zero feature
    # views = honest empty state). NEVER store.apply([]): that writes a
    # zero-entity registry and drops `customer`.
    repo_entities = [obj for obj in vars(entities).values() if isinstance(obj, Entity)]
    assert repo_entities, "entities.py must define at least one Entity"
    store.apply(repo_entities)
    # Ensure registry file exists (FileRegistryStore writes protobuf bytes).
    registry_path = HERE / args.registry
    assert registry_path.is_file(), f"registry not found at {registry_path}; did feast apply fail?"

    if args.emit_secret:
        raw = registry_path.read_bytes()
        # Both Secret keys derive from the SAME registry.db bytes (single
        # base64 string, two representations): stringData.REGISTRY_BASE64 for
        # the transformation env, data.registry.db for the feature-server mount.
        b64 = base64.b64encode(raw).decode("ascii")
        secret = (
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: feast-registry\n"
            "  namespace: edai2\ndata:\n  registry.db: "
            + b64
            + "\nstringData:\n  REGISTRY_BASE64: "
            + b64
            + "\n"
        )
        (HERE / "feast-registry-secret.yaml").write_text(secret, encoding="utf-8")
        print(f"wrote feast-registry-secret.yaml ({len(raw)} registry bytes -> {len(b64)} chars per key)")


if __name__ == "__main__":
    main()
