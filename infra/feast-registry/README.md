# Feast minimal registry generator (local, no lease)

Minimal honest empty state: **one entity, zero feature views**. `feast apply`
on this directory produces a REAL `data/registry.db` (protobuf bytes at
`feast==0.45.0`, NOT SQLite). The binary is NEVER committed (build artifact with
fresh `version_id`/`last_updated` per apply; see `generate.py`).

## Files

- `feature_store.yaml`: `project: default`, `provider: local`,
  `registry: data/registry.db` (matches chart `global.project: default`).
- `entities.py`: single `customer` entity, NO `FeatureView`.
- `generate.py`: applies the repo entities + emits `feast-registry-secret.yaml`
  with BOTH keys from the same bytes: `data.registry.db = base64(registry.db)`
  (feature-server secrets-mount file) and `stringData.REGISTRY_BASE64 =
  base64(registry.db)` (transformation-service env secretKeyRef).

## Leased-agent use (do NOT run locally without lease)

```powershell
pip install "feast[redis]==0.45.*"  # redis extra REQUIRED: repo online_store
                                    # is redis; apply loads its config
cd infra/feast-registry
feast apply                         # writes data/registry.db (protobuf bytes)
python generate.py --emit-secret     # writes feast-registry-secret.yaml
kubectl apply -f feast-registry-secret.yaml
# Alternative without the file (same result):
# kubectl -n edai2 create secret generic feast-registry `
#   --from-file=registry.db=data/registry.db `
#   --from-literal=REGISTRY_BASE64=$(python -c "import base64; print(base64.b64encode(open('data/registry.db','rb').read()).decode())") `
#   --dry-run=client -o yaml | kubectl apply -f -
helm install feast feast-charts/feast --version 0.45.0 -n edai2 `
  -f infra/helm/edai2/values/feast.yaml
```

## Expected states after fresh install with `values/feast.yaml`

- `transformation-service`: Running (REGISTRY_BASE64 present via Secret;
  writes registry to temp dir, needs NO volume).
- `feature-server`: Running (registry mounted from pre-created Secret:
  `global.registry.path=file:///etc/secrets/feast-registry/registry.db` ==
  secrets-mount `/etc/secrets/feast-registry/registry.db`). Distinguish:
  - SUCCESS: `Running`, no `FileNotFound` in logs.
  - Secret missing at install: pod `Pending`/`ContainerCreating`
    (`MountVolume.SetUp failed`: Secret `feast-registry` not found) — create
    the Secret, do NOT edit values.
  - Stale/foreign bytes: CrashLoop with protobuf `DecodeError` — regenerate
    via this directory, do NOT hand-write bytes.
  - Valkey auth: expect NO `WRONGPASS`/`NOAUTH` once `valkey` Secret exists
    (`${REDIS_PASSWORD}` + `REDIS_PASSWORD` secretKeyRef to `valkey/password`).
- `valkey`: `requirepass` enforced (`auth.enabled: true` + existingSecret).

## Re-pin decision

NO re-pin. `feast 0.45.0` UNCHANGED in `releases.yaml`. Newest `0.66.0` still
renders ONLY `FEATURE_STORE_YAML_BASE64`, NO `REGISTRY_BASE64`, NO
`extraVolumes` (helm template proof).
