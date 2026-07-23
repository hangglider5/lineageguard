"""Deterministic compatibility and impact policy for LineageGuard."""

from __future__ import annotations

from collections import defaultdict

from .models import (
    ActionItem,
    ChangeKind,
    DecisionArtifact,
    DecisionEvidence,
    DomainRoute,
    ImpactSnapshot,
    OwnerRoute,
    SchemaChange,
    Severity,
    ValidationQuery,
    Verdict,
)


BREAKING_CHANGES = {
    ChangeKind.DROP_COLUMN,
    ChangeKind.RENAME_COLUMN,
    ChangeKind.TYPE_CHANGE,
}


def _owner_routes(snapshot: ImpactSnapshot) -> list[OwnerRoute]:
    routed_assets: dict[str, set[str]] = defaultdict(set)
    for asset in snapshot.downstream:
        for owner_urn in asset.owner_urns:
            routed_assets[owner_urn].add(asset.urn)
    return [
        OwnerRoute(owner_urn=owner, asset_urns=sorted(asset_urns))
        for owner, asset_urns in sorted(routed_assets.items())
    ]


def _domain_routes(snapshot: ImpactSnapshot) -> list[DomainRoute]:
    """Route ownerless assets through their directly assigned domains."""

    routed_assets: dict[str, set[str]] = defaultdict(set)
    for asset in snapshot.downstream:
        if not asset.owner_urns:
            for domain_urn in asset.domain_urns:
                routed_assets[domain_urn].add(asset.urn)
    return [
        DomainRoute(domain_urn=domain, asset_urns=sorted(asset_urns))
        for domain, asset_urns in sorted(routed_assets.items())
    ]


def _validation_queries(
    change: SchemaChange, snapshot: ImpactSnapshot
) -> list[ValidationQuery]:
    if change.kind not in BREAKING_CHANGES or snapshot.field is None:
        return []
    return [
        ValidationQuery(
            query_id="source-field-population",
            purpose="Measure populated source rows before changing the field.",
            sql=(
                "SELECT COUNT(*) AS populated_rows\n"
                f"FROM {change.target.relation}\n"
                f"WHERE {change.field_path} IS NOT NULL"
            ),
        )
    ]


