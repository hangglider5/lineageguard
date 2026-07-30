import json
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
from lineageguard.planner import MigrationProposal, build_planner_context
from lineageguard.planner_rehearsal import run_rehearsal, write_rehearsal_outputs


REPOSITORY_ROOT = Path(__file__).parents[1]


def load_artifact() -> DecisionArtifact:
    return DecisionArtifact.model_validate_json(
        (
            REPOSITORY_ROOT / "examples/drop-orders-order-total/decision.json"
        ).read_text("utf-8")
    )


def valid_plan(artifact: DecisionArtifact) -> MigrationProposal:
    context = build_planner_context(artifact)
    return MigrationProposal(
        schema_version="1.0",
        scenario_id=context.scenario_id,
        decision_id=context.decision_id,
        executive_summary="Migrate all grounded consumers before the source change.",
        ordered_steps=[
            {
                "step_id": f"step-{index}",
                "sequence": index,
                "asset_urn": asset.asset_urn,
                "action_kind": (
                    "update_semantic_model"
                    if asset.platform in {"looker", "powerbi", "tableau"}
                    else "update_transformation"
                ),
                "impacted_columns": asset.impacted_columns,
                "owner_urns": asset.owner_urns,
                "depends_on": [],
                "rationale": "This grounded consumer depends on the changed field.",
                "success_criteria": "The consumer is migrated and verified.",
            }
            for index, asset in enumerate(context.assets, start=1)
        ],
        open_questions=[],
    )


class RepeatingTransport:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def complete_json(self, settings, messages, json_schema):
        self.calls += 1
        return PlannerTransportResponse(
            content=self.content,
            request_id=f"request-{self.calls}",
            finish_reason="stop",
            input_tokens=20,
            output_tokens=10,
            latency_ms=5,
            actual_provider="deepseek",
        )


class PlannerRehearsalTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_grounded_runs_produce_redacted_report_and_plans(self) -> None:
        artifact = load_artifact()
        plan = valid_plan(artifact)
        transport = RepeatingTransport(plan.model_dump_json())
        settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("not-in-report"),
            model="deepseek-v4-flash",
            max_attempts=1,
        )

        report, outcomes = await run_rehearsal(
            artifact, settings, runs=3, transport=transport
        )

        self.assertTrue(report.all_accepted)
        self.assertEqual(report.accepted_runs, 3)
        self.assertEqual(report.grounded_asset_count, 17)
        self.assertEqual(transport.calls, 3)
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            write_rehearsal_outputs(report, outcomes, output_dir)
            report_text = (output_dir / "report.json").read_text("utf-8")
            self.assertNotIn("not-in-report", report_text)
            self.assertTrue((output_dir / "run-3-plan.json").exists())
            json.loads(report_text)

    async def test_run_count_is_bounded(self) -> None:
        artifact = load_artifact()
        settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("secret"),
            model="deepseek-v4-flash",
        )

        with self.assertRaisesRegex(ValueError, "between 1 and 5"):
            await run_rehearsal(artifact, settings, runs=6)


if __name__ == "__main__":
    unittest.main()
