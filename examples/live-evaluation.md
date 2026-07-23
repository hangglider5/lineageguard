# LineageGuard live evaluation: drop-orders-order-total-live

**Result:** PASS
**Execution scope:** live DataHub MCP read-only workflow
**End-to-end latency:** 1168.633 ms

## Actual result

- Decision: `lineageguard:drop-orders-order-total`
- Source: `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.order_entry_db.order_entry.orders,PROD)`
- Verdict/severity: `block/high`
- Downstream reported/evaluated: `17/17`
- Lineage complete: `True`
- Artifact validation errors: `0`
- Owner routes: `12`
- Domain fallback routes: `1`

## Checks

- [x] `verdict`
- [x] `severity`
- [x] `downstream_total`
- [x] `evaluated_downstream`
- [x] `lineage_complete`
- [x] `artifact_valid`
- [x] `owner_routes`
- [x] `domain_routes`
- [x] `source_resolved`
