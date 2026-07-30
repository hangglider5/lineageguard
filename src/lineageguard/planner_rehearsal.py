"""Opt-in live model rehearsal against a committed deterministic decision."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from pydantic import Field

from .llm_client import PlannerSettings, PlannerTransport
from .models import DecisionArtifact, StrictModel
from .planner import PlannerOutcome, PlannerReceipt, PlannerStatus, run_model_planner


class PlannerRehearsalReport(StrictModel):
    schema_version: str = "1.0"
    provider: str
    model: str
    total_runs: int = Field(ge=1, le=5)
    accepted_runs: int = Field(ge=0, le=5)
    grounded_asset_count: int = Field(ge=0, le=25)
    all_accepted: bool
    receipts: list[PlannerReceipt]


async def run_rehearsal(
    artifact: DecisionArtifact,
    settings: PlannerSettings,
    *,
    runs: int,
    transport: PlannerTransport | None = None,
) -> tuple[PlannerRehearsalReport, list[PlannerOutcome]]:
    if not 1 <= runs <= 5:
        raise ValueError("runs must be between 1 and 5")
    outcomes = [
        await run_model_planner(artifact, settings, transport=transport)
        for _ in range(runs)
    ]
    accepted = sum(
        outcome.receipt.status == PlannerStatus.ACCEPTED for outcome in outcomes
    )
    report = PlannerRehearsalReport(
        provider=settings.provider.value,
        model=settings.model,
        total_runs=runs,
        accepted_runs=accepted,
        grounded_asset_count=len(artifact.impacted_assets),
        all_accepted=accepted == runs,
        receipts=[outcome.receipt for outcome in outcomes],
    )
    return report, outcomes


def write_rehearsal_outputs(
    report: PlannerRehearsalReport,
    outcomes: list[PlannerOutcome],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    for index, outcome in enumerate(outcomes, start=1):
        (output_dir / f"run-{index}-receipt.json").write_text(
            outcome.receipt.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        plan_path = output_dir / f"run-{index}-plan.json"
        if outcome.proposal is not None:
            plan_path.write_text(
                outcome.proposal.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
        elif plan_path.exists():
            plan_path.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run 1-5 real model planner checks without starting DataHub."
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.env_file.exists():
            load_dotenv(args.env_file, override=False)
        settings = PlannerSettings.from_environment(os.environ)
        artifact = DecisionArtifact.model_validate_json(
            args.artifact.read_text("utf-8")
        )
        report, outcomes = asyncio.run(
            run_rehearsal(artifact, settings, runs=args.runs)
        )
        write_rehearsal_outputs(report, outcomes, args.output_dir)
    except Exception as exc:
        print(f"LineageGuard planner rehearsal failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "provider": report.provider,
                "model": report.model,
                "accepted_runs": report.accepted_runs,
                "total_runs": report.total_runs,
                "grounded_asset_count": report.grounded_asset_count,
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 0 if report.all_accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
