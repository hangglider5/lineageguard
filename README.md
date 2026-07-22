# LineageGuard

LineageGuard is a DataHub-native agent that reviews proposed schema changes,
traces their blast radius, produces a validated remediation artifact, and writes
the decision back to DataHub for the next human or agent.

This repository is an entry for the
[DataHub Agent Hackathon](https://datahub.devpost.com/). The submission deadline
is **2026-08-11 05:00 China Standard Time** (2026-08-10 17:00 EDT).

## Current status

The local interface gate passed on 2026-07-22:

- DataHub Core `1.6.0` runs on the official Docker Quickstart.
- The official `showcase-ecommerce` datapack loaded successfully.
- `mcp-server-datahub` `0.6.0` exposed 20 tools over MCP stdio, including
  read-only lineage tools and opt-in mutation tools.
- A search-selected dbt `orders` asset returned 5 upstream and 36 downstream
  assets across datasets, data jobs, dashboards, and charts.
- MCP `save_document` created a Decision document and MCP `get_entities` read it
  back successfully.

Machine-readable evidence is committed at
[`examples/interface-probe.json`](examples/interface-probe.json). The proposal
review and known risks are in [`docs/REVIEW.md`](docs/REVIEW.md).

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

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m compileall -q src tests
bash -n scripts/bootstrap_local.sh
```

## Design

The first vertical slice is deliberately narrow:

1. accept a dbt schema change that removes or changes one column;
2. read schema, ownership, domain, glossary, and multi-hop lineage through MCP;
3. classify direct and transitive impact with deterministic rules;
4. generate and validate a migration decision/checklist;
5. save the decision as a DataHub document related to the impacted assets.

See [`docs/PLAN.md`](docs/PLAN.md) for milestones and evaluation criteria.
