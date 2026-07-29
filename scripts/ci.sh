#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_dir"

python_command="${LINEAGEGUARD_PYTHON:-python3}"
if ! command -v "$python_command" >/dev/null 2>&1; then
  echo "Missing $python_command. Set LINEAGEGUARD_PYTHON to Python 3.10–3.13." >&2
  exit 1
fi

export PYTHONPATH="${repository_dir}/src${PYTHONPATH:+:${PYTHONPATH}}"

"$python_command" -m compileall -q src tests
"$python_command" -m unittest discover -s tests -v
"$python_command" -m lineageguard.evaluation \
  evals/suite.json \
  --output build/evaluation-report.json \
  --markdown-output build/evaluation-report.md
"$python_command" -m lineageguard.submission_gate submission/manifest.json
bash -n scripts/bootstrap_local.sh scripts/ci.sh

echo "LineageGuard offline CI passed."
