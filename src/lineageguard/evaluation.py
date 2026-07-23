"""Deterministic offline evaluation harness for LineageGuard."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal, Sequence

from pydantic import Field, model_validator

from .artifacts import validate_artifact
from .models import (
    ImpactSnapshot,
    SchemaChange,
    Severity,
    StrictModel,
    Verdict,
)
from .policy import decide
from .workflow import WriteBackReceipt


TamperKind = Literal[
    "unsupported_action_asset",
    "misroute_owner",
    "misroute_domain",
    "mutation_sql",
    "wrong_verdict",
]


class DecisionExpectation(StrictModel):
    verdict: Verdict
    severity: Severity
    reason_codes: list[str]
    impacted_asset_urns: list[str]
    direct_downstream: int = Field(ge=0)
    transitive_downstream: int = Field(ge=0)
    evaluated_downstream: int = Field(ge=0)
    lineage_complete: bool
    action_kinds: list[str]
    owner_routes: dict[str, list[str]] = Field(default_factory=dict)
    domain_routes: dict[str, list[str]] = Field(default_factory=dict)


class DecisionCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: str
    kind: Literal["decision"]
    change: str
    snapshot: str
    expected: DecisionExpectation


class AdversarialCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: str
    kind: Literal["artifact_validation"]
    change: str
    snapshot: str
    tamper: TamperKind
    expected_error_substrings: list[str] = Field(min_length=1)


class ReceiptCase(StrictModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    category: str
    kind: Literal["write_back_receipt"]
    receipt_path: str = Field(pattern=r"^[A-Za-z0-9_./-]+$")
    minimum_related_assets: int = Field(ge=1)


EvalCase = Annotated[
    DecisionCase | AdversarialCase | ReceiptCase,
    Field(discriminator="kind"),
]


class EvaluationSuite(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    suite_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    changes: dict[str, SchemaChange]
    snapshots: dict[str, ImpactSnapshot]
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "EvaluationSuite":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation case IDs must be unique")
        for case in self.cases:
            if isinstance(case, (DecisionCase, AdversarialCase)):
                if case.change not in self.changes:
                    raise ValueError(
                        f"case {case.case_id} references unknown change {case.change}"
                    )
                if case.snapshot not in self.snapshots:
                    raise ValueError(
                        f"case {case.case_id} references unknown snapshot {case.snapshot}"
                    )
        return self


class MetricScore(StrictModel):
    passed: int = Field(ge=0)
    total: int = Field(ge=0)
    rate: float = Field(ge=0, le=1)


class LatencySummary(StrictModel):
    p50: float = Field(ge=0)
    p95: float = Field(ge=0)
    maximum: float = Field(ge=0)


class EvaluationCaseResult(StrictModel):
    case_id: str
    category: str
    kind: str
    passed: bool
    checks: dict[str, bool]
    details: list[str] = Field(default_factory=list)
    latency_ms: float = Field(ge=0)


class EvaluationReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    suite_id: str
    execution_scope: Literal["offline_policy_and_artifact_validation"] = (
        "offline_policy_and_artifact_validation"
    )
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    total_checks: int = Field(ge=0)
    passed_checks: int = Field(ge=0)
    metrics: dict[str, MetricScore]
    offline_latency_ms: LatencySummary
    cases: list[EvaluationCaseResult]


def _apply_tamper(artifact: object, tamper: TamperKind) -> None:
    # The evaluator intentionally mutates a generated Pydantic artifact to prove
    # that the independent validator rejects unsupported claims and unsafe output.
    from .models import DecisionArtifact

    if not isinstance(artifact, DecisionArtifact):
        raise TypeError("tamper target must be a DecisionArtifact")
    if tamper == "unsupported_action_asset":
        if not artifact.required_actions:
            raise ValueError("tamper requires at least one action")
        artifact.required_actions[0].asset_urns.append(
            "urn:li:dataset:(urn:li:dataPlatform:test,unsupported,PROD)"
        )
    elif tamper == "misroute_owner":
        if not artifact.owner_routes:
            raise ValueError("tamper requires at least one owner route")
        route = artifact.owner_routes[0]
        unsupported = next(
            (
                asset.urn
                for asset in artifact.impacted_assets
                if route.owner_urn not in asset.owner_urns
            ),
            None,
        )
        if unsupported is None:
            raise ValueError("tamper requires an asset outside the first owner route")
        route.asset_urns = [unsupported]
    elif tamper == "misroute_domain":
        if not artifact.domain_routes:
            raise ValueError("tamper requires at least one domain route")
        route = artifact.domain_routes[0]
        unsupported = next(
            (
                asset.urn
                for asset in artifact.impacted_assets
                if asset.urn not in route.asset_urns
            ),
            None,
        )
        if unsupported is None:
            raise ValueError("tamper requires an asset outside the first domain route")
        route.asset_urns = [unsupported]
    elif tamper == "mutation_sql":
        if not artifact.validation_queries:
            raise ValueError("tamper requires a validation query")
        artifact.validation_queries[0].sql = "DROP TABLE orders"
    elif tamper == "wrong_verdict":
        artifact.verdict = Verdict.ALLOW
    else:  # pragma: no cover - Literal plus strict suite validation makes this unreachable.
        raise ValueError(f"unsupported tamper: {tamper}")


def _safe_repository_path(repository_root: Path, relative_path: str) -> Path:
    resolved = (repository_root / relative_path).resolve()
    if resolved != repository_root and repository_root not in resolved.parents:
        raise ValueError(f"evaluation path escapes repository: {relative_path}")
    return resolved


def _latency_summary(latencies: list[float]) -> LatencySummary:
    ordered = sorted(latencies)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return LatencySummary(
        p50=round(statistics.median(ordered), 3),
        p95=round(ordered[p95_index], 3),
        maximum=round(ordered[-1], 3),
    )


def run_suite(suite: EvaluationSuite, repository_root: Path) -> EvaluationReport:
    metric_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    results: list[EvaluationCaseResult] = []

    def record_metric(name: str, passed: bool) -> None:
        metric_counts[name][1] += 1
        metric_counts[name][0] += int(passed)

    for case in suite.cases:
        started = time.perf_counter()
        checks: dict[str, bool] = {}
        details: list[str] = []
        try:
            if isinstance(case, DecisionCase):
                change = suite.changes[case.change]
                snapshot = suite.snapshots[case.snapshot]
                artifact = decide(change, snapshot)
                repeated = decide(change, snapshot)
                validation_errors = validate_artifact(artifact, change, snapshot)
                expected = case.expected
                checks = {
                    "artifact_valid": validation_errors == [],
                    "deterministic": artifact == repeated,
                    "verdict": artifact.verdict == expected.verdict,
                    "severity": artifact.severity == expected.severity,
                    "reason_codes": artifact.reason_codes == expected.reason_codes,
                    "impacted_assets": sorted(
                        asset.urn for asset in artifact.impacted_assets
                    )
                    == sorted(expected.impacted_asset_urns),
                    "impact_counts": (
                        artifact.evidence.direct_downstream
                        == expected.direct_downstream
                        and artifact.evidence.transitive_downstream
                        == expected.transitive_downstream
                        and artifact.evidence.evaluated_downstream
                        == expected.evaluated_downstream
                    ),
                    "lineage_complete": (
                        artifact.evidence.lineage_complete
                        == expected.lineage_complete
                    ),
                    "action_kinds": [
                        action.kind for action in artifact.required_actions
                    ]
                    == expected.action_kinds,
                    "owner_routes": {
                        route.owner_urn: sorted(route.asset_urns)
                        for route in artifact.owner_routes
                    }
                    == {
                        owner: sorted(asset_urns)
                        for owner, asset_urns in expected.owner_routes.items()
                    },
                    "domain_routes": {
                        route.domain_urn: sorted(route.asset_urns)
                        for route in artifact.domain_routes
                    }
                    == {
                        domain: sorted(asset_urns)
                        for domain, asset_urns in expected.domain_routes.items()
                    },
                }
                details.extend(validation_errors)
                record_metric("artifact_validity", checks["artifact_valid"])
                record_metric("determinism", checks["deterministic"])
                record_metric(
                    "verdict_accuracy", checks["verdict"] and checks["severity"]
                )
                record_metric(
                    "impacted_asset_accuracy",
                    checks["impacted_assets"] and checks["impact_counts"],
                )
                record_metric(
                    "policy_detail_accuracy",
                    checks["reason_codes"]
                    and checks["lineage_complete"]
                    and checks["action_kinds"]
                    and checks["owner_routes"]
                    and checks["domain_routes"],
                )
            elif isinstance(case, AdversarialCase):
                change = suite.changes[case.change]
                snapshot = suite.snapshots[case.snapshot]
                artifact = decide(change, snapshot)
                baseline_errors = validate_artifact(artifact, change, snapshot)
                _apply_tamper(artifact, case.tamper)
                validation_errors = validate_artifact(artifact, change, snapshot)
                checks = {
                    "baseline_valid": baseline_errors == [],
                    "artifact_rejected": bool(validation_errors),
                    "expected_errors": all(
                        any(fragment in error for error in validation_errors)
                        for fragment in case.expected_error_substrings
                    ),
                }
                details.extend(validation_errors)
                guardrail_passed = all(checks.values())
                metric = (
                    "unsupported_claim_prevention"
                    if case.tamper
                    in {
                        "unsupported_action_asset",
                        "misroute_owner",
                        "misroute_domain",
                    }
                    else "artifact_guardrail_rejection"
                )
                record_metric(metric, guardrail_passed)
            elif isinstance(case, ReceiptCase):
                receipt_path = _safe_repository_path(
                    repository_root, case.receipt_path
                )
                receipt = WriteBackReceipt.model_validate_json(
                    receipt_path.read_text("utf-8")
                )
                checks = {
                    "write_succeeded": receipt.success,
                    "document_read_back": receipt.document_read_back_verified,
                    "source_relationship": receipt.source_relationship_verified,
                    "document_urn": receipt.document_urn.startswith(
                        "urn:li:document:"
                    ),
                    "related_assets": (
                        receipt.related_assets_requested
                        >= case.minimum_related_assets
                    ),
                }
                record_metric("write_back_evidence", all(checks.values()))
            else:  # pragma: no cover - discriminated union prevents this.
                raise TypeError(f"unknown evaluation case: {case}")
        except Exception as exc:
            checks = {"execution": False}
            details.append(f"{type(exc).__name__}: {exc}")

        passed = all(checks.values())
        record_metric("task_completion", passed)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        results.append(
            EvaluationCaseResult(
                case_id=case.case_id,
                category=case.category,
                kind=case.kind,
                passed=passed,
                checks=checks,
                details=details,
                latency_ms=elapsed_ms,
            )
        )

    total_checks = sum(len(result.checks) for result in results)
    passed_checks = sum(sum(result.checks.values()) for result in results)
    metrics = {
        name: MetricScore(
            passed=counts[0],
            total=counts[1],
            rate=round(counts[0] / counts[1], 4) if counts[1] else 0,
        )
        for name, counts in sorted(metric_counts.items())
    }
    passed_cases = sum(result.passed for result in results)
    return EvaluationReport(
        suite_id=suite.suite_id,
        total_cases=len(results),
        passed_cases=passed_cases,
        pass_rate=round(passed_cases / len(results), 4),
        total_checks=total_checks,
        passed_checks=passed_checks,
        metrics=metrics,
        offline_latency_ms=_latency_summary(
            [result.latency_ms for result in results]
        ),
        cases=results,
    )


def render_report_markdown(report: EvaluationReport) -> str:
    lines = [
        f"# LineageGuard evaluation: {report.suite_id}",
        "",
        f"**Cases:** {report.passed_cases}/{report.total_cases} passed "
        f"({report.pass_rate:.1%})",
        f"**Checks:** {report.passed_checks}/{report.total_checks} passed",
        "**Execution scope:** offline policy and artifact validation "
        "(excludes MCP/network latency)",
        f"**Offline latency:** p50 {report.offline_latency_ms.p50:.3f} ms, "
        f"p95 {report.offline_latency_ms.p95:.3f} ms, "
        f"max {report.offline_latency_ms.maximum:.3f} ms",
        "",
        "## Metrics",
        "",
        "| Metric | Passed | Rate |",
        "| --- | ---: | ---: |",
    ]
    for name, score in report.metrics.items():
        lines.append(
            f"| `{name}` | {score.passed}/{score.total} | {score.rate:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Category | Kind | Result | Latency |",
            "| --- | --- | --- | --- | ---: |",
        ]
    )
    for result in report.cases:
        state = "PASS" if result.passed else "FAIL"
        lines.append(
            f"| `{result.case_id}` | {result.category} | {result.kind} | "
            f"**{state}** | {result.latency_ms:.3f} ms |"
        )
    failures = [result for result in report.cases if not result.passed]
    if failures:
        lines.extend(["", "## Failures", ""])
        for result in failures:
            lines.append(f"- `{result.case_id}`: {'; '.join(result.details)}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed offline LineageGuard evaluation suite."
    )
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        suite_path = args.suite.resolve()
        suite = EvaluationSuite.model_validate_json(suite_path.read_text("utf-8"))
        report = run_suite(suite, suite_path.parent.parent)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2) + "\n", "utf-8")
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(
                render_report_markdown(report), encoding="utf-8"
            )
    except Exception as exc:
        print(f"LineageGuard evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "suite_id": report.suite_id,
                "passed_cases": report.passed_cases,
                "total_cases": report.total_cases,
                "pass_rate": report.pass_rate,
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report.passed_cases == report.total_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
