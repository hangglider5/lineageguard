# CI and deployment safety

## Pull-request gate

The GitHub Actions workflow runs `scripts/ci.sh` on every push and pull request,
plus manual dispatch after the repository is published. The same entry point is
available locally:

```bash
LINEAGEGUARD_PYTHON=.venv/bin/python ./scripts/ci.sh
```

The gate compiles the source, runs all unit tests, executes the versioned fixed
evaluation suite, and checks the shell scripts. It is intentionally offline and
does not start the roughly 13 GB DataHub Quickstart stack. This keeps pull-request
results deterministic and makes contributions from forks safe to test without
repository secrets.

Before a release or demo, run the separate MCP-backed gate against the pinned
local DataHub graph:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.live_evaluation \
  evals/live.json \
  --output build/live-evaluation.json \
  --markdown-output build/live-evaluation.md
```

## Remote DataHub requirements

LineageGuard permits tokenless HTTP only for loopback hosts such as
`localhost`, `127.0.0.1`, and `::1`. Any non-loopback DataHub endpoint must use
HTTPS and provide `DATAHUB_TOKEN`; credentials embedded in the URL are rejected.
Tokens are passed to the MCP child process and are never printed by the workflow.

```bash
export DATAHUB_TOKEN="replace-with-a-scoped-token"
PYTHONPATH=src .venv/bin/python -m lineageguard.workflow \
  scenarios/drop_orders_order_total.json \
  --gms-url https://datahub.example.com \
  --output-dir build/drop-orders-order-total
```

For a token-authenticated local rehearsal, add `--require-token`. Use a dedicated
DataHub service account or personal access token with the minimum permissions
needed for the demo. Read-only runs need entity, schema, and lineage reads;
`--write-back` additionally needs permission to create or update Documents and
their asset relationships.

Do not place tokens in scenarios, command arguments, committed `.env` files, or
GitHub workflow YAML. A hosted demo should keep `DATAHUB_TOKEN` in its platform
secret store, disable default DataHub credentials, and expose only the thin
LineageGuard backend over HTTPS.

The current local OSS proof verifies tokenless loopback read/write. A scoped,
token-authenticated read/write rehearsal remains a release gate and must not be
claimed complete until the target DataHub deployment issues a working token.
