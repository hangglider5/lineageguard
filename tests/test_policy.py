import unittest

from lineageguard.artifacts import render_markdown, validate_artifact
from lineageguard.models import (
    AssetImpact,
    ChangeKind,
    ImpactSnapshot,
    SchemaChange,
    SchemaFieldEvidence,
    TargetSelector,
    Verdict,
)
from lineageguard.policy import decide


def make_change(kind: ChangeKind = ChangeKind.DROP_COLUMN) -> SchemaChange:
    values = {
        "scenario_id": "drop-orders-order-total",
        "target": TargetSelector(
            query="/q orders",
            platform="dbt",
            name="orders",
            env="PROD",
            relation="order_entry_db.order_entry.orders",
        ),
        "kind": kind,
        "field_path": "order_total",
    }
    if kind == ChangeKind.ADD_COLUMN:
        values["after_type"] = "NUMBER"
    else:
        values["before_type"] = "NUMBER"
    return SchemaChange.model_validate(values)


def make_snapshot(*, complete: bool = True, field_present: bool = True) -> ImpactSnapshot:
    return ImpactSnapshot(
        source=AssetImpact(
            urn="urn:li:dataset:(urn:li:dataPlatform:dbt,orders,PROD)",
            entity_type="DATASET",
            name="orders",
            platform="dbt",
            degree=0,
            owner_urns=["urn:li:corpuser:source-owner"],
        ),
        field=(
            SchemaFieldEvidence(field_path="order_total", native_type="NUMBER")
            if field_present
            else None
        ),
        downstream_total=2,
        downstream=[
            AssetImpact(
                urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,details,PROD)",
                entity_type="DATASET",
                name="order_details",
                platform="snowflake",
                degree=1,
                owner_urns=["urn:li:corpuser:data-owner"],
            ),
            AssetImpact(
                urn="urn:li:dashboard:(looker,orders)",
                entity_type="DASHBOARD",
                name="Orders",
                platform="looker",
                degree=2,
            ),
        ],
        lineage_complete=complete,
    )


class DecisionPolicyTests(unittest.TestCase):
    def test_breaking_change_with_downstream_is_blocked(self) -> None:
        change = make_change()
        snapshot = make_snapshot()

        artifact = decide(change, snapshot)

        self.assertEqual(artifact.verdict, Verdict.BLOCK)
        self.assertEqual(artifact.evidence.direct_downstream, 1)
        self.assertEqual(artifact.evidence.transitive_downstream, 1)
        self.assertIn("BREAKING_CHANGE_HAS_DOWNSTREAM_IMPACT", artifact.reason_codes)
        self.assertIn("DOWNSTREAM_OWNERSHIP_GAPS", artifact.reason_codes)
        self.assertEqual(validate_artifact(artifact, change, snapshot), [])

    def test_add_column_is_allowed_when_lineage_is_complete(self) -> None:
        artifact = decide(
            make_change(ChangeKind.ADD_COLUMN), make_snapshot(field_present=False)
        )

        self.assertEqual(artifact.verdict, Verdict.ALLOW)
        self.assertEqual(artifact.validation_queries, [])

    def test_add_column_blocks_when_field_already_exists(self) -> None:
        artifact = decide(make_change(ChangeKind.ADD_COLUMN), make_snapshot())

        self.assertEqual(artifact.verdict, Verdict.BLOCK)
        self.assertIn("SOURCE_FIELD_ALREADY_EXISTS", artifact.reason_codes)

    def test_breaking_change_blocks_when_declared_type_does_not_match(self) -> None:
        change = make_change()
        change.before_type = "VARCHAR"

        artifact = decide(change, make_snapshot())

        self.assertEqual(artifact.verdict, Verdict.BLOCK)
        self.assertIn("SOURCE_TYPE_MISMATCH", artifact.reason_codes)

    def test_incomplete_lineage_fails_closed(self) -> None:
        artifact = decide(make_change(), make_snapshot(complete=False))

        self.assertEqual(artifact.verdict, Verdict.BLOCK)
        self.assertIn("LINEAGE_INCOMPLETE", artifact.reason_codes)

    def test_ownerless_asset_routes_through_its_domain(self) -> None:
        snapshot = make_snapshot()
        snapshot.downstream[1].domain_urns = ["urn:li:domain:commerce"]

        artifact = decide(make_change(), snapshot)

        self.assertEqual(len(artifact.domain_routes), 1)
        self.assertEqual(
            artifact.domain_routes[0].asset_urns,
            ["urn:li:dashboard:(looker,orders)"],
        )
        self.assertIn(
            "route_domains", [action.kind for action in artifact.required_actions]
        )
        notify_action = next(
            action
            for action in artifact.required_actions
            if action.kind == "notify_owners"
        )
        self.assertNotIn(
            "urn:li:dashboard:(looker,orders)", notify_action.asset_urns
        )
        self.assertEqual(validate_artifact(artifact, make_change(), snapshot), [])

    def test_missing_source_field_fails_closed(self) -> None:
        artifact = decide(make_change(), make_snapshot(field_present=False))

        self.assertEqual(artifact.verdict, Verdict.BLOCK)
        self.assertIn("SOURCE_FIELD_NOT_FOUND", artifact.reason_codes)
        self.assertEqual(artifact.validation_queries, [])
        self.assertNotIn(
            "run_validation", [action.kind for action in artifact.required_actions]
        )

    def test_validator_rejects_unsupported_action_asset(self) -> None:
        change = make_change()
        snapshot = make_snapshot()
        artifact = decide(change, snapshot)
        artifact.required_actions[0].asset_urns.append("urn:li:dataset:unsupported")

        errors = validate_artifact(artifact, change, snapshot)

        self.assertTrue(any("unsupported assets" in error for error in errors))

    def test_markdown_contains_review_sections_and_read_only_sql(self) -> None:
        artifact = decide(make_change(), make_snapshot())

        markdown = render_markdown(artifact)

        self.assertIn("## Evidence", markdown)
        self.assertIn("## Impacted assets", markdown)
        self.assertIn("## Required actions", markdown)
        self.assertIn("## Owner routing", markdown)
        self.assertIn("## Domain fallback routing", markdown)
        self.assertIn("SELECT COUNT(*)", markdown)
        self.assertNotIn("DROP TABLE", markdown)


if __name__ == "__main__":
    unittest.main()
