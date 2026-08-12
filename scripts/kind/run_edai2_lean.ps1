[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $ClusterName,
    [Parameter(Mandatory)] [string] $Context,
    [Parameter(Mandatory)] [string] $Kubeconfig,
    [Parameter(Mandatory)] [string] $NodeImage,
    [Parameter(Mandatory)] [string] $Namespace,
    [Parameter(Mandatory)] [int] $LocalPort,
    [Parameter(Mandatory)] [string] $Preflight,
    [Parameter(Mandatory)] [string] $Inventory
)

$ErrorActionPreference = 'Stop'
$Release = 'edai2-retrieval-kind'
$ExpectedCluster = 'edai2-lean'
$ExpectedContext = 'kind-edai2-lean'
$ExpectedKubeconfig = 'tmp/edai2-kind/kubeconfig'
$ExpectedNodeImage = 'kindest/node:v1.35.5@sha256:ce977ae6d65918d0b58a5f8b5e940429c2ce42fa3a5619ec2bbc60b949c0ac95'
$RuntimeRoot = 'tmp/edai2-kind'
$PidPath = "$RuntimeRoot/port-forward.pid"
$MaxImageBytes = 536870912
$PortForward = $null
$ClusterCreateAttempted = $false
$ReleaseInstalled = $false
$OwnsKubeconfig = $false
$CleanupErrors = [System.Collections.Generic.List[string]]::new()

function Invoke-Rtk {
    param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Arguments)
    & rtk @Arguments
    if ($LASTEXITCODE -ne 0) { throw "command failed: rtk $($Arguments -join ' ')" }
}

function Assert-KindImageLoadOutput {
    param([Parameter(Mandatory)] [object[]] $Output)
    foreach ($Line in $Output) {
        if ("$Line" -match '(?i)^\s*error:|context deadline exceeded|\bfailed\b') {
            throw 'kind image load emitted Error or failure output'
        }
    }
}

function Invoke-KindImageLoad {
    param([Parameter(Mandatory)] [string] $Image, [Parameter(Mandatory)] [string] $OwnedCluster)
    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $Output = @(& rtk kind load docker-image $Image --name $OwnedCluster 2>&1)
        $ExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $PreviousErrorActionPreference }
    $Output | Write-Output
    if ($ExitCode -ne 0) { throw "command failed: rtk kind load docker-image $Image --name $OwnedCluster" }
    Assert-KindImageLoadOutput -Output $Output
}

function Convert-StorageToBytes {
    param([Parameter(Mandatory)] [string] $Quantity)
    if ($Quantity -match '^(\d+)(Ki|Mi|Gi)$') {
        $Multiplier = switch ($Matches[2]) { 'Ki' { 1KB }; 'Mi' { 1MB }; 'Gi' { 1GB } }
        return [int64]$Matches[1] * $Multiplier
    }
    throw "unparseable requests.storage quantity: $Quantity"
}

function Invoke-Probe {
    param([Parameter(Mandatory)] [string] $Path, [Parameter(Mandatory)] [string] $BodyPath, [Parameter(Mandatory)] [string] $StatusPath, [Parameter(Mandatory)] [string] $ExpectedStatus)
    $TemporaryBody = "$BodyPath.tmp"
    $Status = & rtk curl.exe --fail-with-body --silent --show-error --output $TemporaryBody --write-out '%{http_code}' "http://127.0.0.1:$LocalPort$Path"
    if ($LASTEXITCODE -ne 0 -or $Status.Trim() -ne '200') { throw "probe $Path did not return HTTP 200" }
    $Body = Get-Content -Raw -LiteralPath $TemporaryBody | ConvertFrom-Json
    if ($Body.status -ne $ExpectedStatus -or $Body.service -ne 'edai2-retrieval-agent') { throw "probe $Path returned an invalid local-preflight schema" }
    Move-Item -LiteralPath $TemporaryBody -Destination $BodyPath -Force
    Set-Content -LiteralPath "$StatusPath.tmp" -Value '200' -NoNewline
    Move-Item -LiteralPath "$StatusPath.tmp" -Destination $StatusPath -Force
}

