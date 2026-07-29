# LineageGuard demo script

Target length: 2 minutes 55 seconds. Spoken narration is represented by blockquotes so the submission gate can enforce a safe word budget.

## 00:00–00:20 — The change

**Shot:** Open the LineageGuard demo at the fixed `orders.order_total` scenario. Keep the source, column, and change facts visible.

> A single schema change can break assets several hops away, but the pull request rarely contains the lineage, owners, or governance context needed to review it safely. This proposal drops order total from our dbt orders model. LineageGuard uses DataHub to turn that local diff into an auditable migration decision.

## 00:20–00:45 — Read the graph

**Shot:** Select **Run impact review**. Hold on the loading state as it lists source resolution, lineage tracing, and artifact validation.

> When I run the review, LineageGuard starts the standalone DataHub MCP Server. It resolves one exact dataset, verifies that the column exists with the declared type, then reads fine-grained downstream lineage together with ownership, domains, tags, and glossary terms. The public demo is read-only, and callers cannot provide their own URNs, commands, endpoints, or write-back flags.

## 00:45–01:25 — Explain the decision

**Shot:** Show the live `BLOCK / HIGH` result, the 17 downstream count, representative lineage, and the three action summaries.

> The result is block, high severity. DataHub reports seventeen attributable downstream column consumers: one direct and sixteen transitive. The graph is complete, so this is not a guess based on a truncated window. LineageGuard routes the decision to twelve discovered owners, identifies ownership gaps, stages migration work for every impacted asset, and generates a read-only source validation query. Every asset shown here comes from the retrieved graph.

## 01:25–01:55 — Show the artifacts

**Shot:** Open `decision.json`, `migration-checklist.md`, and the validation SQL portion of the checklist side by side.

> The agent produces more than prose. The JSON Decision records evidence, reason codes, owner and domain routes, required actions, and validation queries. The Markdown checklist is ready for a change review. Before either artifact is accepted, a separate validator rejects unsupported assets, incorrect routing, unsafe SQL, incomplete lineage, or a verdict that does not match the evidence.

## 01:55–02:25 — Prove write-back

**Shot:** Run the explicit CLI write-back command, then show the receipt and the related Decision Document in DataHub.

> Write-back is deliberately separate and explicit. With mutation enabled, LineageGuard saves the validated result as a DataHub Decision related to the source and all seventeen impacted assets. It then reads the Document back by URN and verifies that the source asset exposes the same relationship. A retry can update the same Document instead of creating duplicates.

## 02:25–02:45 — Show evaluation evidence

**Shot:** Show the fixed evaluation summary and the CI workflow result: 16 of 16 cases, 130 of 130 checks, and 53 tests.

> Reliability is part of the product. Sixteen fixed scenarios cover safe additions, breaking changes, missing or contradictory metadata, truncated lineage, ownership gaps, artifact attacks, and idempotent write-back. All one hundred thirty checks pass, alongside fifty-three automated tests and a separate live MCP gate.

## 02:45–02:55 — Close

**Shot:** Return to the completed LineageGuard decision screen.

> LineageGuard closes the loop from context, to decision, to validated action, to durable knowledge in DataHub. It helps data teams stop unsafe changes before they ship, without asking reviewers to trust unsupported claims.
