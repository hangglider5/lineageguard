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

## 01:25–02:00 — Show the artifacts and bounded planner

**Shot:** Open `decision.json`, `migration-plan.json`, `planner-receipt.json`, and the combined checklist side by side.

> The deterministic Decision records evidence, routes, required actions, and validation queries. Only after it passes validation does a bounded DeepSeek planner receive the compact graph facts. It proposes sequencing, execution prerequisites, rationale, and success criteria, but it cannot change the verdict, assets, owners, columns, or write targets. A second validator rejects incompatible actions, backward lineage order, executable text, and unsupported structured claims. The frozen contract passed three live runs with all seventeen assets grounded and no retries.

## 02:00–02:25 — Prove write-back

**Shot:** Run the explicit CLI write-back command, then show the receipt and the related Decision Document in DataHub.

> Write-back is deliberately explicit. In our integrated proof run, the accepted model plan and validated Decision stayed in the same workflow before LineageGuard updated the existing DataHub Decision related to the source and all seventeen impacted assets. It then read the Document back by URN and verified that the source asset exposed the same relationship, without creating a duplicate.

## 02:25–02:45 — Show evaluation evidence

**Shot:** Show the fixed evaluation summary, the three-run planner receipt, and CI: 16 of 16 cases, 130 of 130 checks, and more than 90 tests.

> Reliability is part of the product. Sixteen fixed scenarios cover safe additions, breaking changes, contradictory metadata, truncated lineage, ownership gaps, artifact attacks, and idempotent write-back. All one hundred thirty checks pass, alongside more than ninety automated tests, three grounded model runs, and a separate live MCP gate.

## 02:45–02:55 — Close

**Shot:** Return to the completed LineageGuard decision screen.

> LineageGuard closes the loop from context, to decision, to validated action, to durable knowledge in DataHub. It helps data teams stop unsafe changes before they ship, without asking reviewers to trust unsupported claims.
