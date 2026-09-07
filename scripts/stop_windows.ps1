<#
.SYNOPSIS
    Stop and remove the FinAlly Docker container.

.DESCRIPTION
    Idempotent stop script. Stops and removes the "finally-app" container
    if it exists/is running. Does NOT remove the "finally-data" volume,
    so the database persists across stop/start cycles.
#>

$ContainerName = "finally-app"

$exists = docker ps -a --filter "name=^/$ContainerName`$" --format "{{.ID}}"

if (-not $exists) {
    Write-Host "Container '$ContainerName' does not exist. Nothing to stop."
    exit 0
}

Write-Host "Stopping container '$ContainerName'..."
docker stop $ContainerName | Out-Null

Write-Host "Removing container '$ContainerName'..."
docker rm $ContainerName | Out-Null

Write-Host "Stopped. Data volume 'finally-data' was preserved."
