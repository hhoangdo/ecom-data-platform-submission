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
$PortForward = $null
$ClusterCreated = $false
$ReleaseInstalled = $false
$OwnsKubeconfig = $false

function Invoke-Rtk {
    param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Arguments)
    & rtk @Arguments
    if ($LASTEXITCODE -ne 0) { throw "command failed: rtk $($Arguments -join ' ')" }
}

function Assert-KindImageLoadOutput {
    param([Parameter(Mandatory)] [object[]] $Output)
    foreach ($Line in $Output) {
        if ("$Line" -match '^\s*Error:') { throw 'kind image load emitted Error output' }
    }
}

function Invoke-KindImageLoad {
    param([Parameter(Mandatory)] [string] $Image, [Parameter(Mandatory)] [string] $OwnedCluster)
    $Output = @(& rtk kind load docker-image $Image --name $OwnedCluster 2>&1)
    $ExitCode = $LASTEXITCODE
    $Output | Write-Output
    if ($ExitCode -ne 0) { throw "command failed: rtk kind load docker-image $Image --name $OwnedCluster" }
    Assert-KindImageLoadOutput -Output $Output
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
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    $OwnsKubeconfig = $true

    Invoke-Rtk kind create cluster --name $ClusterName --image $NodeImage --config infra/kind/edai2-lean/kind-config.yaml --kubeconfig $Kubeconfig
    $ClusterCreated = $true
    $CurrentContext = & rtk kubectl --kubeconfig $Kubeconfig --context $Context config current-context
    if ($LASTEXITCODE -ne 0 -or $CurrentContext.Trim() -ne $Context) { throw 'Kind context verification failed' }
    Invoke-Rtk docker build --file containers/edai2/Dockerfile --target retrieval_agent --tag edai2/retrieval-agent:kind-local .
    Invoke-KindImageLoad -Image edai2/retrieval-agent:kind-local -OwnedCluster $ClusterName
    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context apply -f infra/kind/edai2-lean/namespace.yaml
    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context apply -f infra/kind/edai2-lean/resource-quota.yaml -f infra/kind/edai2-lean/limit-range.yaml -f infra/kind/edai2-lean/network-policy.yaml
    Invoke-Rtk helm --kubeconfig $Kubeconfig --kube-context $Context upgrade --install $Release infra/helm/edai2/service-agent --namespace $Namespace -f infra/kind/edai2-lean/retrieval-values.yaml --set-string image.repository=edai2/retrieval-agent --set-string image.tag=kind-local --set image.pullPolicy=IfNotPresent --wait --timeout 5m
    $ReleaseInstalled = $true
    Invoke-Rtk kubectl --kubeconfig $Kubeconfig --context $Context -n $Namespace rollout status deployment/$Release --timeout=180s

    $PortForward = Start-Process -FilePath rtk -ArgumentList @('kubectl', '--kubeconfig', $Kubeconfig, '--context', $Context, '-n', $Namespace, 'port-forward', "service/$Release", "$LocalPort`:8080", '--address', '127.0.0.1') -WindowStyle Hidden -PassThru -RedirectStandardOutput "$RuntimeRoot/port-forward.stdout.log" -RedirectStandardError "$RuntimeRoot/port-forward.stderr.log"
    Set-Content -LiteralPath "$RuntimeRoot/port-forward.pid" -Value $PortForward.Id -NoNewline
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

    $InventoryText = & rtk kubectl --kubeconfig $Kubeconfig --context $Context -n $Namespace get pods,pvc,services -o json
    if ($LASTEXITCODE -ne 0) { throw 'inventory command failed' }
    $InventoryObject = $InventoryText | ConvertFrom-Json
    $Pods = @($InventoryObject.items | Where-Object { $_.kind -eq 'Pod' })
    $Pvcs = @($InventoryObject.items | Where-Object { $_.kind -eq 'PersistentVolumeClaim' })
    $Services = @($InventoryObject.items | Where-Object { $_.kind -eq 'Service' })
    if ($Pods.Count -gt 30 -or $Pvcs.Count -gt 8 -or @($Services | Where-Object { $_.spec.type -eq 'LoadBalancer' }).Count -ne 0) { throw 'bounded inventory validation failed' }
    Set-Content -LiteralPath "$Inventory.tmp" -Value $InventoryText -NoNewline
    Move-Item -LiteralPath "$Inventory.tmp" -Destination $Inventory -Force
}
finally {
    if ($null -ne $PortForward) {
        Stop-Process -Id $PortForward.Id -ErrorAction SilentlyContinue
        Wait-Process -Id $PortForward.Id -ErrorAction SilentlyContinue
        if (Get-Process -Id $PortForward.Id -ErrorAction SilentlyContinue) { throw 'owned port-forward remains running' }
    }
    if ($ReleaseInstalled) {
        try { Invoke-Rtk helm --kubeconfig $Kubeconfig --kube-context $Context uninstall $Release --namespace $Namespace --wait --timeout 2m } catch { Write-Warning $_ }
    }
    if ($ClusterCreated) {
        try { Invoke-Rtk kind delete cluster --name $ClusterName } catch { Write-Warning $_ }
    }
    if ($OwnsKubeconfig -and (Test-Path -LiteralPath $Kubeconfig)) { Remove-Item -LiteralPath $Kubeconfig -Force }
}