try {
    if ($ClusterName -ne $ExpectedCluster -or $Context -ne $ExpectedContext -or $Kubeconfig -ne $ExpectedKubeconfig -or $NodeImage -ne $ExpectedNodeImage -or $Namespace -ne $ExpectedCluster -or $LocalPort -ne 18081) { throw 'only the Topic 21 owned Kind values are allowed' }
    $PreflightReport = Get-Content -Raw -LiteralPath $Preflight | ConvertFrom-Json
    if ($PreflightReport.status -ne 'passed' -or $PreflightReport.cluster -ne $ExpectedCluster -or $PreflightReport.context -ne $ExpectedContext -or $PreflightReport.kubeconfig -ne $ExpectedKubeconfig -or $PreflightReport.node_image -ne $ExpectedNodeImage) { throw 'preflight report is not the exact owned local preflight' }
    if (Test-Path -LiteralPath $Kubeconfig) { throw 'dedicated kubeconfig already exists' }
    $ExistingClusters = @(& rtk proxy kind get clusters)
    if ($LASTEXITCODE -ne 0) { throw 'Kind cluster inventory failed' }
    if ($ExistingClusters -contains $ClusterName) { throw 'owned Kind cluster already exists' }
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

    Invoke-Rtk docker build --file containers/edai2/Dockerfile.kind-retrieval --target retrieval_agent_kind --tag edai2/retrieval-agent:kind-local .
    $HostImage = (& rtk proxy docker image inspect edai2/retrieval-agent:kind-local) | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or @($HostImage).Count -ne 1) { throw 'local image inspection failed' }
    $HostImageId = "$($HostImage[0].Id)"
    $HostImageSize = [int64]$HostImage[0].Size
    if (-not $HostImageId.StartsWith('sha256:') -or $HostImageSize -gt $MaxImageBytes) { throw "Kind image exceeds $MaxImageBytes bytes or has no immutable ID" }

    $OwnsKubeconfig = $true
    $ClusterCreateAttempted = $true
    Invoke-Rtk kind create cluster --name $ClusterName --image $NodeImage --config infra/kind/edai2-lean/kind-config.yaml --kubeconfig $Kubeconfig
    $CurrentContext = & rtk kubectl --kubeconfig $Kubeconfig --context $Context config current-context
    if ($LASTEXITCODE -ne 0 -or $CurrentContext.Trim() -ne $Context) { throw 'Kind context verification failed' }
    Invoke-KindImageLoad -Image edai2/retrieval-agent:kind-local -OwnedCluster $ClusterName
    $NodeImageJson = & rtk proxy docker exec "$ClusterName-control-plane" crictl images --output=json
    if ($LASTEXITCODE -ne 0) { throw 'loaded node image inspection failed' }
    $NodeImageList = $NodeImageJson | ConvertFrom-Json
    $LoadedImages = @($NodeImageList.images | Where-Object {
        $Tags = @($_.repoTags)
        ($Tags -contains 'docker.io/edai2/retrieval-agent:kind-local') -or ($Tags -contains 'edai2/retrieval-agent:kind-local')
    })
    if ($LoadedImages.Count -ne 1) { throw "loaded node image inventory contains $($LoadedImages.Count) matching tags" }
    $NodeImageId = "$($LoadedImages[0].id)"
    if (-not $NodeImageId.StartsWith('sha256:')) { throw "loaded node image has no immutable ID: node=$NodeImageId" }
    Write-Output "KIND_IMAGE host_id=$HostImageId node_id=$NodeImageId size_bytes=$HostImageSize"
    $ApiReady = & rtk proxy kubectl --kubeconfig $Kubeconfig --context $Context get --raw=/readyz
    if ($LASTEXITCODE -ne 0 -or "$ApiReady" -notmatch '^ok') { throw 'owned Kind API is not ready after image load' }

    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context apply -f infra/kind/edai2-lean/namespace.yaml
    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context apply -f infra/kind/edai2-lean/resource-quota.yaml -f infra/kind/edai2-lean/limit-range.yaml -f infra/kind/edai2-lean/network-policy.yaml
    Invoke-Rtk helm --kubeconfig $Kubeconfig --kube-context $Context upgrade --install $Release infra/helm/edai2/service-agent --namespace $Namespace -f infra/kind/edai2-lean/retrieval-values.yaml --set-string image.repository=edai2/retrieval-agent --set-string image.tag=kind-local --set image.pullPolicy=IfNotPresent --wait --timeout 5m
    $ReleaseInstalled = $true
    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context -n $Namespace rollout status deployment/$Release --timeout=180s

    $PortForward = Start-Process -FilePath rtk -ArgumentList @('kubectl', '--kubeconfig', $Kubeconfig, '--context', $Context, '-n', $Namespace, 'port-forward', "service/$Release", "$LocalPort`:8080", '--address', '127.0.0.1') -WindowStyle Hidden -PassThru -RedirectStandardOutput "$RuntimeRoot/port-forward.stdout.log" -RedirectStandardError "$RuntimeRoot/port-forward.stderr.log"
    Set-Content -LiteralPath $PidPath -Value $PortForward.Id -NoNewline
    $ProbeSucceeded = $false
    for ($Attempt = 1; $Attempt -le 15 -and -not $ProbeSucceeded; $Attempt++) {
        try {
            Invoke-Probe -Path '/healthz' -BodyPath "$RuntimeRoot/health.json" -StatusPath "$RuntimeRoot/health.status" -ExpectedStatus 'ok'
            Invoke-Probe -Path '/readyz' -BodyPath "$RuntimeRoot/readiness.json" -StatusPath "$RuntimeRoot/readiness.status" -ExpectedStatus 'ready'
            $ProbeSucceeded = $true
        } catch {
            if ($Attempt -eq 15) { throw }
            Start-Sleep -Seconds 2
        }
    }

    $InventoryText = & rtk proxy kubectl --kubeconfig $Kubeconfig --context $Context -n $Namespace get pods,pvc,services -o json
    if ($LASTEXITCODE -ne 0) { throw 'inventory command failed' }
    $InventoryObject = $InventoryText | ConvertFrom-Json
    $Pods = @($InventoryObject.items | Where-Object { $_.kind -eq 'Pod' })
    $Pvcs = @($InventoryObject.items | Where-Object { $_.kind -eq 'PersistentVolumeClaim' })
    $Services = @($InventoryObject.items | Where-Object { $_.kind -eq 'Service' })
    $RequestedStorage = [int64]0
    foreach ($Pvc in $Pvcs) { $RequestedStorage += Convert-StorageToBytes "$($Pvc.spec.resources.requests.storage)" }
    if ($Pods.Count -gt 30 -or $Pvcs.Count -gt 8 -or $RequestedStorage -gt 20GB -or @($Services | Where-Object { $_.spec.type -eq 'LoadBalancer' }).Count -ne 0) { throw 'bounded inventory validation failed' }
    Set-Content -LiteralPath "$Inventory.tmp" -Value $InventoryText -NoNewline
    Move-Item -LiteralPath "$Inventory.tmp" -Destination $Inventory -Force
}
finally {
    if ($null -ne $PortForward) {
        try {
            Stop-Process -Id $PortForward.Id -ErrorAction SilentlyContinue
            Wait-Process -Id $PortForward.Id -ErrorAction SilentlyContinue
            if (Get-Process -Id $PortForward.Id -ErrorAction SilentlyContinue) { throw 'owned port-forward remains running' }
        } catch { $CleanupErrors.Add("port-forward cleanup: $($_.Exception.Message)") }
    }
    if (Test-Path -LiteralPath $PidPath) {
        try { Remove-Item -LiteralPath $PidPath -Force } catch { $CleanupErrors.Add("PID cleanup: $($_.Exception.Message)") }
    }
    if ($ReleaseInstalled) {
        try { Invoke-Rtk helm --kubeconfig $Kubeconfig --kube-context $Context uninstall $Release --namespace $Namespace --wait --timeout 2m } catch { $CleanupErrors.Add("Helm cleanup: $($_.Exception.Message)") }
    }
    if ($ClusterCreateAttempted) {
        try {
            $CurrentClusters = @(& rtk proxy kind get clusters)
            if ($LASTEXITCODE -ne 0) { throw 'Kind cluster inventory failed during cleanup' }
            if ($CurrentClusters -contains $ClusterName) { Invoke-Rtk kind delete cluster --name $ClusterName }
        } catch { $CleanupErrors.Add("Kind cleanup: $($_.Exception.Message)") }
    }
    if ($OwnsKubeconfig -and (Test-Path -LiteralPath $Kubeconfig)) {
        try { Remove-Item -LiteralPath $Kubeconfig -Force } catch { $CleanupErrors.Add("kubeconfig cleanup: $($_.Exception.Message)") }
    }
    if ($CleanupErrors.Count -gt 0) { throw ($CleanupErrors -join '; ') }
}
