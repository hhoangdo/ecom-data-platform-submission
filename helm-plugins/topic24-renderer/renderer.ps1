# topic24-renderer (Windows entrypoint): pipe Helm-rendered manifests on stdin
# through scripts/gke/topic24_postrender.py, emitting adapted manifests on stdout.
# Interface: no argv consumed (extra --post-renderer-args are ignored);
# configuration ONLY via EDAI2_SUBSTRATE_API_IMAGE / EDAI2_ATELET_WI_ANNOTATION.
$pluginDir = if ($env:HELM_PLUGIN_DIR) { $env:HELM_PLUGIN_DIR } else { Split-Path -Parent $PSCommandPath }
$repoDir = $pluginDir
for ($i = 0; $i -lt 5; $i++) {
  if (Test-Path (Join-Path $repoDir 'scripts/gke/topic24_postrender.py')) { break }
  $repoDir = (Resolve-Path (Join-Path $repoDir '..')).Path
}
$py = if ($env:REPO_PYTHON_BIN) { $env:REPO_PYTHON_BIN } `
  elseif (Test-Path (Join-Path $repoDir '.venv/Scripts/python.exe')) { Join-Path $repoDir '.venv/Scripts/python.exe' } `
  else { 'python' }
Set-Location $repoDir
& $py 'scripts/gke/topic24_postrender.py' @args
exit $LASTEXITCODE
