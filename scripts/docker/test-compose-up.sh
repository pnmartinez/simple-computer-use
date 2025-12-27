#!/bin/bash
# Smoke test to validate docker compose up and health endpoint.

set -euo pipefail

SERVICE_NAME="voice-control-server"
HEALTH_URL="http://localhost:5000/health"

if ! command -v docker &>/dev/null; then
  echo "Error: docker is not installed." >&2
  exit 1
fi

if ! docker info &>/dev/null; then
  echo "Error: docker daemon is not running." >&2
  exit 1
fi

compose_cmd=(docker compose)
if ! docker compose version &>/dev/null; then
  if command -v docker-compose &>/dev/null; then
    compose_cmd=(docker-compose)
  else
    echo "Error: docker compose is not available." >&2
    exit 1
  fi
fi

cleanup() {
  "${compose_cmd[@]}" down --remove-orphans || true
}
trap cleanup EXIT

"${compose_cmd[@]}" down --remove-orphans || true
"${compose_cmd[@]}" up -d --build

echo "Waiting for ${HEALTH_URL}..."
max_retries=30
retry_count=0
until curl -fsS "${HEALTH_URL}" >/dev/null; do
  if [ "${retry_count}" -ge "${max_retries}" ]; then
    echo "Error: service did not become healthy in time." >&2
    "${compose_cmd[@]}" logs "${SERVICE_NAME}" || true
    exit 1
  fi
  retry_count=$((retry_count + 1))
  sleep 2
  echo "Retry ${retry_count}/${max_retries}..."
done

echo "Compose up smoke test passed."
