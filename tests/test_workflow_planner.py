import tempfile
import unittest
from pathlib import Path

from pydantic import SecretStr

from lineageguard.llm_client import (
    PlannerProvider,
    PlannerSettings,
    PlannerTransportResponse,
)
from lineageguard.models import DecisionArtifact
from lineageguard.planner import (
    MigrationProposal,
    PlannerStatus,
    build_planner_context,
    run_model_planner,
)
from lineageguard.workflow import WorkflowResult, run_workflow, write_outputs


REPOSITORY_ROOT = Path(__file__).parents[1]


def load_artifact() -> DecisionArtifact:
    return DecisionArtifact.model_validate_json(
        (
            REPOSITORY_ROOT / "examples/drop-orders-order-total/decision.json"
        ).read_text("utf-8")
    )


def proposal_for(artifact: DecisionArtifact) -> MigrationProposal:
    context = build_planner_context(artifact)
    steps = []
    for index, asset in enumerate(context.assets, start=1):
        action = (
            "update_semantic_model"
            if asset.platform in {"looker", "powerbi", "tableau"}
            else "update_transformation"
        )
        steps.append(
            {
                "step_id": f"migrate-{index}",
                "sequence": index,
                "asset_urn": asset.asset_urn,
                "action_kind": action,
                "impacted_columns": asset.impacted_columns,
                "owner_urns": asset.owner_urns,
                "depends_on": [],
                "rationale": "Update the grounded consumer before the source change.",
                "success_criteria": "The consumer is migrated and verified.",
            }
        )
    return MigrationProposal(
        schema_version="1.0",
        scenario_id=context.scenario_id,
        decision_id=context.decision_id,
        executive_summary="Migrate all grounded consumers before changing the source field.",
        ordered_steps=steps,
        open_questions=[],
    )


class OneResponseTransport:
    def __init__(self, content: str) -> None:
        self.content = content

    async def complete_json(self, settings, messages, json_schema):
        return PlannerTransportResponse(
            content=self.content,
            request_id="workflow-test",
            finish_reason="stop",
            input_tokens=100,
            output_tokens=200,
            latency_ms=15,
            actual_provider="deepseek",
        )


class PlannerWorkflowOutputTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.artifact = load_artifact()
        self.settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("not-written"),
            model="deepseek-v4-flash",
            max_attempts=1,
        )

    async def test_accepted_plan_writes_sidecars_and_composite_checklist(self) -> None:
        proposal = proposal_for(self.artifact)
        outcome = await run_model_planner(
            self.artifact,
            self.settings,
            transport=OneResponseTransport(proposal.model_dump_json()),
        )
        result = WorkflowResult(
            artifact=self.artifact,
            validation_errors=[],
            planner=outcome,
        )

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            write_outputs(result, output_dir)

            plan = output_dir / "migration-plan.json"
            receipt = output_dir / "planner-receipt.json"
            checklist = output_dir / "migration-checklist.md"
            self.assertTrue(plan.exists())
            self.assertTrue(receipt.exists())
            checklist_text = checklist.read_text("utf-8")
            self.assertIn("Model-assisted migration plan", checklist_text)
            self.assertIn("Proposed execution prerequisites", checklist_text)
            self.assertIn("deepseek-v4-flash", receipt.read_text("utf-8"))
            self.assertNotIn("not-written", receipt.read_text("utf-8"))

    async def test_rejected_plan_writes_receipt_but_not_plan(self) -> None:
        proposal = proposal_for(self.artifact)
        proposal.ordered_steps[0].asset_urn = "urn:li:dataset:invented"
        outcome = await run_model_planner(
            self.artifact,
            self.settings,
            transport=OneResponseTransport(proposal.model_dump_json()),
        )
        self.assertEqual(outcome.receipt.status, PlannerStatus.REJECTED)
        result = WorkflowResult(
            artifact=self.artifact,
            validation_errors=[],
            planner=outcome,
        )

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            write_outputs(result, output_dir)

            self.assertFalse((output_dir / "migration-plan.json").exists())
            self.assertTrue((output_dir / "planner-receipt.json").exists())
            self.assertNotIn(
                "Model-assisted migration plan",
                (output_dir / "migration-checklist.md").read_text("utf-8"),
            )

    async def test_require_planner_without_settings_fails_before_mcp(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires planner_settings"):
            await run_workflow(  # type: ignore[arg-type]
                None,
                require_planner=True,
            )


if __name__ == "__main__":
    unittest.main()
