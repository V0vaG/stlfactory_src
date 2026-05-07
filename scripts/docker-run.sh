#!/usr/bin/env bash
# Run the app with plain `docker` (no Compose). Use this if docker-compose-plugin
# is not available on your distro.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

IMAGE="${IMAGE:-stlfactory:local}"

docker build -t "$IMAGE" "$ROOT"

exec docker run --rm \
  -p "${PORT:-5000}:5000" \
  -v "$ROOT/models:/app/models" \
  -e FLASK_DEBUG="${FLASK_DEBUG:-0}" \
  -e PYTHONUNBUFFERED=1 \
  "$IMAGE"
