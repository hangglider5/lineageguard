# LineageGuard

**Tagline:** A DataHub-native agent that turns risky schema changes into validated, auditable migration decisions.

**Try it:** [Verified public evidence demo](https://hangglider5.github.io/lineageguard/)

## Problem

A column rename or deletion can silently break dashboards, warehouse models, and ML features several hops away. Engineers often review these changes with incomplete context: a schema diff in one tab, lineage in another, and owner information scattered across tools. DataHub already knows how the stack is connected, but an impact graph alone does not produce a safe migration plan or preserve the decision for the next reviewer.

## Solution

LineageGuard is a pre-merge schema-change agent built on DataHub OSS and the DataHub MCP Server. It resolves the exact source asset and field, reads column-level lineage plus ownership and governance context, classifies compatibility risk, generates a concrete remediation artifact, validates every claim, and can write the verified Decision back to DataHub.

After the deterministic verdict is validated, an optional bounded AI planner turns the attributable graph evidence into an ordered, platform-aware migration plan. The model cannot change the verdict, invent assets or owners, emit executable code, or call DataHub mutation tools. DeepSeek Official API and OpenRouter share the same strict output contract, semantic validator, redacted receipt, and deterministic fallback.

Against the frozen contract, DeepSeek completed three of three live rehearsals on the first attempt. Every run covered the same 17 assets, copied exact column and owner evidence, used the single action allowed by each graph entity, and moved through nondecreasing lineage degree. A subsequent integrated run used the same frozen context to complete live MCP read, accepted planning, Decision update, Document read-back, and source-relationship read-back in one workflow. The permanent demo publishes the representative plan and redacted run evidence.

The primary demo asks whether a team can drop `orders.order_total`. LineageGuard verifies the dbt field and its `FLOAT` type, discovers 17 attributable downstream column consumers, and returns `BLOCK / HIGH` with accountable owners, domain fallbacks, migration actions, and a read-only validation query.

## How it works

1. A strict change model accepts a proposed add, drop, rename, or type change.
2. The agent uses MCP search to resolve one unambiguous DataHub dataset.
3. It verifies the source schema and retrieves bounded, deduplicated column lineage.
4. A fail-closed policy turns attributable graph evidence into a structured Decision.
5. A separate validator rejects unsupported assets, owner or domain misrouting, unsafe SQL, incomplete lineage, and verdict tampering.
6. The bounded planner proposes an ordered advisory plan; a second validator checks its exact assets, evidence, actions, ordering, and non-executable text.
7. An explicit mutation path saves the validated Decision as a DataHub Document and reads back both the Document and its relationship to the source asset.

The live demo API is intentionally read-only. The [permanent GitHub Pages demo](https://hangglider5.github.io/lineageguard/) transparently replays a committed, validated evidence snapshot without secrets; the local live run and authenticated write-back receipt prove the DataHub interaction. Graph mutation remains a separately authorized, auditable operation.

## How we use DataHub

DataHub is the system of context and the system of record for the result. LineageGuard reads schemas, fine-grained lineage, owners, domains, tags, and glossary terms through the standalone DataHub MCP Server. It compacts large responses without losing URNs or completeness evidence. After validation, it writes a first-class Decision Document related to the source and every materially impacted asset, so future humans and agents inherit the reasoning.

## Validation

The fixed evaluation suite contains 16 versioned cases and 130 exact checks covering safe additions, breaking changes, type mismatches, missing fields, truncated lineage, ownership gaps, domain routing, artifact tampering, unsafe SQL, and verified idempotent write-back. All cases pass. More than 90 automated tests additionally cover the bounded planner contract, provider envelopes, malicious model outputs, transient failures, deterministic fallback, and secret isolation. Three frozen-contract DeepSeek runs passed with 17/17 grounded assets and no retries. A separate live MCP-backed gate rechecks all 17 downstream assets, and a redacted integrated receipt proves that accepted model planning and live MCP write/read-back can complete in the same execution; the PAT receipt separately proves authenticated transport.

## What makes it different

LineageGuard does not rebuild DataHub's impact-analysis UI. It closes the operational loop after discovery: change proposal, attributable graph evidence, deterministic decision, bounded AI planning, concrete migration files, adversarial validation, and graph write-back. The model contributes platform-aware planning while the safety-critical verdict and write targets remain reproducible and inspectable.

## Built with

- DataHub OSS/Core 1.6.0 and the official showcase-ecommerce graph
- DataHub MCP Server 0.6.0 over MCP stdio
- DeepSeek/OpenRouter-compatible bounded model planning
- Python 3.11–3.13, Pydantic, Starlette, and Uvicorn
- Docker, Docker Compose, and GitHub Actions
- A code-native responsive interface with no third-party browser assets

## Challenges

DataHub Core does not expose the managed `/mcp` endpoint, so the OSS deployment needs the standalone MCP server. Raw multi-hop lineage exceeded 100,000 characters, which required deterministic compaction and an independent completeness proof. Early real-model rehearsals exposed JSON truncation, ambiguous BI action labels, and unsupported free-text counts; those failures drove tighter output limits, per-asset action allowlists, lineage-degree ordering, and explicit advisory boundaries. We also verified the authenticated read/write/read-back path after enabling Metadata Service Authentication locally.

## What's next

The next release gates are a dedicated least-privilege DataHub principal, pull-request integration, and a second live change scenario. The public surface will remain read-only unless a separately authenticated, budget-limited model endpoint is deployed.

## Disclosures

No LineageGuard project code predates the hackathon submission period. The project builds on DataHub and the open-source dependencies declared in `pyproject.toml`. OpenAI Codex assisted with implementation, code review, testing, documentation, and visual concept exploration. HeyGen synthesized temporary rough-cut narration for timing and review. The entrant directed the product and is responsible for the submitted work.
