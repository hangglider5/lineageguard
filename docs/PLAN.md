# DataHub Agent Hackathon Plan

Status on 2026-07-29: **first scenario, fixed evaluation v1, offline and
container CI, the responsive read-only demo, PAT-authenticated MCP compatibility,
and the first submission kit draft are complete.**

## Objective

Produce a reliable agent that uses DataHub's context graph to diagnose a real
data-platform change, creates a concrete remediation artifact, and writes the
result back so future humans or agents inherit the decision.

Primary target: **Agents That Do Real Work**.

Secondary fit: **Metadata-Aware Code Generation & Development**.

## Recommended concept

Working name: **LineageGuard**

A pull-request and incident companion that:

1. reads schema, ownership, domain, glossary and lineage context from DataHub;
2. estimates the blast radius of a proposed schema or pipeline change;
3. generates a reviewable remediation artifact, such as a migration checklist,
   dbt patch, owner notification plan or validation query;
4. runs deterministic checks on the artifact;
5. writes a structured decision, status or incident note back to DataHub.

The competition story is not "chat with metadata." It is a closed loop:
context -> decision -> validated action -> graph write-back.

## Alternatives parked after the Jul 22 technical gate

- ML Lineage Incident Investigator: trace model-quality regressions back through
  features and datasets, then write an incident record.
- Data Contract Repair Agent: detect contract drift, propose a patch and record
  the accepted compatibility decision.

LineageGuard won the gate because the showcase graph supports a credible
cross-platform blast radius and the MCP server can write a linked Decision
document. Revisit an alternative only if the first dbt change scenario cannot
produce a deterministic validated artifact by Jul 30.

## Required architecture

- Local DataHub OSS quickstart pinned to `1.6.0`
- Standalone DataHub MCP Server pinned to `0.6.0`; DataHub Core GMS does not
  expose the managed `/mcp` endpoint used by DataHub Cloud
- Small deterministic orchestration layer around model calls
- Synthetic but realistic data-platform graph and change scenarios
- Validation/evaluation harness that can run without the UI
- Thin demo UI or CLI only after the vertical slice works

## Evaluation

Create 10–20 fixed scenarios covering:

- direct and transitive downstream impact;
- ownership and domain-aware routing;
- safe versus breaking schema changes;
- missing or contradictory metadata;
- invalid model-generated artifacts;
- successful DataHub write-back.

Track task completion, correct impacted assets, artifact validity, unsupported
claims, write-back success and end-to-end latency.

Implemented in fixed evaluation v1:

- [x] 16 versioned cases with explicit graph fixtures and expected outputs
- [x] exact verdict, severity, reason, action, impacted-URN, and lineage checks
- [x] exact owner routing and domain fallback for ownerless assets
- [x] adversarial rejection for unsupported assets, owner/domain misrouting,
  unsafe SQL, and verdict override
- [x] verified write-back receipt check
- [x] offline policy latency reported separately from live MCP workflow latency
- [x] shared local/GitHub Actions gate on Python 3.11 and 3.13
- [x] fixed-scenario public API with no write surface, timeout, body, and rate caps
- [x] authenticated MCP read/write/read-back using a one-hour local PAT
- [x] responsive one-screen demo with explicit loading and failure states
- [x] non-root container smoke gate and hardened single-host Compose definition
- [x] English Devpost draft, disclosure, and 2:55 demo script
- [x] local/strict submission readiness gate

## Schedule

- Jul 22–24: run DataHub locally, load sample graph, select concept — complete
- Jul 25–27: end-to-end scenario, fixed evaluation, graph write-back — complete
- Jul 28: shared offline CI and remote connection safety baseline — complete
- Jul 29–Aug 1: public demo backend and scoped-token authentication rehearsal
- Aug 2–4: demo UI/CLI polish, failure states, fresh evaluation pass
- Aug 5–7: sample outputs and optional upstream feedback/contribution
- Aug 8: record rough demo and draft Devpost text
- Aug 9: freeze code; fresh-machine setup rehearsal
- Aug 10: submission buffer only

## Go/no-go gates

Jul 24:

- [x] DataHub starts locally and exposes enough graph context for the chosen story.
- [x] MCP search and 3+ hop lineage reads succeed on a sample dbt asset.
- [x] A harmless Decision document write-back and read-back succeed.
- [ ] Token-authenticated MCP read/write succeeds with scoped permissions.

Jul 30:

- [x] One scenario runs end-to-end without manual database edits.
- [x] The output is a concrete artifact, not only prose.

The gate was reached early on Jul 23. Fixed evaluation v1 now covers safe
additions, type mismatches, missing fields, truncated lineage, ownership gaps,
artifact tampering, and verified/idempotent write-back behavior. The next target
is a hosted demo endpoint and least-privilege principal. As of Jul 28, the
demo-safe backend, responsive UI, container smoke gate, and PAT transport gate
are complete, and remote endpoints are rejected unless they use HTTPS and
`DATAHUB_GMS_TOKEN`. The remaining auth gate is a scoped-principal MCP read/write
rehearsal against the deployment target.

The first English Devpost draft and a 362-word demo narration are also complete.
The public repository is now configured. The submission gate passes all local
materials and intentionally reports two external blockers until the hosted
project and video URLs are configured.

If either gate fails, reduce scope to a CLI and a single change type. Do not
remove evaluation or write-back.

## Submission checklist

- New work created during the competition period
- Apache-2.0 license
- Public repository and working test/demo URL
- Keep the working project available through Aug 31, 2026 at 17:00 EDT
- Complete setup and sample dataset instructions
- Example outputs committed to `examples/`
- Public English demo under three minutes
- English Devpost narrative
- Disclosure of pre-existing tools, templates and AI assistance

## Initial budget

- Model/API usage: USD 30–80
- Hosting/demo: USD 0–25
- Contingency: USD 20
- Target cap: USD 120
