# LineageGuard Judge Guide

LineageGuard is a DataHub-native schema-change agent. It reads attributable
graph context, makes a fail-closed impact decision, asks a bounded AI planner for
a grounded migration sequence, validates the result, and writes the verified
Decision back to DataHub.

## 60-second path

1. Open the [verified public demo](https://hangglider5.github.io/lineageguard/)
   and select **Inspect verified evidence**.
2. Confirm the result is `BLOCK / HIGH`, with 17 downstream assets and
   **17 AI-planned assets · 3/3 live runs**.
3. Open the committed
   [integrated workflow receipt](examples/drop-orders-order-total/integrated-workflow.json)
   and confirm `planner.status`, `write_back.success`,
   `document_read_back_verified`, and `source_relationship_verified`.

The public page is intentionally a zero-secret evidence replay. It does not
pretend that a browser click reaches the entrant's local DataHub instance.

## Evidence map

| Claim | Inspect | Expected evidence |
| --- | --- | --- |
| DataHub found the blast radius | [Decision](examples/drop-orders-order-total/decision.json) | `BLOCK / HIGH`, complete lineage, 17 attributable assets |
| The planner stayed grounded | [Three-run rehearsal](examples/drop-orders-order-total/planner-rehearsal.json) | 3/3 accepted, one attempt each, stable context and prompt hashes |
| The model produced a concrete plan | [Integrated plan](examples/drop-orders-order-total/integrated-migration-plan.json) | 17 unique assets with platform-constrained actions |
| The full loop completed | [Integrated receipt](examples/drop-orders-order-total/integrated-workflow.json) | Live MCP read, accepted plan, Document update, and both read-backs |
| No result is accepted on prose alone | [Fixed evaluation](examples/evaluation-report.md) | 16/16 cases and 130/130 exact checks |
| Authenticated MCP transport works | [Authentication gate](examples/authenticated-gate.json) | PAT read/write/read-back with no committed credential |
| The current revision is green | [GitHub Actions](https://github.com/hangglider5/lineageguard/actions) | CI and Pages passing on `main` |

The Pages build independently cross-checks the Decision, planner coverage,
actions, frozen hashes, exact integrated sidecars, and DataHub read-back receipts.
Contradictory committed evidence fails the build.

## Five-minute source verification

This path needs Python but does not need Docker, DataHub, an LLM key, or network
access after dependencies are installed:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
LINEAGEGUARD_PYTHON=.venv/bin/python ./scripts/ci.sh
```

Expected result: 92 tests, 16/16 evaluation cases, 130/130 checks, and a passing
local submission gate. The only external submission blocker before publishing
the final video is `video_url`.

## Full live reproduction

The live path requires Docker Desktop with at least 13 GB free:

```bash
./scripts/bootstrap_local.sh
PYTHONPATH=src .venv/bin/python -m lineageguard.workflow \
  scenarios/drop_orders_order_total.json \
  --output-dir build/judge-review
```

This runs the read-only DataHub MCP workflow and produces a deterministic
Decision. Model planning and graph mutation are separate opt-in operations; see
the [README](README.md#run-the-bounded-ai-planner) for their explicit flags and
credential requirements.

## What the video proves

The under-three-minute video shows the live local DataHub path that the public
snapshot cannot safely expose: MCP graph reads, the validated Decision, bounded
DeepSeek planning, explicit Document update, and both read-back checks. The
public repository, project URL, and video remain available through the end of
judging on September 1, 2026 at 05:00 China Standard Time.
