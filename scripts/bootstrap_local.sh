#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_dir"

python_command="${LINEAGEGUARD_PYTHON:-python3.11}"
if ! command -v "$python_command" >/dev/null 2>&1; then
  echo "Missing $python_command. Set LINEAGEGUARD_PYTHON to Python 3.10–3.13." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install and start Docker Desktop first." >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  "$python_command" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --editable .

DATAHUB_TELEMETRY_ENABLED=false \
  .venv/bin/datahub docker quickstart \
  --version v1.6.0 \
  --dump-logs-on-failure

DATAHUB_GMS_URL=http://localhost:8080 \
DATAHUB_SKIP_CONFIG=true \
DATAHUB_TELEMETRY_ENABLED=false \
  .venv/bin/datahub datapack load showcase-ecommerce

echo "DataHub is ready at http://localhost:9002 (datahub / datahub)."
echo "Run the MCP probe shown in README.md to verify search and lineage."
