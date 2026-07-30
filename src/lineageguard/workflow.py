"""End-to-end LineageGuard command: graph read, decision, artifact, write-back."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from ipaddress import ip_address
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from .artifacts import render_markdown, validate_artifact
from .datahub_mcp import call_payload, collect_snapshot
from .llm_client import PlannerSettings, PlannerTransport
from .mcp_probe import DEFAULT_GMS_URL, default_server_command
from .models import DecisionArtifact, SchemaChange
from .planner import PlannerOutcome, PlannerStatus, run_model_planner
from .policy import decide
from .subprocess_env import mcp_child_environment


class WriteBackReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    document_urn: str
    document_read_back_verified: bool
    source_relationship_verified: bool
    related_assets_requested: int


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: DecisionArtifact
    validation_errors: list[str]
    planner: PlannerOutcome | None = None
    write_back: WriteBackReceipt | None = None


def validate_connection_policy(
    gms_url: str,
    *,
    require_token: bool = False,
    environment: dict[str, str] | None = None,
) -> None:
    """Reject unsafe remote GMS connections before launching the MCP process."""
    parsed = urlparse(gms_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("gms_url must be an absolute HTTP or HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("gms_url must not contain embedded credentials")

    hostname = parsed.hostname.lower()
    is_loopback = hostname == "localhost"
    try:
        is_loopback = is_loopback or ip_address(hostname).is_loopback
    except ValueError:
        pass

    token = (environment if environment is not None else os.environ).get(
        "DATAHUB_GMS_TOKEN", ""
    )
    if not is_loopback and parsed.scheme != "https":
        raise ValueError("remote DataHub connections require HTTPS")
    if (require_token or not is_loopback) and not token.strip():
        raise ValueError("this DataHub connection requires DATAHUB_GMS_TOKEN")


async def _write_back(
    session: ClientSession,
    artifact: DecisionArtifact,
    markdown: str,
    *,
    document_urn: str | None = None,
) -> WriteBackReceipt:
    if document_urn and not document_urn.startswith("urn:li:document:"):
        raise ValueError("document_urn must be a DataHub Document URN")
    related_assets = [artifact.source.urn] + [
        asset.urn for asset in artifact.impacted_assets
    ]
    save_arguments: dict[str, Any] = {
        "document_type": "Decision",
        "title": (
            f"LineageGuard: {artifact.scenario_id} — {artifact.verdict.value.upper()}"
        ),
        "content": markdown,
        "topics": ["lineageguard", artifact.change_kind.value, artifact.verdict.value],
        "related_assets": related_assets,
    }
    if document_urn:
        save_arguments["urn"] = document_urn
    saved = await call_payload(
        session,
        "save_document",
        save_arguments,
    )
    if not isinstance(saved, dict) or not saved.get("success") or not saved.get("urn"):
        raise RuntimeError("DataHub did not confirm the Decision document write-back")
    document_urn = str(saved["urn"])
    read_back = await call_payload(session, "get_entities", {"urns": document_urn})
    document_verified = document_urn in json.dumps(read_back, sort_keys=True)
    if not document_verified:
        raise RuntimeError("DataHub Decision document could not be verified by read-back")
    source_read_back = await call_payload(
        session, "get_entities", {"urns": artifact.source.urn}
    )
    relationship_verified = document_urn in json.dumps(source_read_back, sort_keys=True)
    if not relationship_verified:
        raise RuntimeError(
            "DataHub Decision exists but its relationship to the source asset was not found"
        )
    return WriteBackReceipt(
        success=True,
        document_urn=document_urn,
        document_read_back_verified=True,
        source_relationship_verified=True,
        related_assets_requested=len(related_assets),
    )


async def run_workflow(
    change: SchemaChange,
    *,
    gms_url: str = DEFAULT_GMS_URL,
    server_command: str | None = None,
    max_assets: int = 100,
    write_back: bool = False,
    document_urn: str | None = None,
    require_token: bool = False,
    planner_settings: PlannerSettings | None = None,
    require_planner: bool = False,
    planner_transport: PlannerTransport | None = None,
) -> WorkflowResult:
    if document_urn and not write_back:
        raise ValueError("document_urn requires write_back")
    if require_planner and planner_settings is None:
        raise ValueError("require_planner requires planner_settings")
    parent_env = os.environ.copy()
    validate_connection_policy(
        gms_url, require_token=require_token, environment=parent_env
    )
    child_env = mcp_child_environment(
        parent_env,
        gms_url=gms_url,
        mutation_enabled=write_back,
    )
    parameters = StdioServerParameters(
        command=server_command or default_server_command(), env=child_env
    )
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        async with stdio_client(parameters, errlog=errlog) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                snapshot = await collect_snapshot(
                    session, change, max_assets=max_assets
                )
                artifact = decide(change, snapshot)
                validation_errors = validate_artifact(artifact, change, snapshot)
                planner = None
                if planner_settings is not None:
                    if validation_errors:
                        raise RuntimeError(
                            "Refusing model planning because deterministic artifact "
                            "validation failed"
                        )
                    planner = await run_model_planner(
                        artifact,
                        planner_settings,
                        transport=planner_transport,
                    )
                    if (
                        require_planner
                        and planner.receipt.status != PlannerStatus.ACCEPTED
                    ):
                        raise RuntimeError(
                            "Required model plan was not accepted: "
                            + (planner.receipt.fallback_reason or planner.receipt.status.value)
                        )
                markdown = render_markdown(
                    artifact,
                    planner.proposal if planner is not None else None,
                )
                receipt = None
                if write_back:
                    if validation_errors:
                        raise RuntimeError(
                            "Refusing DataHub write-back because artifact validation failed: "
                            + "; ".join(validation_errors)
                        )
                    receipt = await _write_back(
                        session,
                        artifact,
                        markdown,
                        document_urn=document_urn,
                    )
    return WorkflowResult(
        artifact=artifact,
        validation_errors=validation_errors,
        planner=planner,
        write_back=receipt,
    )


def write_outputs(result: WorkflowResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "decision.json").write_text(
        result.artifact.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "migration-checklist.md").write_text(
        render_markdown(
            result.artifact,
            result.planner.proposal if result.planner is not None else None,
        ),
        encoding="utf-8",
    )
    plan_path = output_dir / "migration-plan.json"
    planner_receipt_path = output_dir / "planner-receipt.json"
    if result.planner is not None:
        planner_receipt_path.write_text(
            result.planner.receipt.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
        if result.planner.proposal is not None:
            plan_path.write_text(
                result.planner.proposal.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
        elif plan_path.exists():
            plan_path.unlink()
    else:
        for stale_path in (plan_path, planner_receipt_path):
            if stale_path.exists():
                stale_path.unlink()
    receipt_path = output_dir / "write-back.json"
    if result.write_back:
        receipt_path.write_text(
            result.write_back.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    elif receipt_path.exists():
        receipt_path.unlink()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess one schema change with DataHub column lineage."
    )
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gms-url", default=DEFAULT_GMS_URL)
    parser.add_argument("--server-command", default=default_server_command())
    parser.add_argument("--max-assets", type=int, default=100)
    parser.add_argument(
        "--planner",
        choices=("off", "model"),
        default="off",
        help="Run the bounded model planner after deterministic validation.",
    )
    parser.add_argument(
        "--require-planner",
        action="store_true",
        help="Fail unless the requested model plan passes grounding validation.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Load runtime secrets from this ignored file when it exists.",
    )
    parser.add_argument(
        "--require-token",
        action="store_true",
        help="Require DATAHUB_GMS_TOKEN even when connecting to local DataHub.",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Create and read back a linked DataHub Decision document.",
    )
    parser.add_argument(
        "--document-urn",
        help="Update an existing Decision document instead of creating a new one.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.document_urn and not args.write_back:
        print("LineageGuard failed: --document-urn requires --write-back", file=sys.stderr)
        return 1
    if args.require_planner and args.planner != "model":
        print(
            "LineageGuard failed: --require-planner requires --planner model",
            file=sys.stderr,
        )
        return 1
    try:
        if args.env_file.exists():
            load_dotenv(args.env_file, override=False)
        planner_settings = (
            PlannerSettings.from_environment(os.environ)
            if args.planner == "model"
            else None
        )
        change = SchemaChange.model_validate_json(args.scenario.read_text("utf-8"))
        result = asyncio.run(
            run_workflow(
                change,
                gms_url=args.gms_url,
                server_command=args.server_command,
                max_assets=args.max_assets,
                write_back=args.write_back,
                document_urn=args.document_urn,
                require_token=args.require_token,
                planner_settings=planner_settings,
                require_planner=args.require_planner,
            )
        )
        write_outputs(result, args.output_dir)
    except Exception as exc:
        print(f"LineageGuard failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "decision_id": result.artifact.decision_id,
                "verdict": result.artifact.verdict.value,
                "downstream_total": result.artifact.evidence.downstream_total,
                "lineage_complete": result.artifact.evidence.lineage_complete,
                "validation_errors": result.validation_errors,
                "planner_status": (
                    result.planner.receipt.status.value if result.planner else "disabled"
                ),
                "planner_model": (
                    result.planner.receipt.model if result.planner else None
                ),
                "document_urn": (
                    result.write_back.document_urn if result.write_back else None
                ),
                "output_dir": str(args.output_dir),
            },
            indent=2,
        )
    )
    return 2 if result.validation_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
