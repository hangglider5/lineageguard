# LineageGuard decision: drop-orders-order-total

**Verdict:** BLOCK
**Severity:** HIGH

BLOCK drop_column of order_total: 17 downstream assets reported, 17 evaluated.

## Evidence

- Source: `urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.order_entry_db.order_entry.orders,PROD)`
- Changed field: `order_total`
- Observed type: `FLOAT`
- Source owners: `2`
- Source domains/tags/terms: `1/0/3`
- Field tags/terms: `Order Total`
- Field verified: `True`
- Downstream reported/evaluated: `17/17`
- Direct/transitive: `1/16`
- Complete lineage page set: `True`

## Impacted assets

| Hop | Type | Platform | Asset | Owners | Impacted columns |
| ---: | --- | --- | --- | ---: | --- |
| 1 | DATASET | dbt | `order_details`<br>`urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_details,PROD)` | 10 | `order_total` |
| 3 | DATASET | dbt | `order_history`<br>`urn:li:dataset:(urn:li:dataPlatform:dbt,b2fd91.ORDER_ENTRY_DB.analytics.order_history,PROD)` | 0 | `order_total` |
| 3 | DATASET | looker | `order_details`<br>`urn:li:dataset:(urn:li:dataPlatform:looker,b2fd91.order-entry-looker.view.order_details,PROD)` | 4 | `order_total` |
| 4 | DATASET | looker | `Order Details`<br>`urn:li:dataset:(urn:li:dataPlatform:looker,b2fd91.order-entry.explore.order_details,PROD)` | 3 | `order_details.order_total` |
| 3 | DATASET | powerbi | `Customer Analytics Measures`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Customer_Analytics_Measures,PROD)` | 0 | `ORDER_TOTAL` |
| 3 | DATASET | powerbi | `Essential KPI Measures`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Essential_KPI_Measures,PROD)` | 0 | `ORDER_TOTAL`, `Total Revenue` |
| 3 | DATASET | powerbi | `Geographic Measures`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Geographic_Measures,PROD)` | 0 | `ORDER_TOTAL` |
| 3 | DATASET | powerbi | `ORDER_DETAILS`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.ORDER_DETAILS,PROD)` | 1 | `ORDER_TOTAL` |
| 3 | DATASET | powerbi | `Product Perfromance Measures`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Product_Perfromance_Measures,PROD)` | 0 | `ORDER_TOTAL` |
| 3 | DATASET | powerbi | `Time Inteligence Measures`<br>`urn:li:dataset:(urn:li:dataPlatform:powerbi,b2fd91.datahub_order_entries.Time_Inteligence_Measures,PROD)` | 0 | `ORDER_TOTAL` |
| 2 | DATASET | snowflake | `ORDER_DETAILS`<br>`urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_details,PROD)` | 3 | `order_total` |
| 3 | DATASET | snowflake | `ORDER_DETAILS_REPLICA`<br>`urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_details_replica,PROD)` | 0 | `order_total` |
| 3 | DATASET | snowflake | `ORDER_HISTORY`<br>`urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.analytics.order_history,PROD)` | 0 | `order_total` |
| 3 | DATASET | tableau | `Custom SQL Query`<br>`urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.37fcfb15-34ae-973a-5ae3-cf63691d48e3,PROD)` | 0 | `AVERAGE_ORDER_VALUE`, `TOTAL_REVENUE` |
| 3 | DATASET | tableau | `Custom SQL Query`<br>`urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.8bfe7483-1c9a-a0e1-ec84-57207dd37a15,PROD)` | 0 | `AVERAGE_ORDER_VALUE`, `TOTAL_REVENUE` |
| 4 | DATASET | tableau | `Promotions`<br>`urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.b980a8c5-28eb-119e-f6ca-4da32732e5be,PROD)` | 1 | `AVERAGE_ORDER_VALUE`, `TOTAL_REVENUE` |
| 4 | DATASET | tableau | `Order Mode`<br>`urn:li:dataset:(urn:li:dataPlatform:tableau,b2fd91.c067553a-127e-a871-14a0-5f32cb032c78,PROD)` | 1 | `AVERAGE_ORDER_VALUE`, `TOTAL_REVENUE` |

## Required actions

- [ ] **hold-deployment** — Do not merge or deploy until required migration work is verified.
- [ ] **migrate-dependents** — Update 17 discovered downstream assets or prove that they do not reference the changed field.
- [ ] **notify-owners** — Route the migration decision to all discovered asset owners.
- [ ] **route-domain-fallbacks** — Route ownerless impacted assets through their assigned domains.
- [ ] **resolve-ownership** — Assign accountable owners before approving the schema change.
- [ ] **run-source-validation** — Run the read-only population check and attach its result.

## Owner routing

- `urn:li:corpGroup:b2fd91.1e0398a3-113f-475e-b6fc-32ab72a634d2` — 2 assets
- `urn:li:corpGroup:b2fd91.ORG_BACKEND_ENG` — 1 asset
- `urn:li:corpGroup:b2fd91.ORG_DATA_PLATFORM` — 3 assets
- `urn:li:corpuser:b2fd91.EMP006` — 3 assets
- `urn:li:corpuser:b2fd91.alex@example.com` — 1 asset
- `urn:li:corpuser:b2fd91.brock1@example.com` — 4 assets
- `urn:li:corpuser:b2fd91.bryan@example.com` — 1 asset
- `urn:li:corpuser:b2fd91.jonny1@example.com` — 2 assets
- `urn:li:corpuser:b2fd91.jonny2@example.com` — 1 asset
- `urn:li:corpuser:b2fd91.kirk@example.com` — 2 assets
- `urn:li:corpuser:b2fd91.marty@example.com` — 2 assets
- `urn:li:corpuser:b2fd91.sam@example.com` — 1 asset

## Domain fallback routing

- `urn:li:domain:b2fd91.d4f24004-fb54-4e3c-8dea-2b7e209230b0` — 1 ownerless asset

## Validation SQL

### source-field-population

Measure populated source rows before changing the field.

```sql
SELECT COUNT(*) AS populated_rows
FROM order_entry_db.order_entry.orders
WHERE order_total IS NOT NULL
```


## Reason codes

- `BREAKING_CHANGE_HAS_DOWNSTREAM_IMPACT`
- `DOWNSTREAM_OWNERSHIP_GAPS`

## Warnings

- 10 impacted assets have no owner metadata.
