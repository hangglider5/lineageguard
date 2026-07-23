# LineageGuard evaluation: lineageguard-fixed-v1

**Cases:** 16/16 passed (100.0%)
**Checks:** 130/130 passed
**Execution scope:** offline policy and artifact validation (excludes MCP/network latency)
**Offline latency:** p50 0.087 ms, p95 0.725 ms, max 0.725 ms

## Metrics

| Metric | Passed | Rate |
| --- | ---: | ---: |
| `artifact_guardrail_rejection` | 2/2 | 100.0% |
| `artifact_validity` | 10/10 | 100.0% |
| `determinism` | 10/10 | 100.0% |
| `impacted_asset_accuracy` | 10/10 | 100.0% |
| `policy_detail_accuracy` | 10/10 | 100.0% |
| `task_completion` | 16/16 | 100.0% |
| `unsupported_claim_prevention` | 3/3 | 100.0% |
| `verdict_accuracy` | 10/10 | 100.0% |
| `write_back_evidence` | 1/1 | 100.0% |

## Cases

| Case | Category | Kind | Result | Latency |
| --- | --- | --- | --- | ---: |
| `safe-add-new-field` | safe-change | decision | **PASS** | 0.725 ms |
| `add-existing-field` | contradictory-schema | decision | **PASS** | 0.049 ms |
| `drop-direct-transitive-with-gap` | breaking-change | decision | **PASS** | 0.142 ms |
| `rename-without-consumers` | breaking-change | decision | **PASS** | 0.051 ms |
| `type-change-with-impact` | breaking-change | decision | **PASS** | 0.106 ms |
| `declared-type-mismatch` | contradictory-schema | decision | **PASS** | 0.107 ms |
| `missing-source-field` | missing-metadata | decision | **PASS** | 0.039 ms |
| `truncated-lineage` | incomplete-metadata | decision | **PASS** | 0.162 ms |
| `fully-owned-routing` | owner-routing | decision | **PASS** | 0.097 ms |
| `single-direct-consumer` | direct-impact | decision | **PASS** | 0.060 ms |
| `reject-unsupported-action-asset` | unsupported-claim | artifact_validation | **PASS** | 0.083 ms |
| `reject-owner-misroute` | unsupported-claim | artifact_validation | **PASS** | 0.087 ms |
| `reject-mutation-sql` | unsafe-artifact | artifact_validation | **PASS** | 0.078 ms |
| `reject-domain-misroute` | unsupported-claim | artifact_validation | **PASS** | 0.087 ms |
| `reject-wrong-verdict` | unsafe-artifact | artifact_validation | **PASS** | 0.072 ms |
| `verified-write-back-receipt` | graph-write-back | write_back_receipt | **PASS** | 0.126 ms |
