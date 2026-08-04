#!/bin/sh
set -eu

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export NO_PROXY="${NO_PROXY:-},minio,localhost,127.0.0.1"
export no_proxy="${no_proxy:-},minio,localhost,127.0.0.1"

mc alias set ALIAS http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

mc mb --ignore-existing ALIAS/bronze
mc mb --ignore-existing ALIAS/silver
mc mb --ignore-existing ALIAS/gold
mc mb --ignore-existing ALIAS/checkpoints
mc mb --ignore-existing ALIAS/evidence

mc pipe ALIAS/checkpoints/spark-events/.keep </dev/null

mc ls ALIAS
