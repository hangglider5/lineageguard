import json
import unittest
from pathlib import Path

from pydantic import SecretStr

from lineageguard.llm_client import (
    PlannerProvider,
    PlannerSettings,
    PlannerTransportError,
    PlannerTransportResponse,
)
from lineageguard.models import DecisionArtifact
from lineageguard.planner import (
    MigrationProposal,
    PlannerStatus,
    build_planner_context,
    run_model_planner,
)


REPOSITORY_ROOT = Path(__file__).parents[1]


def load_artifact() -> DecisionArtifact:
    return DecisionArtifact.model_validate_json(
        (
            REPOSITORY_ROOT / "examples/drop-orders-order-total/decision.json"
        ).read_text("utf-8")
    )


def valid_proposal(artifact: DecisionArtifact) -> MigrationProposal:
    context = build_planner_context(artifact)
    steps = []
    for index, asset in enumerate(context.assets, start=1):
        if asset.platform in {"looker", "powerbi", "tableau"}:
            action = "update_semantic_model"
        elif asset.platform in {"dbt", "snowflake"}:
            action = "update_transformation"
        else:
            action = "verify_consumer"
        steps.append(
            {
                "step_id": f"migrate-{index}",
                "sequence": index,
                "asset_urn": asset.asset_urn,
                "action_kind": action,
                "impacted_columns": asset.impacted_columns,
                "owner_urns": asset.owner_urns,
                "depends_on": [],
                "rationale": "This consumer depends on the changed field.",
                "success_criteria": "The consumer is updated and verified.",
            }
        )
    return MigrationProposal(
        schema_version="1.0",
        scenario_id=context.scenario_id,
        decision_id=context.decision_id,
        executive_summary="Migrate every grounded downstream consumer before release.",
        ordered_steps=steps,
        open_questions=[],
    )


class FakeTransport:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = []

    async def complete_json(self, settings, messages, json_schema):
        self.calls.append((settings, messages, json_schema))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def response(content: str, *, tokens: int = 10) -> PlannerTransportResponse:
    return PlannerTransportResponse(
        content=content,
        request_id="request-1",
        finish_reason="stop",
        input_tokens=tokens,
        output_tokens=tokens,
        latency_ms=12.5,
        actual_provider="deepseek",
    )


class PlannerRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.artifact = load_artifact()
        self.settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("never-log-this-key"),
            model="deepseek-v4-flash",
        )

    async def test_valid_response_is_accepted_with_hash_only_receipt(self) -> None:
        proposal = valid_proposal(self.artifact)
        transport = FakeTransport([response(proposal.model_dump_json())])

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.ACCEPTED)
        self.assertEqual(outcome.proposal, proposal)
        self.assertEqual(outcome.receipt.attempts, 1)
        self.assertEqual(outcome.receipt.input_tokens, 10)
        self.assertEqual(len(outcome.receipt.response_sha256 or ""), 64)
        receipt_json = outcome.receipt.model_dump_json()
        self.assertNotIn("never-log-this-key", receipt_json)
        self.assertNotIn(proposal.executive_summary, receipt_json)

    async def test_format_failure_retries_once_then_accepts(self) -> None:
        proposal = valid_proposal(self.artifact)
        transport = FakeTransport(
            [response("not-json", tokens=3), response(proposal.model_dump_json(), tokens=5)]
        )

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.ACCEPTED)
        self.assertEqual(outcome.receipt.attempts, 2)
        self.assertEqual(outcome.receipt.input_tokens, 8)
        self.assertEqual(len(transport.calls), 2)

    async def test_semantic_violation_is_rejected_without_retry(self) -> None:
        proposal = valid_proposal(self.artifact)
        proposal.ordered_steps[0].asset_urn = "urn:li:dataset:invented"
        transport = FakeTransport([response(proposal.model_dump_json())])

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.REJECTED)
        self.assertIsNone(outcome.proposal)
        self.assertEqual(len(transport.calls), 1)
        self.assertTrue(
            any("unsupported assets" in error for error in outcome.receipt.validation_errors)
        )

    async def test_retryable_transport_failure_has_bounded_attempts(self) -> None:
        transport = FakeTransport(
            [
                PlannerTransportError("temporary failure", retryable=True),
                PlannerTransportError("still unavailable", retryable=True),
            ]
        )

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.UNAVAILABLE)
        self.assertEqual(outcome.receipt.attempts, 2)
        self.assertEqual(outcome.receipt.fallback_reason, "still unavailable")

    async def test_nonretryable_auth_failure_stops_immediately(self) -> None:
        transport = FakeTransport(
            [PlannerTransportError("planner request returned HTTP 401", retryable=False)]
        )

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.UNAVAILABLE)
        self.assertEqual(outcome.receipt.attempts, 1)
        self.assertEqual(len(transport.calls), 1)

    async def test_more_than_twenty_five_assets_skips_transport(self) -> None:
        original = list(self.artifact.impacted_assets)
        for index in range(9):
            duplicate = original[0].model_copy(deep=True)
            duplicate.urn = f"urn:li:dataset:extra-{index}"
            self.artifact.impacted_assets.append(duplicate)
        transport = FakeTransport([])

        outcome = await run_model_planner(
            self.artifact, self.settings, transport=transport
        )

        self.assertEqual(outcome.receipt.status, PlannerStatus.UNAVAILABLE)
        self.assertEqual(outcome.receipt.attempts, 0)
        self.assertIn("25-asset", outcome.receipt.fallback_reason or "")
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
