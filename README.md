# LineageGuard

LineageGuard is a DataHub-native agent that reviews proposed schema changes,
traces their blast radius, produces a validated remediation artifact, and writes
the decision back to DataHub for the next human or agent.

This repository is an entry for the
[DataHub Agent Hackathon](https://datahub.devpost.com/). The submission deadline
is **2026-08-11 05:00 China Standard Time** (2026-08-10 17:00 EDT).

[Inspect the verified public evidence demo](https://hangglider5.github.io/lineageguard/)
or follow the live local MCP workflow below.

## Current status

The first end-to-end scenario passed on 2026-07-23:

- DataHub Core `1.6.0` runs on the official Docker Quickstart.
- The official `showcase-ecommerce` datapack loaded successfully.
- `mcp-server-datahub` `0.6.0` exposed 20 tools over MCP stdio, including
  read-only lineage tools and opt-in mutation tools.
- The `drop_orders_order_total` scenario verified the source schema and found all
  17 column-level downstream datasets (1 direct and 16 transitive).
- The deterministic policy produced a validated `BLOCK/HIGH` decision, owner
  routes, a migration checklist, and read-only validation SQL.
- MCP `save_document` wrote the Decision back against 18 related assets. Both the
  document read-back and the source asset's `relatedDocuments` edge were verified.
- The fixed evaluation suite passes 16/16 cases and 130/130 checks. A separate
  live DataHub gate passes with all 17 downstream assets and records real MCP
  workflow latency.
- The GitHub Actions workflow is configured to run the shared offline CI gate on
  Python 3.11 and 3.13. Remote DataHub connections fail closed unless they use
  HTTPS and `DATAHUB_GMS_TOKEN`.
- A fixed-scenario, read-only demo API runs the same MCP workflow with request
  limits, timeouts, optional API-key protection, and no public write surface.
- The API now serves a responsive single-screen demo UI with real loading,
  authenticated-access, rate-limit, timeout, upstream, and validation failure
  states. GitHub Actions also builds and smoke-tests the non-root container.
- Metadata Service Authentication was enabled for a local rehearsal and a
  one-hour PAT completed authenticated MCP read, write-back, and both read-back
  checks. Least-privilege policy scoping remains a deployment gate.

The resulting artifacts are committed under
[`examples/drop-orders-order-total/`](examples/drop-orders-order-total/).
Interface evidence is at [`examples/interface-probe.json`](examples/interface-probe.json),
authenticated evidence is at
[`examples/authenticated-gate.json`](examples/authenticated-gate.json), and the
proposal review and known risks are in [`docs/REVIEW.md`](docs/REVIEW.md).

## Local setup

Prerequisites:

- Docker Desktop with at least 2 CPUs, 8 GB RAM, and 13 GB free disk space
- Python 3.10–3.13; Python 3.11 is the tested version

Run the bootstrap:

```bash
./scripts/bootstrap_local.sh
```

The script creates `.venv`, installs the pinned DataHub and MCP packages, starts
DataHub Core `1.6.0`, and loads the showcase graph. It intentionally connects to
local GMS through `DATAHUB_GMS_URL` instead of writing a global CLI token file.

Open the UI at <http://localhost:9002> with `datahub` / `datahub`.

## Verify the MCP interfaces

Read-only MCP handshake, tool schemas, search, and lineage:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.mcp_probe --exercise-search
```

To intentionally create one clearly labeled smoke-test Decision document and
read it back:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.mcp_probe --write-probe-document
```

Mutation tools are disabled by default in the official MCP server. The probe
enables them only in its child process and the write action requires the explicit
flag above.

## Run the first LineageGuard scenario

Generate a decision without mutating DataHub:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.workflow \
  scenarios/drop_orders_order_total.json \
  --output-dir build/drop-orders-order-total
```

The expected verdict is `BLOCK`; that is a successful policy result, not a
process failure. The CLI exits nonzero only for retrieval/runtime failures or an
invalid artifact.

Explicitly write the validated Decision to DataHub and verify it:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.workflow \
  scenarios/drop_orders_order_total.json \
  --output-dir build/drop-orders-order-total \
  --write-back
```

For an idempotent retry, pass the `document_urn` from `write-back.json`:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.workflow \
  scenarios/drop_orders_order_total.json \
  --output-dir build/drop-orders-order-total \
  --write-back \
  --document-urn urn:li:document:YOUR_EXISTING_DOCUMENT_ID
```

The workflow resolves exactly one source dataset, verifies the field and declared
type, retrieves column-level downstream lineage, compacts only attributable graph
metadata, applies fail-closed rules, validates every cited asset/owner/query, and
only then permits write-back.

## Run the fixed evaluations

The offline suite requires neither Docker nor network access:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.evaluation \
  evals/suite.json \
  --output build/evaluation-report.json \
  --markdown-output build/evaluation-report.md
```

With DataHub running, execute the read-only live gate:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.live_evaluation \
  evals/live.json \
  --output build/live-evaluation.json \
  --markdown-output build/live-evaluation.md
```

The offline report measures deterministic local policy latency; the live report
measures the MCP-backed core workflow. See [`evals/README.md`](evals/README.md)
for the scenario and scoring protocol, and
[`examples/evaluation-report.md`](examples/evaluation-report.md) for the current
offline result. The matching MCP-backed result is in
[`examples/live-evaluation.md`](examples/live-evaluation.md).

## Tests

```bash
LINEAGEGUARD_PYTHON=.venv/bin/python ./scripts/ci.sh
```

The same deterministic gate is configured for every GitHub push and pull
request. It does not require Docker, network access, or DataHub credentials. See
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the separate live release gate and
the HTTPS/token rules for a hosted demo.

## Run the demo API

Start the fixed-scenario API against local Quickstart:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.demo_api
```

Then request the only public review scenario:

```bash
curl -fsS \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id":"drop-orders-order-total"}' \
http://127.0.0.1:8000/api/review
```

Or open `http://127.0.0.1:8000/` to run the same review from the responsive demo
UI. The page renders only code-native assets served by LineageGuard itself; it
has no analytics, third-party scripts, fonts, or image requests.

The public API always runs `write_back=False`; callers cannot provide asset URNs,
DataHub endpoints, commands, or filesystem paths. Container and hosted deployment
instructions are in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Public evidence snapshot

The GitHub Pages workflow publishes a zero-secret, static version of the same
interface for judges. It is explicitly labeled **Verified evidence snapshot**:
the button loads a committed result rather than claiming to query DataHub live.
`scripts/build_pages.py` cross-checks the Decision against the live MCP evaluation,
fixed evaluation, authenticated write-back, Document read-back, and relationship
read-back evidence before it emits the site. Any contradiction fails the build.

The snapshot complements rather than replaces the live proof. The container API
still runs the read-only MCP workflow, and the demo video shows the explicit
authenticated write-back/read-back path. Build the static site into a fresh
directory with:

```bash
pages_root="$(mktemp -d)"
.venv/bin/python scripts/build_pages.py --output "$pages_root/site"
python3 -m http.server 4173 --directory "$pages_root/site"
```

## Prepare the submission

The English Devpost draft, disclosure text, machine-readable readiness manifest,
and 2:55 demo script are committed under [`submission/`](submission/). Validate
all local materials without requiring unpublished URLs:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.submission_gate \
  submission/manifest.json
```

Immediately before submitting, add the public repository, project, and video
URLs to `submission/manifest.json` and run the strict gate:

```bash
PYTHONPATH=src .venv/bin/python -m lineageguard.submission_gate \
  submission/manifest.json \
  --strict
```

## Design

The implemented first vertical slice is deliberately narrow:

1. accept a dbt schema change that removes or changes one column;
2. read schema, ownership, domain, glossary, and multi-hop lineage through MCP;
3. classify direct and transitive impact with deterministic rules;
4. generate and validate a migration decision/checklist;
5. save the decision as a DataHub document related to the impacted assets.

See [`docs/PLAN.md`](docs/PLAN.md) for milestones and evaluation criteria.
