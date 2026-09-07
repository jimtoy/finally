#!/usr/bin/env bash
# Build (if needed) and start the FinAlly Docker container. Idempotent.
#
# Usage: ./scripts/start_mac.sh [--build] [--no-browser]

set -euo pipefail

IMAGE_NAME="finally"
CONTAINER_NAME="finally-app"
VOLUME_NAME="finally-data"
PORT=8000

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

BUILD=false
OPEN_BROWSER=true
for arg in "$@"; do
    case "$arg" in
        --build) BUILD=true ;;
        --no-browser) OPEN_BROWSER=false ;;
    esac
done

cd "$REPO_ROOT"

if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: no .env file found at $ENV_FILE." >&2
    echo "Copy .env.example to .env and fill in values (LLM_MOCK=true works without an API key)." >&2
fi

# Ensure the named volume exists (idempotent).
if ! docker volume inspect "$VOLUME_NAME" >/dev/null 2>&1; then
    echo "Creating Docker volume '$VOLUME_NAME'..."
    docker volume create "$VOLUME_NAME" >/dev/null
fi

IMAGE_EXISTS=$(docker images -q "$IMAGE_NAME")

if [ "$BUILD" = true ] || [ -z "$IMAGE_EXISTS" ]; then
    echo "Building Docker image '$IMAGE_NAME'..."
    docker build -t "$IMAGE_NAME" "$REPO_ROOT"
fi

CONTAINER_ID=$(docker ps -a --filter "name=^/${CONTAINER_NAME}\$" --format "{{.ID}}")

if [ "$BUILD" = true ] && [ -n "$CONTAINER_ID" ]; then
    echo "Removing existing container '$CONTAINER_NAME' to apply rebuilt image..."
    docker rm -f "$CONTAINER_NAME" >/dev/null
    CONTAINER_ID=""
fi

if [ -n "$CONTAINER_ID" ]; then
    STATE=$(docker inspect -f '{{.State.Status}}' "$CONTAINER_NAME")
    if [ "$STATE" = "running" ]; then
        echo "Container '$CONTAINER_NAME' is already running."
    else
        echo "Starting existing container '$CONTAINER_NAME'..."
        docker start "$CONTAINER_NAME" >/dev/null
    fi
else
    echo "Creating and starting container '$CONTAINER_NAME'..."
    ENV_FILE_ARGS=()
    if [ -f "$ENV_FILE" ]; then
        ENV_FILE_ARGS=(--env-file "$ENV_FILE")
    fi
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "${VOLUME_NAME}:/app/db" \
        -p "${PORT}:8000" \
        "${ENV_FILE_ARGS[@]}" \
        "$IMAGE_NAME" >/dev/null
fi

URL="http://localhost:${PORT}"
echo ""
echo "FinAlly is running at $URL"

if [ "$OPEN_BROWSER" = true ]; then
    if command -v open >/dev/null 2>&1; then
        open "$URL"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL"
    fi
fi
