<#
.SYNOPSIS
    Deploy a Shipyard application image, verify it, and roll back automatically on failure.

.DESCRIPTION
    Replaces the running "shipyard-app" container with a new image while leaving the
    database, Prometheus, and Grafana services (managed by docker-compose.yml) untouched.
    The previously running container is kept, stopped, as a fallback until the new
    deployment is verified healthy.

.PARAMETER Image
    Full image reference to deploy, e.g. ghcr.io/owner/shipyard:1.2.3 or
    ghcr.io/owner/shipyard@sha256:...  Digest references are preferred for reproducibility.

.PARAMETER ContainerName
    Name of the application container to manage. Default: shipyard-app

.PARAMETER Network
    Docker network to attach the container to, so it can reach the "db" service.
    Default: shipyard_shipyard-net (the default docker-compose project network).

.PARAMETER Port
    Host port to publish. Default: 8000

.PARAMETER EnvFile
    Path to an env file with POSTGRES_* credentials. Default: ../.env

.PARAMETER TimeoutSeconds
    Maximum time to wait for readiness before declaring the deploy failed. Default: 90

.PARAMETER SkipPull
    Skip "docker pull" — use this for images built and tagged locally.

.EXAMPLE
    ./deploy.ps1 -Image ghcr.io/example/shipyard:1.4.0
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$ContainerName = "shipyard-app",
    [string]$Network = "shipyard_shipyard-net",
    [int]$Port = 8000,
    [string]$EnvFile = (Join-Path $PSScriptRoot "..\.env"),
    [int]$TimeoutSeconds = 90,
    [switch]$SkipPull
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$previousContainerName = "$ContainerName-previous"

function Restore-PreviousContainer {
    Write-DeployLog -Level "WARN" -Message "attempting automatic rollback to previous container"

    if (-not (Test-ContainerExists -Name $previousContainerName)) {
        Write-DeployLog -Level "ERROR" -Message "no previous container available to roll back to"
        return $false
    }

    if (Test-ContainerExists -Name $ContainerName) {
        docker logs $ContainerName > (Join-Path $script:LogDir "failed-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss').log") 2>&1
        docker rm -f $ContainerName | Out-Null
    }
    docker start $previousContainerName | Out-Null
    docker rename $previousContainerName $ContainerName

    if (-not (Wait-ForReadiness -Port $Port -TimeoutSeconds $TimeoutSeconds)) {
        Write-DeployLog -Level "ERROR" -Message "rollback container did not become ready"
        return $false
    }

    Write-DeployLog -Message "automatic rollback complete, previous release restored"
    return $true
}

Write-DeployLog -Message "starting deployment of image '$Image'"

if ([string]::IsNullOrWhiteSpace($Image) -or $Image -match '\s') {
    Write-DeployLog -Level "ERROR" -Message "invalid image reference: '$Image'"
    exit 1
}

$state = Get-DeployState
$priorCurrentImage = if ($state) { $state.currentImage } else { $null }

if (Test-ContainerExists -Name $previousContainerName) {
    Write-DeployLog -Message "removing stale fallback container '$previousContainerName' from an earlier deploy"
    docker rm -f $previousContainerName | Out-Null
}

$hadRunningContainer = Test-ContainerExists -Name $ContainerName
if ($hadRunningContainer) {
    Write-DeployLog -Message "stopping current container '$ContainerName' and preserving it as rollback fallback"
    docker stop $ContainerName | Out-Null
    docker rename $ContainerName $previousContainerName
} else {
    Write-DeployLog -Message "no existing '$ContainerName' container found; this is a first deployment"
}

if (-not $SkipPull) {
    Write-DeployLog -Message "pulling image '$Image'"
    docker pull $Image
    if ($LASTEXITCODE -ne 0) {
        Write-DeployLog -Level "ERROR" -Message "docker pull failed"
        if ($hadRunningContainer) { Restore-PreviousContainer | Out-Null }
        exit 1
    }
} else {
    Write-DeployLog -Message "skipping pull for local image '$Image'"
}

$envFileArgs = @()
if (Test-Path $EnvFile) {
    $envFileArgs = @("--env-file", $EnvFile)
} else {
    Write-DeployLog -Level "WARN" -Message "env file '$EnvFile' not found, relying on image defaults"
}

Write-DeployLog -Message "starting new container '$ContainerName' on network '$Network'"
docker run -d `
    --name $ContainerName `
    --network $Network `
    -p "${Port}:8000" `
    @envFileArgs `
    --restart unless-stopped `
    $Image | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-DeployLog -Level "ERROR" -Message "failed to start new container"
    if ($hadRunningContainer) { Restore-PreviousContainer | Out-Null }
    exit 1
}

Write-DeployLog -Message "waiting up to $TimeoutSeconds seconds for readiness"
if (-not (Wait-ForReadiness -Port $Port -TimeoutSeconds $TimeoutSeconds)) {
    Write-DeployLog -Level "ERROR" -Message "new container failed to become ready within timeout"
    $rolledBack = $false
    if ($hadRunningContainer) { $rolledBack = Restore-PreviousContainer }
    if ($rolledBack) { exit 1 } else { exit 2 }
}

Write-DeployLog -Message "running smoke tests"
if (-not (Invoke-SmokeTests -Port $Port)) {
    Write-DeployLog -Level "ERROR" -Message "smoke tests failed against new deployment"
    $rolledBack = $false
    if ($hadRunningContainer) { $rolledBack = Restore-PreviousContainer }
    if ($rolledBack) { exit 1 } else { exit 2 }
}

$runningVersion = Get-RunningAppVersion -Port $Port
Write-DeployLog -Message "new container reports version '$($runningVersion.version)' sha '$($runningVersion.git_sha)'"

Save-DeployState -State @{
    currentImage  = $Image
    previousImage = $priorCurrentImage
    version       = $runningVersion.version
    gitSha        = $runningVersion.git_sha
    deployedAt    = (Get-Date).ToString("o")
    status        = "success"
}

Write-DeployLog -Message "deployment successful. Fallback container '$previousContainerName' retained for rollback."
exit 0
