import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from lineageguard.models import DecisionArtifact
from lineageguard.planner import (
    MigrationProposal,
    PlannerContext,
    PlannerStep,
    build_planner_context,
    planner_context_json,
    sha256_text,
    validate_migration_proposal,
)


REPOSITORY_ROOT = Path(__file__).parents[1]


def load_artifact() -> DecisionArtifact:
    return DecisionArtifact.model_validate_json(
        (
            REPOSITORY_ROOT / "examples/drop-orders-order-total/decision.json"
        ).read_text("utf-8")
    )


def valid_action(platform: str | None) -> str:
    if platform in {"looker", "powerbi", "tableau"}:
        return "update_semantic_model"
    if platform in {"dbt", "snowflake"}:
        return "update_transformation"
    return "verify_consumer"


def make_valid_proposal(context: PlannerContext) -> MigrationProposal:
    return MigrationProposal(
        schema_version="1.0",
        scenario_id=context.scenario_id,
        decision_id=context.decision_id,
        executive_summary="Stage downstream migrations before the protected field changes.",
        ordered_steps=[
            PlannerStep(
                step_id=f"migrate-{index}",
                sequence=index,
                asset_urn=asset.asset_urn,
                action_kind=valid_action(asset.platform),
                impacted_columns=asset.impacted_columns,
                owner_urns=asset.owner_urns,
                depends_on=[],
                rationale="This consumer uses a field derived from the proposed change.",
                success_criteria="The consumer is updated and its existing checks pass.",
            )
            for index, asset in enumerate(context.assets, start=1)
        ],
        open_questions=["Which deployment window is approved for downstream migrations?"],
    )


class PlannerContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact = load_artifact()
        self.context = build_planner_context(self.artifact)

    def test_context_contains_only_bounded_grounding_fields(self) -> None:
        payload = self.context.model_dump(mode="json")

        self.assertEqual(len(payload["assets"]), 17)
        self.assertEqual(payload["immutable_verdict"], "block")
        self.assertNotIn("summary", payload)
        self.assertNotIn("description", payload["assets"][0])
        self.assertNotIn("name", payload["assets"][0])
        self.assertTrue(
            all(len(asset["allowed_action_kinds"]) == 1 for asset in payload["assets"])
        )
        powerbi_asset = next(
            asset for asset in payload["assets"] if asset["platform"] == "powerbi"
        )
        self.assertEqual(
            powerbi_asset["allowed_action_kinds"],
            ["update_semantic_model"],
        )
        serialized = planner_context_json(self.context)
        self.assertEqual(serialized, planner_context_json(self.context))
        self.assertEqual(len(sha256_text(serialized)), 64)

    def test_valid_grounded_proposal_is_accepted(self) -> None:
        proposal = make_valid_proposal(self.context)

        self.assertEqual(validate_migration_proposal(proposal, self.context), [])

    def test_extra_verdict_field_is_rejected_by_schema(self) -> None:
        payload = make_valid_proposal(self.context).model_dump(mode="json")
        payload["verdict"] = "allow"

        with self.assertRaises(ValidationError):
            MigrationProposal.model_validate(payload)

    def test_unsupported_asset_and_missing_asset_are_rejected(self) -> None:
        proposal = make_valid_proposal(self.context)
        proposal.ordered_steps[0].asset_urn = "urn:li:dataset:invented"

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(any("omitted assets" in error for error in errors))
        self.assertTrue(any("unsupported assets" in error for error in errors))

    def test_changed_columns_and_owners_are_rejected(self) -> None:
        proposal = make_valid_proposal(self.context)
        proposal.ordered_steps[0].impacted_columns = ["invented_column"]
        proposal.ordered_steps[0].owner_urns = ["urn:li:corpuser:invented"]

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(any("impacted-column evidence" in error for error in errors))
        self.assertTrue(any("owner evidence" in error for error in errors))

    def test_incompatible_platform_action_is_rejected(self) -> None:
        proposal = make_valid_proposal(self.context)
        looker_step = next(
            step
            for step in proposal.ordered_steps
            if "dataPlatform:looker" in step.asset_urn
        )
        looker_step.action_kind = "update_transformation"

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(any("incompatible with platform looker" in error for error in errors))

    def test_powerbi_dataset_cannot_be_misclassified_as_dashboard(self) -> None:
        proposal = make_valid_proposal(self.context)
        powerbi_step = next(
            step
            for step in proposal.ordered_steps
            if "dataPlatform:powerbi" in step.asset_urn
        )
        powerbi_step.action_kind = "update_dashboard"

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(
            any("incompatible with platform powerbi" in error for error in errors)
        )

    def test_forward_or_unknown_dependency_is_rejected(self) -> None:
        proposal = make_valid_proposal(self.context)
        proposal.ordered_steps[0].depends_on = [proposal.ordered_steps[1].step_id]
        proposal.ordered_steps[1].depends_on = ["missing-step"]

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(any("only on earlier steps" in error for error in errors))
        self.assertTrue(any("unknown step" in error for error in errors))

    def test_step_order_and_exact_evidence_order_are_enforced(self) -> None:
        proposal = make_valid_proposal(self.context)
        proposal.ordered_steps[0], proposal.ordered_steps[1] = (
            proposal.ordered_steps[1],
            proposal.ordered_steps[0],
        )
        evidence_step = next(
            step
            for step in proposal.ordered_steps
            if len(step.impacted_columns) > 1
        )
        evidence_step.impacted_columns = list(reversed(evidence_step.impacted_columns))

        errors = validate_migration_proposal(proposal, self.context)

        self.assertTrue(any("must be ordered" in error for error in errors))
        self.assertTrue(any("impacted-column evidence" in error for error in errors))

    def test_markup_links_multiline_and_free_text_urns_are_rejected(self) -> None:
        proposal = make_valid_proposal(self.context)
        proposal.executive_summary = "<script>alert(1)</script>"
        proposal.ordered_steps[0].rationale = "See [runbook](https://example.com)."
        proposal.ordered_steps[1].success_criteria = "first line\nsecond line"
        proposal.open_questions = ["Check urn:li:dataset:invented?"]

        errors = validate_migration_proposal(proposal, self.context)

        self.assertGreaterEqual(len(errors), 4)

    def test_context_rejects_more_than_twenty_five_assets(self) -> None:
        payload = self.context.model_dump(mode="json")
        payload["assets"] = payload["assets"] + [payload["assets"][0]] * 9

        with self.assertRaises(ValidationError):
            PlannerContext.model_validate(payload)

    def test_contract_json_schema_forbids_extra_properties(self) -> None:
        schema = MigrationProposal.model_json_schema()

        self.assertFalse(schema["additionalProperties"])
        self.assertIn("ordered_steps", schema["required"])
        self.assertEqual(schema["properties"]["open_questions"]["maxItems"], 3)
        json.dumps(schema)


if __name__ == "__main__":
    unittest.main()
