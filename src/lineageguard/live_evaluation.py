"""Read-only live DataHub gate for the fixed LineageGuard scenario."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable, Literal, Sequence

from pydantic import Field

from .mcp_probe import DEFAULT_GMS_URL, default_server_command
from .models import SchemaChange, Severity, StrictModel, Verdict
from .workflow import WorkflowResult, run_workflow


class LiveExpectation(StrictModel):
    verdict: Verdict
    severity: Severity
    downstream_total: int = Field(ge=0)
    evaluated_downstream: int = Field(ge=0)
    lineage_complete: bool
    validation_error_count: int = Field(ge=0)
    owner_route_count: int = Field(ge=0)
    domain_route_count: int = Field(ge=0)


class LiveEvaluationSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    scenario_path: str = Field(pattern=r"^[A-Za-z0-9_./-]+$")
    max_assets: int = Field(default=100, ge=1)
    expected: LiveExpectation


class LiveActual(StrictModel):
    decision_id: str
    source_urn: str
    verdict: Verdict
    severity: Severity
    downstream_total: int
    evaluated_downstream: int
    lineage_complete: bool
    validation_error_count: int
    owner_route_count: int
    domain_route_count: int


class LiveEvaluationReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    evaluation_id: str
    execution_scope: Literal["live_datahub_read_only"] = "live_datahub_read_only"
    passed: bool
    checks: dict[str, bool]
    end_to_end_latency_ms: float = Field(ge=0)
    actual: LiveActual


WorkflowRunner = Callable[..., Awaitable[WorkflowResult]]


def _safe_path(repository_root: Path, relative_path: str) -> Path:
    resolved = (repository_root / relative_path).resolve()
    if resolved != repository_root and repository_root not in resolved.parents:
        raise ValueError(f"live evaluation path escapes repository: {relative_path}")
    return resolved


async def run_live_evaluation(
    spec: LiveEvaluationSpec,
    repository_root: Path,
    *,
    gms_url: str = DEFAULT_GMS_URL,
    server_command: str | None = None,
    workflow_runner: WorkflowRunner = run_workflow,
) -> LiveEvaluationReport:
    scenario_path = _safe_path(repository_root, spec.scenario_path)
    change = SchemaChange.model_validate_json(scenario_path.read_text("utf-8"))
    started = time.perf_counter()
    result = await workflow_runner(
        change,
        gms_url=gms_url,
        server_command=server_command or default_server_command(),
        max_assets=spec.max_assets,
        write_back=False,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    artifact = result.artifact
    actual = LiveActual(
        decision_id=artifact.decision_id,
        source_urn=artifact.source.urn,
        verdict=artifact.verdict,
        severity=artifact.severity,
        downstream_total=artifact.evidence.downstream_total,
        evaluated_downstream=artifact.evidence.evaluated_downstream,
        lineage_complete=artifact.evidence.lineage_complete,
        validation_error_count=len(result.validation_errors),
        owner_route_count=len(artifact.owner_routes),
        domain_route_count=len(artifact.domain_routes),
    )
    expected = spec.expected
    checks = {
        "verdict": actual.verdict == expected.verdict,
        "severity": actual.severity == expected.severity,
        "downstream_total": actual.downstream_total == expected.downstream_total,
        "evaluated_downstream": (
            actual.evaluated_downstream == expected.evaluated_downstream
        ),
        "lineage_complete": actual.lineage_complete == expected.lineage_complete,
        "artifact_valid": (
            actual.validation_error_count == expected.validation_error_count
        ),
        "owner_routes": actual.owner_route_count == expected.owner_route_count,
        "domain_routes": actual.domain_route_count == expected.domain_route_count,
        "source_resolved": actual.source_urn.startswith("urn:li:dataset:"),
    }
    return LiveEvaluationReport(
        evaluation_id=spec.evaluation_id,
        passed=all(checks.values()),
        checks=checks,
        end_to_end_latency_ms=elapsed_ms,
        actual=actual,
    )


def render_live_markdown(report: LiveEvaluationReport) -> str:
    state = "PASS" if report.passed else "FAIL"
    lines = [
        f"# LineageGuard live evaluation: {report.evaluation_id}",
        "",
        f"**Result:** {state}",
        "**Execution scope:** live DataHub MCP read-only workflow",
        f"**End-to-end latency:** {report.end_to_end_latency_ms:.3f} ms",
        "",
        "## Actual result",
        "",
        f"- Decision: `{report.actual.decision_id}`",
        f"- Source: `{report.actual.source_urn}`",
        f"- Verdict/severity: `{report.actual.verdict.value}/"
        f"{report.actual.severity.value}`",
        f"- Downstream reported/evaluated: "
        f"`{report.actual.downstream_total}/{report.actual.evaluated_downstream}`",
        f"- Lineage complete: `{report.actual.lineage_complete}`",
        f"- Artifact validation errors: `{report.actual.validation_error_count}`",
        f"- Owner routes: `{report.actual.owner_route_count}`",
        f"- Domain fallback routes: `{report.actual.domain_route_count}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- [{'x' if passed else ' '}] `{name}`"
        for name, passed in report.checks.items()
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the read-only fixed scenario against live DataHub MCP."
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--gms-url", default=DEFAULT_GMS_URL)
    parser.add_argument("--server-command", default=default_server_command())
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        spec_path = args.spec.resolve()
        spec = LiveEvaluationSpec.model_validate_json(spec_path.read_text("utf-8"))
        report = asyncio.run(
            run_live_evaluation(
                spec,
                spec_path.parent.parent,
                gms_url=args.gms_url,
                server_command=args.server_command,
            )
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2) + "\n", "utf-8")
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(
                render_live_markdown(report), encoding="utf-8"
            )
    except Exception as exc:
        print(f"LineageGuard live evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "evaluation_id": report.evaluation_id,
                "passed": report.passed,
                "end_to_end_latency_ms": report.end_to_end_latency_ms,
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
