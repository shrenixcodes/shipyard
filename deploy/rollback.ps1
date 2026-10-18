<#
.SYNOPSIS
    Roll back the running Shipyard application container to the previous known-good release.

.DESCRIPTION
    Restores the container preserved by deploy.ps1 under "<ContainerName>-previous".
    Does not touch the database, its data, or run any migration — only the application
    container is swapped. See docs/runbooks/rollback.md for migration-compatibility notes.

.PARAMETER ContainerName
    Name of the application container to manage. Default: shipyard-app

.PARAMETER Port
    Host port the application is published on. Default: 8000

.PARAMETER TimeoutSeconds
    Maximum time to wait for the restored container to become ready. Default: 90

.EXAMPLE
    ./rollback.ps1
#>
[CmdletBinding()]
param(
    [string]$ContainerName = "shipyard-app",
    [int]$Port = 8000,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1"

$previousContainerName = "$ContainerName-previous"

Write-DeployLog -Message "rollback requested for '$ContainerName'"

if (-not (Test-ContainerExists -Name $previousContainerName)) {
    Write-DeployLog -Level "ERROR" -Message "no fallback container '$previousContainerName' found; cannot roll back"
    exit 1
}

$state = Get-DeployState
$currentImage = Get-ContainerImageRef -Name $ContainerName
$previousImage = Get-ContainerImageRef -Name $previousContainerName

if (Test-ContainerExists -Name $ContainerName) {
    $logPath = Join-Path $script:LogDir "pre-rollback-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
    Write-DeployLog -Message "preserving current container logs to '$logPath'"
    docker logs $ContainerName > $logPath 2>&1
    docker rm -f $ContainerName | Out-Null
} else {
    Write-DeployLog -Level "WARN" -Message "no running '$ContainerName' container found; proceeding to restore fallback anyway"
}

Write-DeployLog -Message "starting fallback container (image '$previousImage')"
docker start $previousContainerName | Out-Null
docker rename $previousContainerName $ContainerName

Write-DeployLog -Message "waiting up to $TimeoutSeconds seconds for restored container to become ready"
if (-not (Wait-ForReadiness -Port $Port -TimeoutSeconds $TimeoutSeconds)) {
    Write-DeployLog -Level "ERROR" -Message "restored container did not become ready; manual intervention required"
    exit 2
}

Write-DeployLog -Message "running smoke tests against restored container"
if (-not (Invoke-SmokeTests -Port $Port)) {
    Write-DeployLog -Level "ERROR" -Message "smoke tests failed after rollback; manual intervention required"
    exit 2
}

$runningVersion = Get-RunningAppVersion -Port $Port
Write-DeployLog -Message "rollback verified: running version '$($runningVersion.version)' sha '$($runningVersion.git_sha)'"

Save-DeployState -State @{
    currentImage  = $previousImage
    previousImage = $currentImage
    version       = $runningVersion.version
    gitSha        = $runningVersion.git_sha
    deployedAt    = (Get-Date).ToString("o")
    status        = "rolled_back"
}

Write-DeployLog -Message "rollback complete and service availability verified"
exit 0
