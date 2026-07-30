# LineageGuard proposal review

Reviewed on 2026-07-22 against the official rules, current DataHub `1.6.0`
documentation, and a live local Quickstart. Updated through 2026-07-30 after the
end-to-end scenario, authentication rehearsal, demo UI, and submission draft.

## Verdict

**Proceed with LineageGuard**, narrowed to one dbt breaking-change scenario.

The concept fits the primary challenge better than the retained alternatives
because the showcase graph already provides the required cross-platform lineage,
owners, domains, glossary terms, schemas, and documents. The MCP server supports
both multi-hop lineage reads and first-class Decision document write-back. The
first vertical slice can therefore prove the complete competition loop without a
warehouse or a second metadata system.

The differentiator must be the validated action artifact, not lineage discovery.
DataHub already performs impact analysis. LineageGuard should turn a proposed
code change into an auditable decision with exact impacted assets, accountable
owners, validation checks, and explicit unsupported/unknown claims.

## First vertical slice

Input:

- a deterministic dbt manifest/schema diff that removes or changes one column on
  the showcase `orders` model.

Context reads:

- dataset and column schema;
- 3+ hop downstream column lineage;
- ownership, domains, glossary terms, and tags.

Decision and artifact:

- classify the change as safe, risky, or blocked;
- identify directly and transitively impacted datasets using fine-grained column
  lineage; use dataset-level lineage separately when broader dashboard/chart
  context is needed;
- produce a JSON decision plus a Markdown migration checklist and validation SQL;
- fail closed when metadata is missing or the artifact does not validate.

Write-back:

- save a DataHub `Decision` document linked to the changed and materially
  impacted assets;
- add dedicated structured properties only after their definitions and update
  semantics are tested.

## Live evidence

The 2026-07-22 interface probe established:

- Quickstart `1.6.0` is healthy on Apple Silicon.
- The showcase datapack loaded 67 datasets with table and column lineage.
- Official MCP server `0.6.0` advertised 20 tools with mutation tools enabled.
- Searching for `orders` returned cross-platform candidates plus owner, domain,
  tag, glossary, and platform facets.
- The selected dbt asset had 5 upstream and 36 downstream assets; the first page
  returned 20 downstream assets spanning datasets, dashboards, and charts.
- `save_document` created a Decision and `get_entities` verified the exact URN.

See `examples/interface-probe.json` for machine-readable evidence.

The 2026-07-23 vertical slice additionally established:

- the `order_total` field exists on the dbt source with native type `FLOAT` and
  the `Order Total` glossary term;
- column-level lineage narrows the 36 dataset-level downstream assets to 17
  attributable column consumers (1 direct, 16 transitive);
- deterministic validation accepted the generated decision with zero errors and
  found 10 impacted assets without owner metadata;
- one Decision document was related to the source plus 17 impacted datasets, read
  back by URN, and found through the source asset's `relatedDocuments` edge;
- an explicit document URN updates the same Decision on retry.

The fixed evaluation v1 adds 16 cases and 130 checks. All pass offline, including
exact owner/domain routing and domain-misroute rejection, while a
separate read-only live gate revalidated 17/17 downstream assets with zero
artifact errors and recorded MCP workflow latency independently from local policy
latency.

## Highest risks

### P0 — Required interface deployment is easy to misread

DataHub Core `1.6.0` GMS returned 404 at `/mcp`. The detailed official MCP guide
requires the standalone `mcp-server-datahub` process for DataHub Core, even though
the Agent Context Kit overview shows a self-hosted GMS `/mcp` URL. The repository
must package and pin the MCP sidecar; a demo cannot assume Quickstart exposes it.

Mitigation: pin `mcp-server-datahub==0.6.0`, test the actual stdio protocol, and
add an HTTP wrapper only if the hosted demo requires it.

### P0 — Authentication transport works, but authorization is not yet scoped

