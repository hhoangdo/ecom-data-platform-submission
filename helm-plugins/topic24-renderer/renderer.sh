#!/usr/bin/env sh
# topic24-renderer (POSIX entrypoint): pipe Helm-rendered manifests on stdin
# through scripts/gke/topic24_postrender.py, emitting adapted manifests on stdout.
# Interface: no argv consumed (extra --post-renderer-args are ignored);
# configuration ONLY via EDAI2_SUBSTRATE_API_IMAGE / EDAI2_ATELET_WI_ANNOTATION.
set -eu

_plugin_dir="${HELM_PLUGIN_DIR:-}"
if [ -z "$_plugin_dir" ]; then
  _plugin_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
fi
# Resolve symlinks (dev-mode install is a symlink into $HELM_PLUGINS).
if command -v readlink >/dev/null 2>&1; then
  _resolved="$(readlink -f "$_plugin_dir" 2>/dev/null || true)"
  [ -n "$_resolved" ] && _plugin_dir="$_resolved"
fi
# Repo root = nearest ancestor containing scripts/gke/topic24_postrender.py.
_repo_dir="$_plugin_dir"
for _i in 1 2 3 4 5; do
  if [ -f "$_repo_dir/scripts/gke/topic24_postrender.py" ]; then
    break
  fi
  _repo_dir="$(CDPATH= cd -- "$_repo_dir/.." && pwd)"
done

_py="$REPO_PYTHON_BIN:-"
if [ -z "$_py" ]; then
  if [ -x "$_repo_dir/.venv/bin/python" ]; then
    _py="$_repo_dir/.venv/bin/python"
  elif [ -x "$_repo_dir/.venv/Scripts/python.exe" ]; then
    _py="$_repo_dir/.venv/Scripts/python.exe"
  elif command -v python3 >/dev/null 2>&1; then
    _py="python3"
  else
    _py="python"
  fi
fi

cd "$_repo_dir"
exec "$_py" scripts/gke/topic24_postrender.py "$@"
