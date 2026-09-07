#!/usr/bin/env bash
# Stop and remove the FinAlly Docker container. Idempotent.
# Does NOT remove the finally-data volume, so the database persists.

set -euo pipefail

CONTAINER_NAME="finally-app"

CONTAINER_ID=$(docker ps -a --filter "name=^/${CONTAINER_NAME}\$" --format "{{.ID}}")

if [ -z "$CONTAINER_ID" ]; then
    echo "Container '$CONTAINER_NAME' does not exist. Nothing to stop."
    exit 0
fi

echo "Stopping container '$CONTAINER_NAME'..."
docker stop "$CONTAINER_NAME" >/dev/null

echo "Removing container '$CONTAINER_NAME'..."
docker rm "$CONTAINER_NAME" >/dev/null

echo "Stopped. Data volume 'finally-data' was preserved."