def decide(change: SchemaChange, snapshot: ImpactSnapshot) -> DecisionArtifact:
    """Create a decision using only supplied, attributable graph evidence."""

    breaking = change.kind in BREAKING_CHANGES
    field_verified = snapshot.field is not None
    expected_type = change.before_type.casefold() if change.before_type else None
    observed_type = (
        snapshot.field.native_type.casefold()
        if snapshot.field and snapshot.field.native_type
        else None
    )
    missing_owner_assets = sorted(
        asset.urn for asset in snapshot.downstream if not asset.owner_urns
    )
    reasons: list[str] = []
    warnings = list(snapshot.warnings)

    if change.kind == ChangeKind.ADD_COLUMN and field_verified:
        verdict = Verdict.BLOCK
        severity = Severity.CRITICAL
        reasons.append("SOURCE_FIELD_ALREADY_EXISTS")
    elif breaking and not field_verified:
        verdict = Verdict.BLOCK
        severity = Severity.CRITICAL
        reasons.append("SOURCE_FIELD_NOT_FOUND")
    elif breaking and expected_type and observed_type != expected_type:
        verdict = Verdict.BLOCK
        severity = Severity.CRITICAL
        reasons.append("SOURCE_TYPE_MISMATCH")
    elif not snapshot.lineage_complete:
        verdict = Verdict.BLOCK
        severity = Severity.CRITICAL
        reasons.append("LINEAGE_INCOMPLETE")
    elif breaking and snapshot.downstream_total > 0:
        verdict = Verdict.BLOCK
        severity = Severity.HIGH
        reasons.append("BREAKING_CHANGE_HAS_DOWNSTREAM_IMPACT")
    elif breaking:
        verdict = Verdict.REVIEW
        severity = Severity.MEDIUM
        reasons.append("BREAKING_CHANGE_WITH_NO_KNOWN_DOWNSTREAM")
    else:
        verdict = Verdict.ALLOW
        severity = Severity.LOW
        reasons.append("BACKWARD_COMPATIBLE_ADDITION")

    if missing_owner_assets:
        reasons.append("DOWNSTREAM_OWNERSHIP_GAPS")
        warnings.append(
            f"{len(missing_owner_assets)} impacted assets have no owner metadata."
        )

    direct_count = sum(asset.degree == 1 for asset in snapshot.downstream)
    transitive_count = sum(asset.degree > 1 for asset in snapshot.downstream)
    owner_routes = _owner_routes(snapshot)
    domain_routes = _domain_routes(snapshot)
    impacted_urns = sorted(asset.urn for asset in snapshot.downstream)
    validation_queries = _validation_queries(change, snapshot)
    actions: list[ActionItem] = []

    if verdict == Verdict.BLOCK:
        actions.append(
            ActionItem(
                action_id="hold-deployment",
                kind="hold_deployment",
                description="Do not merge or deploy until required migration work is verified.",
                asset_urns=[snapshot.source.urn],
            )
        )
    if impacted_urns:
        actions.append(
            ActionItem(
                action_id="migrate-dependents",
                kind="migrate_dependents",
                description=(
                    f"Update {len(impacted_urns)} discovered downstream assets or prove "
                    "that they do not reference the changed field."
                ),
                asset_urns=impacted_urns,
            )
        )
    if owner_routes:
        owned_asset_urns = sorted(
            {asset for route in owner_routes for asset in route.asset_urns}
        )
        actions.append(
            ActionItem(
                action_id="notify-owners",
                kind="notify_owners",
                description="Route the migration decision to all discovered asset owners.",
                asset_urns=owned_asset_urns,
                owner_urns=[route.owner_urn for route in owner_routes],
            )
        )
    if domain_routes:
        domain_asset_urns = sorted(
            {asset for route in domain_routes for asset in route.asset_urns}
        )
        actions.append(
            ActionItem(
                action_id="route-domain-fallbacks",
                kind="route_domains",
                description=(
                    "Route ownerless impacted assets through their assigned domains."
                ),
                asset_urns=domain_asset_urns,
                domain_urns=[route.domain_urn for route in domain_routes],
            )
        )
    if missing_owner_assets:
        actions.append(
            ActionItem(
                action_id="resolve-ownership",
                kind="resolve_ownership",
                description="Assign accountable owners before approving the schema change.",
                asset_urns=missing_owner_assets,
            )
        )
    if validation_queries:
        actions.append(
            ActionItem(
                action_id="run-source-validation",
                kind="run_validation",
                description="Run the read-only population check and attach its result.",
                asset_urns=[snapshot.source.urn],
            )
        )

    summary = (
        f"{verdict.value.upper()} {change.kind.value} of {change.field_path}: "
        f"{snapshot.downstream_total} downstream assets reported, "
        f"{len(snapshot.downstream)} evaluated."
    )
    return DecisionArtifact(
        decision_id=f"lineageguard:{change.scenario_id}",
        scenario_id=change.scenario_id,
        verdict=verdict,
        severity=severity,
        summary=summary,
        source=snapshot.source,
        source_field=snapshot.field,
        field_path=change.field_path,
        change_kind=change.kind,
        evidence=DecisionEvidence(
            source_field_verified=field_verified,
            downstream_total=snapshot.downstream_total,
            evaluated_downstream=len(snapshot.downstream),
            direct_downstream=direct_count,
            transitive_downstream=transitive_count,
            lineage_complete=snapshot.lineage_complete,
        ),
        impacted_assets=sorted(snapshot.downstream, key=lambda asset: asset.urn),
        owner_routes=owner_routes,
        domain_routes=domain_routes,
        reason_codes=reasons,
        required_actions=actions,
        validation_queries=validation_queries,
        warnings=warnings,
    )
