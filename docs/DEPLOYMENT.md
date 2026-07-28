# CI and deployment safety

## Pull-request gate

The GitHub Actions workflow runs `scripts/ci.sh` on every push and pull request,
plus manual dispatch after the repository is published. A separate container
smoke job validates the Compose configuration, builds the exact Dockerfile,
asserts the runtime user is `10001:10001`, and requests the health, HTML, and CSS
surfaces. The same deterministic test entry point is available locally:

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

## Fixed-scenario demo API

The public service exposes a same-origin product surface and three API routes:

- `GET /` and the allowlisted `/assets/demo.css` and `/assets/demo.js`
- `GET /health`
- `GET /api/scenarios`
- `POST /api/review`

`POST /api/review` accepts only the committed `drop-orders-order-total` scenario.
The backend fixes `write_back=False`, the lineage cap at 100 assets, and a 30
second upstream timeout. It rejects extra fields, bodies over 1 KiB, unsupported
content types, more than 10 requests per client per minute, and more than two
concurrent MCP workflows. Invalid artifacts fail closed. The service does not
enable CORS, trust caller-supplied forwarding headers, or expose exception
details. A restrictive Content Security Policy permits only same-origin CSS,
JavaScript, and API connections. The interface includes loading, access-key,
rate-limit, timeout, upstream, and artifact-validation failure states.

Run it locally:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.demo_api
```

For an authenticated deployment, configure the environment in the hosting
platform's secret store:

```text
DATAHUB_GMS_URL=https://datahub.example.com
DATAHUB_GMS_TOKEN=<scoped PAT>
LINEAGEGUARD_REQUIRE_DATAHUB_AUTH=true
LINEAGEGUARD_DEMO_API_KEY=<optional caller API key>
```

If `LINEAGEGUARD_DEMO_API_KEY` is set, `/api/review` requires
`Authorization: Bearer <key>`. Health and scenario discovery remain public. Run a
single worker because rate limiting is in memory; put the service behind a trusted
HTTPS reverse proxy for public hosting.

Build the non-root container and pass secrets at runtime, never as build arguments:

```bash
docker build -t lineageguard-demo .
docker run --rm -p 8000:8000 --env-file .env lineageguard-demo
```

The container passes `--require-datahub-auth` by default and runs as UID/GID
10001.

For a hardened single-host deployment, use the committed Compose definition:

```bash
export DATAHUB_GMS_URL="https://datahub.example.com"
export DATAHUB_GMS_TOKEN="replace-with-a-scoped-token"
export LINEAGEGUARD_DEMO_API_KEY="replace-with-a-demo-access-key"
docker compose -f deploy/compose.demo.yml up --build --detach
```

The service binds only to `127.0.0.1:${LINEAGEGUARD_PORT:-8000}` for placement
behind an HTTPS reverse proxy. It uses a read-only root filesystem, a bounded
temporary filesystem, drops all Linux capabilities, enables
`no-new-privileges`, and caps process count. Terminate TLS and apply any
internet-wide rate limiting at the reverse proxy; the application deliberately
does not trust forwarded client headers.

## Remote DataHub requirements

LineageGuard permits tokenless HTTP only for loopback hosts such as
`localhost`, `127.0.0.1`, and `::1`. Any non-loopback DataHub endpoint must use
HTTPS and provide `DATAHUB_GMS_TOKEN`; credentials embedded in the URL are rejected.
Tokens are passed to the MCP child process and are never printed by the workflow.

```bash
export DATAHUB_GMS_TOKEN="replace-with-a-scoped-token"
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
GitHub workflow YAML. A hosted demo should keep `DATAHUB_GMS_TOKEN` in its platform
secret store, disable default DataHub credentials, and expose only the thin
LineageGuard backend over HTTPS.

On 2026-07-28, the local OSS rehearsal enabled Metadata Service Authentication,
verified an unauthenticated GraphQL request returned `401`, issued a one-hour PAT,
and completed MCP read, idempotent Decision write-back, document read-back, and
source-relationship read-back through `DATAHUB_GMS_TOKEN`. The PAT was not logged
or committed and was invalidated when the rehearsal stack returned to its normal
Quickstart signing configuration.

That proves authenticated transport and MCP compatibility, but not least-privilege
authorization: the rehearsal PAT belonged to the local administrator. A dedicated
principal restricted to graph reads plus Document write-back remains mandatory for
the hosted deployment.