The first fresh-Quickstart attempt showed that frontend credentials alone were
not enough while Metadata Service Authentication was disabled. A later rehearsal
enabled it, confirmed an unauthenticated GraphQL request returned `401`, issued a
one-hour PAT, and completed MCP read, write-back, Document read-back, and source
relationship read-back through the SDK's actual `DATAHUB_GMS_TOKEN` variable.

That PAT belonged to the local administrator, so it does not prove least-privilege
authorization. Before any public demo, provision a dedicated principal limited to
graph reads plus Document write-back, verify its policies, and remove default
credentials. Keep the reproducible CLI error as hackathon feedback or an upstream
issue.

### P0 — A public working project must survive through judging

The rules require a testable URL, demo, or test build available without charge or
restriction through the end of judging. A local Docker setup alone is weak because
judges may not install a 13 GB stack and may judge only the narrative/video.

Mitigation: keep local setup reproducible, but plan a lightweight public demo with
precomputed evidence and a live scoped DataHub backend before submission freeze.

### P2 — Local disk headroom must remain monitored

Disk headroom recovered from roughly 4 GB on Jul 22 to roughly 37 GB on Jul 23.
The official guide asks for 13 GB free before installation, so the current machine
is above the requirement, but Docker growth can still regress it.

Mitigation: avoid a second DataHub version, monitor Docker disk use, and perform
the fresh-machine rehearsal on a volume with at least 20 GB free.

### P1 — Raw lineage exceeds a safe agent context budget

One 3+ hop response exceeded 100,000 characters while only 20 of 36 downstream
assets were returned. Passing raw metadata to an LLM would be slow, costly, and
likely truncate important evidence.

Mitigation: request a bounded window, page deterministically when token truncation
occurs, retain URN/type/degree/owner/domain first, and require `total` to equal the
deduplicated retrieved count before calling lineage complete.

The MCP server's current `hasMore` value is derived from the fetched window and
can be false even when `total` is larger. LineageGuard therefore does not trust
`hasMore` as its completeness proof.

The bounded planner does not receive this raw response. It runs only after the
deterministic artifact is validated and receives at most 25 compact asset facts:
URN, platform, hop, impacted columns, owners, domains, and immutable policy
results. Descriptions and Document text remain outside model context. Model output
is advisory, strictly typed, independently grounded, and omitted from write-back
when validation fails.

### P1 — `max_hops=3` means the `3+` bucket

The MCP implementation treats three or more hops as `1`, `2`, and `3+`; it is not
an exact three-hop cutoff. Impact claims must not imply a precise depth bound.

Mitigation: label it `3+ hop transitive impact` and add exact path verification
for assets cited in remediation actions.

### P1 — Datapack and server schemas are not perfectly aligned

The loader filtered 247 derived aspects, including lineage and usage feature
summaries, as incompatible with Core `1.6.0`. Core `upstreamLineage`,
`fineGrainedLineages`, schemas, ownership, and domains loaded successfully.

Mitigation: depend only on aspects verified in the target Core version and make
missing metadata an evaluation scenario, not an implicit success.

### P1 — Originality can collapse into existing impact analysis

DataHub already exposes impact analysis and community dbt impact actions. A UI
that simply renders downstream lineage will score poorly on originality.

Mitigation: demonstrate code-diff understanding, deterministic compatibility
rules, validated remediation files, unsupported-claim detection, owner-aware
routing, and graph write-back as one transaction-like workflow.

### P1 — Mutation safety and idempotency need explicit design

MCP mutation tools are opt-in, but a retry can still create duplicate documents
or overwrite editable metadata.

Mitigation: require the explicit `--write-back` flag, use a stable decision ID,
allow retries to target `--document-urn`, and verify both the document URN and its
relationship from the source asset after every write.

## Rule corrections to the original plan

- The repository needs an Apache-2.0 license visible from the start.
- The public project/test build must remain available through the judging period,
  not merely at the submission deadline.
- The three-minute video is an upper bound; judges are not required to watch past
  it or run the project.
- DataHub usage, technical execution, originality, usefulness, and submission
  quality are equally weighted. Bonus upstream contributions should not displace
  the end-to-end vertical slice.
