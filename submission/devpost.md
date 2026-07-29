# LineageGuard

**Tagline:** A DataHub-native agent that turns risky schema changes into validated, auditable migration decisions.

**Try it:** [Verified public evidence demo](https://hangglider5.github.io/lineageguard/)

## Problem

A column rename or deletion can silently break dashboards, warehouse models, and ML features several hops away. Engineers often review these changes with incomplete context: a schema diff in one tab, lineage in another, and owner information scattered across tools. DataHub already knows how the stack is connected, but an impact graph alone does not produce a safe migration plan or preserve the decision for the next reviewer.

## Solution

LineageGuard is a pre-merge schema-change agent built on DataHub OSS and the DataHub MCP Server. It resolves the exact source asset and field, reads column-level lineage plus ownership and governance context, classifies compatibility risk, generates a concrete remediation artifact, validates every claim, and can write the verified Decision back to DataHub.

The primary demo asks whether a team can drop `orders.order_total`. LineageGuard verifies the dbt field and its `FLOAT` type, discovers 17 attributable downstream column consumers, and returns `BLOCK / HIGH` with accountable owners, domain fallbacks, migration actions, and a read-only validation query.

## How it works

1. A strict change model accepts a proposed add, drop, rename, or type change.
2. The agent uses MCP search to resolve one unambiguous DataHub dataset.
3. It verifies the source schema and retrieves bounded, deduplicated column lineage.
4. A fail-closed policy turns attributable graph evidence into a structured Decision.
5. A separate validator rejects unsupported assets, owner or domain misrouting, unsafe SQL, incomplete lineage, and verdict tampering.
6. An explicit mutation path saves the validated Decision as a DataHub Document and reads back both the Document and its relationship to the source asset.

The live demo API is intentionally read-only. The [permanent GitHub Pages demo](https://hangglider5.github.io/lineageguard/) transparently replays a committed, validated evidence snapshot without secrets; the local live run and authenticated write-back receipt prove the DataHub interaction. Graph mutation remains a separately authorized, auditable operation.

## How we use DataHub

DataHub is the system of context and the system of record for the result. LineageGuard reads schemas, fine-grained lineage, owners, domains, tags, and glossary terms through the standalone DataHub MCP Server. It compacts large responses without losing URNs or completeness evidence. After validation, it writes a first-class Decision Document related to the source and every materially impacted asset, so future humans and agents inherit the reasoning.

## Validation

The fixed evaluation suite contains 16 versioned cases and 130 exact checks covering safe additions, breaking changes, type mismatches, missing fields, truncated lineage, ownership gaps, domain routing, artifact tampering, unsafe SQL, and verified idempotent write-back. All cases pass. The repository also has more than 50 automated tests, a separate live MCP-backed gate that rechecks all 17 downstream assets, and a PAT-authenticated read/write/read-back receipt.

## What makes it different

LineageGuard does not rebuild DataHub's impact-analysis UI. It closes the operational loop after discovery: change proposal, attributable graph evidence, deterministic decision, concrete migration files, adversarial validation, and graph write-back. The safety-critical verdict remains reproducible and inspectable instead of depending on an unconstrained model response.

## Built with

- DataHub OSS/Core 1.6.0 and the official showcase-ecommerce graph
- DataHub MCP Server 0.6.0 over MCP stdio
- Python 3.11–3.13, Pydantic, Starlette, and Uvicorn
- Docker, Docker Compose, and GitHub Actions
- A code-native responsive interface with no third-party browser assets

## Challenges

DataHub Core does not expose the managed `/mcp` endpoint, so the OSS deployment needs the standalone MCP server. Raw multi-hop lineage exceeded 100,000 characters, which required deterministic compaction and an independent completeness proof. We also found that the DataHub SDK and MCP process expect `DATAHUB_GMS_TOKEN`, and verified the full authenticated path after enabling Metadata Service Authentication locally.

## What's next

The next release gates are a hosted HTTPS demo and a dedicated least-privilege DataHub principal. We also plan to add a bounded model-assisted planner that proposes richer migration patches while keeping the existing deterministic policy and validator as the authority, plus a pull-request integration and a second live change scenario.

## Disclosures

No LineageGuard project code predates the hackathon submission period. The project builds on DataHub and the open-source dependencies declared in `pyproject.toml`. OpenAI Codex assisted with implementation, code review, testing, documentation, and visual concept exploration. The entrant directed the product and is responsible for the submitted work.
