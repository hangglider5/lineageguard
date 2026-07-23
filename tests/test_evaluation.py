import unittest
from pathlib import Path

from lineageguard.evaluation import (
    DecisionCase,
    EvaluationSuite,
    render_report_markdown,
    run_suite,
)
from lineageguard.live_evaluation import (
    LiveEvaluationSpec,
    render_live_markdown,
    run_live_evaluation,
)
from lineageguard.models import DecisionArtifact, Verdict
from lineageguard.workflow import WorkflowResult


REPOSITORY_ROOT = Path(__file__).parents[1]


class EvaluationTests(unittest.TestCase):
    def load_suite(self) -> EvaluationSuite:
        return EvaluationSuite.model_validate_json(
            (REPOSITORY_ROOT / "evals/suite.json").read_text("utf-8")
        )

    def test_fixed_suite_passes_all_cases_and_metrics(self) -> None:
        report = run_suite(self.load_suite(), REPOSITORY_ROOT)

        self.assertEqual(report.total_cases, 16)
        self.assertEqual(report.passed_cases, 16)
        self.assertEqual(report.passed_checks, report.total_checks)
        self.assertEqual(report.metrics["verdict_accuracy"].rate, 1.0)
        self.assertEqual(report.metrics["write_back_evidence"].rate, 1.0)

    def test_changed_expectation_fails_the_relevant_case(self) -> None:
        suite = self.load_suite().model_copy(deep=True)
        first_case = suite.cases[0]
        self.assertIsInstance(first_case, DecisionCase)
        first_case.expected.verdict = Verdict.BLOCK

        report = run_suite(suite, REPOSITORY_ROOT)

        self.assertEqual(report.passed_cases, 15)
        self.assertFalse(report.cases[0].checks["verdict"])

    def test_markdown_labels_latency_as_offline(self) -> None:
        markdown = render_report_markdown(
            run_suite(self.load_suite(), REPOSITORY_ROOT)
        )

        self.assertIn("excludes MCP/network latency", markdown)
        self.assertIn("16/16 passed", markdown)


class LiveEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_gate_scores_a_workflow_result(self) -> None:
        spec = LiveEvaluationSpec.model_validate_json(
            (REPOSITORY_ROOT / "evals/live.json").read_text("utf-8")
        )
        artifact = DecisionArtifact.model_validate_json(
            (
                REPOSITORY_ROOT
                / "examples/drop-orders-order-total/decision.json"
            ).read_text("utf-8")
        )

        async def fake_runner(*args, **kwargs) -> WorkflowResult:
            self.assertFalse(kwargs["write_back"])
            return WorkflowResult(artifact=artifact, validation_errors=[])

        report = await run_live_evaluation(
            spec,
            REPOSITORY_ROOT,
            workflow_runner=fake_runner,
        )

        self.assertTrue(report.passed)
        self.assertEqual(report.actual.downstream_total, 17)
        self.assertIn("live DataHub MCP", render_live_markdown(report))


if __name__ == "__main__":
    unittest.main()
