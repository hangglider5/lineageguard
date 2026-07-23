"""Render and validate reviewable LineageGuard action artifacts."""

from __future__ import annotations

import re

from .models import DecisionArtifact, ImpactSnapshot, SchemaChange, Verdict
from .policy import BREAKING_CHANGES, decide


FORBIDDEN_SQL = re.compile(
    r"\b(ALTER|CREATE|DELETE|DROP|GRANT|INSERT|MERGE|REVOKE|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)


def validate_artifact(
    artifact: DecisionArtifact,
    change: SchemaChange,
    snapshot: ImpactSnapshot,
) -> list[str]:
    """Return deterministic validation errors; an empty list means valid."""

    errors: list[str] = []
    if artifact != decide(change, snapshot):
        errors.append("artifact differs from the deterministic policy output")
    evidence_urns = {asset.urn for asset in snapshot.downstream}
    artifact_urns = {asset.urn for asset in artifact.impacted_assets}

    if artifact.scenario_id != change.scenario_id:
        errors.append("scenario_id does not match the requested change")
    if artifact.source != snapshot.source:
        errors.append("source context does not match the graph snapshot")
    if artifact.source_field != snapshot.field:
        errors.append("source field context does not match the schema evidence")
    if artifact.field_path != change.field_path:
        errors.append("field_path does not match the requested change")
    if artifact.change_kind != change.kind:
        errors.append("change_kind does not match the requested change")
    if artifact.evidence.downstream_total != snapshot.downstream_total:
        errors.append("downstream_total does not match graph evidence")
    if artifact.evidence.evaluated_downstream != len(snapshot.downstream):
        errors.append("evaluated_downstream does not match graph evidence")
    if artifact.evidence.source_field_verified != (snapshot.field is not None):
        errors.append("source_field_verified does not match schema evidence")
    if artifact.evidence.direct_downstream != sum(
        asset.degree == 1 for asset in snapshot.downstream
    ):
        errors.append("direct_downstream does not match graph evidence")
    if artifact.evidence.transitive_downstream != sum(
        asset.degree > 1 for asset in snapshot.downstream
    ):
        errors.append("transitive_downstream does not match graph evidence")
    if artifact.evidence.lineage_complete != snapshot.lineage_complete:
        errors.append("lineage_complete does not match graph evidence")
    if artifact_urns != evidence_urns:
        errors.append("impacted_assets differ from the retrieved lineage evidence")
    if not snapshot.lineage_complete and artifact.verdict != Verdict.BLOCK:
        errors.append("incomplete lineage must block the change")
    if (
        change.kind in BREAKING_CHANGES
        and snapshot.downstream_total > 0
        and artifact.verdict != Verdict.BLOCK
    ):
        errors.append("a breaking change with downstream impact must be blocked")

    allowed_action_urns = evidence_urns | {snapshot.source.urn}
    for action in artifact.required_actions:
        unsupported = set(action.asset_urns) - allowed_action_urns
        if unsupported:
            errors.append(
                f"action {action.action_id} cites unsupported assets: "
                + ", ".join(sorted(unsupported))
            )

    owner_assets: dict[str, set[str]] = {}
    for asset in snapshot.downstream:
        for owner in asset.owner_urns:
            owner_assets.setdefault(owner, set()).add(asset.urn)
    for route in artifact.owner_routes:
        if route.owner_urn not in owner_assets:
            errors.append(f"owner route is unsupported: {route.owner_urn}")
        unsupported = set(route.asset_urns) - owner_assets.get(route.owner_urn, set())
        if unsupported:
            errors.append(
                f"owner route cites assets not owned by that route: "
                f"{', '.join(sorted(unsupported))}"
            )

    domain_assets: dict[str, set[str]] = {}
    for asset in snapshot.downstream:
        if not asset.owner_urns:
            for domain in asset.domain_urns:
                domain_assets.setdefault(domain, set()).add(asset.urn)
    for route in artifact.domain_routes:
        if route.domain_urn not in domain_assets:
            errors.append(f"domain route is unsupported: {route.domain_urn}")
        unsupported = set(route.asset_urns) - domain_assets.get(
            route.domain_urn, set()
        )
        if unsupported:
            errors.append(
                "domain route cites ownerless assets outside that domain: "
                f"{', '.join(sorted(unsupported))}"
            )

    supported_owners = set(owner_assets)
    supported_domains = set(domain_assets)
    for action in artifact.required_actions:
        unsupported_owners = set(action.owner_urns) - supported_owners
        if unsupported_owners:
            errors.append(
                f"action {action.action_id} cites unsupported owners: "
                + ", ".join(sorted(unsupported_owners))
            )
        unsupported_domains = set(action.domain_urns) - supported_domains
        if unsupported_domains:
            errors.append(
                f"action {action.action_id} cites unsupported domains: "
                + ", ".join(sorted(unsupported_domains))
            )

    for query in artifact.validation_queries:
        normalized = query.sql.strip()
        if not normalized.upper().startswith("SELECT "):
            errors.append(f"validation query {query.query_id} is not read-only SELECT")
        if FORBIDDEN_SQL.search(normalized):
            errors.append(f"validation query {query.query_id} contains mutation SQL")
        if change.field_path.lower() not in normalized.lower():
            errors.append(f"validation query {query.query_id} omits the changed field")
        if change.target.relation.lower() not in normalized.lower():
            errors.append(f"validation query {query.query_id} omits the target relation")

    return errors


def render_markdown(artifact: DecisionArtifact) -> str:
    """Render a stable human-reviewable migration decision."""

    def asset_count(count: int, *, ownerless: bool = False) -> str:
        qualifier = "ownerless " if ownerless else ""
        noun = "asset" if count == 1 else "assets"
        return f"{count} {qualifier}{noun}"

    lines = [
        f"# LineageGuard decision: {artifact.scenario_id}",
        "",
        f"**Verdict:** {artifact.verdict.value.upper()}",
        f"**Severity:** {artifact.severity.value.upper()}",
        "",
        artifact.summary,
        "",
        "## Evidence",
        "",
        f"- Source: `{artifact.source.urn}`",
        f"- Changed field: `{artifact.field_path}`",
        f"- Observed type: "
        f"`{artifact.source_field.native_type if artifact.source_field else 'not found'}`",
        f"- Source owners: `{len(artifact.source.owner_urns)}`",
        f"- Source domains/tags/terms: "
        f"`{len(artifact.source.domain_urns)}/{len(artifact.source.tag_urns)}/"
        f"{len(artifact.source.term_urns)}`",
        "- Field tags/terms: `"
        + (
            ", ".join(
                artifact.source_field.tag_names + artifact.source_field.term_names
            )
            if artifact.source_field
            else "none"
        )
        + "`",
        f"- Field verified: `{artifact.evidence.source_field_verified}`",
        f"- Downstream reported/evaluated: "
        f"`{artifact.evidence.downstream_total}/{artifact.evidence.evaluated_downstream}`",
        f"- Direct/transitive: "
        f"`{artifact.evidence.direct_downstream}/{artifact.evidence.transitive_downstream}`",
        f"- Complete lineage page set: `{artifact.evidence.lineage_complete}`",
        "",
        "## Impacted assets",
        "",
        "| Hop | Type | Platform | Asset | Owners | Impacted columns |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    if artifact.impacted_assets:
        for asset in artifact.impacted_assets:
            columns = ", ".join(f"`{column}`" for column in asset.impacted_columns)
            lines.append(
                f"| {asset.degree} | {asset.entity_type} | {asset.platform or '-'} | "
                f"`{asset.name}`<br>`{asset.urn}` | {len(asset.owner_urns)} | "
                f"{columns or '-'} |"
            )
    else:
        lines.append("| - | - | - | No downstream assets | 0 | - |")

    lines.extend(
        [
            "",
            "## Required actions",
            "",
        ]
    )
    for action in artifact.required_actions:
        lines.append(f"- [ ] **{action.action_id}** — {action.description}")

    lines.extend(["", "## Owner routing", ""])
    if artifact.owner_routes:
        lines.extend(
            f"- `{route.owner_urn}` — {asset_count(len(route.asset_urns))}"
            for route in artifact.owner_routes
        )
    else:
        lines.append("- No owners were present in the retrieved evidence.")

    lines.extend(["", "## Domain fallback routing", ""])
    if artifact.domain_routes:
        lines.extend(
            f"- `{route.domain_urn}` — "
            f"{asset_count(len(route.asset_urns), ownerless=True)}"
            for route in artifact.domain_routes
        )
    else:
        lines.append("- No ownerless assets had an assigned domain fallback.")

    lines.extend(["", "## Validation SQL", ""])
    if artifact.validation_queries:
        for query in artifact.validation_queries:
            lines.extend(
                [
                    f"### {query.query_id}",
                    "",
                    query.purpose,
                    "",
                    "```sql",
                    query.sql,
                    "```",
                    "",
                ]
            )
    else:
        lines.append("No pre-deployment SQL check is required for this change type.")

    lines.extend(["", "## Reason codes", ""])
    lines.extend(f"- `{code}`" for code in artifact.reason_codes)
    if artifact.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in artifact.warnings)
    return "\n".join(lines).rstrip() + "\n"
