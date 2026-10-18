# Shared helpers for deploy.ps1 and rollback.ps1.
# Dot-source this file: . "$PSScriptRoot\common.ps1"

$script:StateFilePath = Join-Path $PSScriptRoot "state.json"
$script:LogDir = Join-Path $PSScriptRoot "logs"

function Get-DeployState {
    if (Test-Path $script:StateFilePath) {
        return Get-Content $script:StateFilePath -Raw | ConvertFrom-Json
    }
    return $null
}

function Save-DeployState {
    param(
        [Parameter(Mandatory = $true)][hashtable]$State
    )
    $State | ConvertTo-Json -Depth 5 | Set-Content -Path $script:StateFilePath -Encoding utf8
}

function Write-DeployLog {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
    $line = "[$timestamp] [$Level] $Message"
    Write-Host $line
    if (-not (Test-Path $script:LogDir)) {
        New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null
    }
    Add-Content -Path (Join-Path $script:LogDir "deploy.log") -Value $line
}

function Test-ContainerExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    $id = & docker ps -a --filter "name=^/$Name`$" --format "{{.ID}}" 2>$null
    return -not [string]::IsNullOrWhiteSpace($id)
}

function Test-ContainerRunning {
    param([Parameter(Mandatory = $true)][string]$Name)
    $status = & docker inspect -f "{{.State.Running}}" $Name 2>$null
    return $status -eq "true"
}

function Get-ContainerImageRef {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Test-ContainerExists -Name $Name)) {
        return $null
    }
    return (& docker inspect -f "{{.Config.Image}}" $Name 2>$null)
}

function Wait-ForReadiness {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $url = "http://localhost:$Port/ready"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                return $true
            }
        } catch {
            # not ready yet, keep polling
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Invoke-SmokeTests {
    param([Parameter(Mandatory = $true)][int]$Port)

    $base = "http://localhost:$Port"

    try {
        $health = Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 5
        if ($health.StatusCode -ne 200) { return $false }

        $ready = Invoke-WebRequest -Uri "$base/ready" -UseBasicParsing -TimeoutSec 5
        if ($ready.StatusCode -ne 200) { return $false }

        $version = Invoke-WebRequest -Uri "$base/version" -UseBasicParsing -TimeoutSec 5
        if ($version.StatusCode -ne 200) { return $false }

        $metrics = Invoke-WebRequest -Uri "$base/metrics" -UseBasicParsing -TimeoutSec 5
        if ($metrics.StatusCode -ne 200) { return $false }

        $createBody = @{ name = "smoke-test-$(Get-Random)" } | ConvertTo-Json
        $created = Invoke-WebRequest -Uri "$base/ships" -Method Post -Body $createBody `
            -ContentType "application/json" -UseBasicParsing -TimeoutSec 5
        if ($created.StatusCode -ne 201) { return $false }

        $createdShip = $created.Content | ConvertFrom-Json
        $deleted = Invoke-WebRequest -Uri "$base/ships/$($createdShip.id)" -Method Delete `
            -UseBasicParsing -TimeoutSec 5
        if ($deleted.StatusCode -ne 204) { return $false }

        return $true
    } catch {
        Write-DeployLog -Level "ERROR" -Message "smoke test request failed: $($_.Exception.Message)"
        return $false
    }
}

function Get-RunningAppVersion {
    param([Parameter(Mandatory = $true)][int]$Port)
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port/version" -UseBasicParsing -TimeoutSec 5
        return ($response.Content | ConvertFrom-Json)
    } catch {
        return $null
    }
}
