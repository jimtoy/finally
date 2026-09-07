<#
.SYNOPSIS
    Build (if needed) and start the FinAlly Docker container.

.DESCRIPTION
    Idempotent start script for the FinAlly trading workstation.
    - Builds the "finally" image if it doesn't exist yet, or if -Build is passed.
    - Reuses/starts an existing stopped container named "finally-app" when possible.
    - Replaces the named container only when a rebuild is requested.
    - Mounts the named volume "finally-data" at /app/db and publishes port 8000.
    - Reads environment variables from .env in the repo root (via --env-file).

.PARAMETER Build
    Force a rebuild of the Docker image and replace the running container.

.PARAMETER NoBrowser
    Skip automatically opening the default browser once the app is up.
#>
param(
    [switch]$Build,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ImageName = "finally"
$ContainerName = "finally-app"
$VolumeName = "finally-data"
$Port = 8000
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $RepoRoot ".env"

Set-Location $RepoRoot

if (-not (Test-Path $EnvFile)) {
    Write-Warning "No .env file found at $EnvFile. Copy .env.example to .env and fill in values (LLM_MOCK=true works without an API key)."
    Write-Warning "Continuing without --env-file; OPENROUTER_API_KEY will be unset."
}

# Ensure the named volume exists (idempotent - no-op if already present).
docker volume inspect $VolumeName > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Docker volume '$VolumeName'..."
    docker volume create $VolumeName | Out-Null
}

$imageExists = (docker images -q $ImageName) -ne ""

if ($Build -or -not $imageExists) {
    Write-Host "Building Docker image '$ImageName'..."
    docker build -t $ImageName $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed."
    }
}

$containerInfo = docker ps -a --filter "name=^/$ContainerName`$" --format "{{.ID}}|{{.State}}"

if ($Build -and $containerInfo) {
    Write-Host "Removing existing container '$ContainerName' to apply rebuilt image..."
    docker rm -f $ContainerName | Out-Null
    $containerInfo = $null
}

if ($containerInfo) {
    $state = ($containerInfo -split "\|")[1]
    if ($state -eq "running") {
        Write-Host "Container '$ContainerName' is already running."
    } else {
        Write-Host "Starting existing container '$ContainerName'..."
        docker start $ContainerName | Out-Null
    }
} else {
    Write-Host "Creating and starting container '$ContainerName'..."
    $dockerArgs = @(
        "run", "-d",
        "--name", $ContainerName,
        "-v", "${VolumeName}:/app/db",
        "-p", "${Port}:8000"
    )
    if (Test-Path $EnvFile) {
        $dockerArgs += @("--env-file", $EnvFile)
    }
    $dockerArgs += $ImageName
    docker @dockerArgs | Out-Null
}

$Url = "http://localhost:$Port"
Write-Host ""
Write-Host "FinAlly is running at $Url"

if (-not $NoBrowser) {
    Start-Process $Url
}
