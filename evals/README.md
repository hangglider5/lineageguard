# LineageGuard evaluation protocol

The evaluation has two intentionally separate layers.

The optional bounded-model layer is evaluated separately. Unit and adversarial
tests use fixed transport responses so CI remains deterministic and zero-cost. A
real-provider rehearsal runs 1–5 times against a committed Decision and requires
every plan to pass exact asset, column, owner, dependency, output-schema, and
non-executable-text checks:

```bash
lineageguard-planner-rehearsal \
  examples/drop-orders-order-total/decision.json \
  --output-dir build/planner-rehearsal \
  --runs 3
```

The full live gate adds `--planner model --require-planner` to the normal workflow.
Neither real-provider path runs in GitHub Actions or exposes a key to the DataHub
MCP child process.

The frozen-contract DeepSeek rehearsal passed 3/3 runs on the first attempt. Its
redacted report and representative plan are committed under
`examples/drop-orders-order-total/` and independently cross-checked by the Pages
build before publication.

## Fixed offline suite

`suite.json` contains 16 strict, versioned cases with explicit schema changes,
graph snapshots, and expected outcomes:

- 10 decision cases: safe addition, existing-field collision, direct and
  transitive impact, rename, type change, declared-type mismatch, missing field,
  incomplete lineage, ownership gaps, and complete owner routing;
- 5 adversarial artifacts: unsupported asset, invalid owner route, invalid domain
  fallback, mutation SQL, and an unsafe verdict override;
- 1 recorded graph write-back receipt requiring document read-back, source-edge
  verification, and at least 18 requested related assets.

Run it without Docker or network access:

```bash
lineageguard-eval evals/suite.json \
  --output build/evaluation-report.json \
  --markdown-output build/evaluation-report.md
```

The suite reports exact verdict, severity, reason, action, owner route, domain
fallback, lineage-completeness, and impacted-URN checks. Its latency covers only
local policy and artifact validation; it explicitly excludes MCP and network
work.

## Live DataHub gate

`live.json` fixes the expected result for the pinned `showcase-ecommerce` graph.
It runs the real MCP search, entity/schema reads, complete column-lineage fetch,
decision, and artifact validation with mutation tools disabled:

```bash
lineageguard-live-eval evals/live.json \
  --output build/live-evaluation.json \
  --markdown-output build/live-evaluation.md
```

This report records core workflow end-to-end latency. It does not perform a new
write on every run; write-back correctness is covered by the verified receipt and
the dedicated idempotency tests.

Committed example reports are in `examples/evaluation-report.*` and
`examples/live-evaluation.*`.
