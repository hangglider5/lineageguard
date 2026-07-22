# DataHub Agent Hackathon Plan

Status on 2026-07-22: **LineageGuard selected; local read/write gate passed.**

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

## Schedule

- Jul 22–24: run DataHub locally, load sample graph, select concept
- Jul 25–30: implement one end-to-end scenario
- Jul 31–Aug 4: evaluation harness, error handling, graph write-back
- Aug 5–7: UI/CLI polish, sample outputs, optional upstream feedback/contribution
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

- One scenario runs end-to-end without manual database edits.
- The output is a concrete artifact, not only prose.

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
