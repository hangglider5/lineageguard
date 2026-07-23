"""End-to-end LineageGuard command: graph read, decision, artifact, write-back."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, ConfigDict

from .artifacts import render_markdown, validate_artifact
from .datahub_mcp import call_payload, collect_snapshot
from .mcp_probe import DEFAULT_GMS_URL, default_server_command
from .models import DecisionArtifact, SchemaChange
from .policy import decide


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
    write_back: WriteBackReceipt | None = None


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
) -> WorkflowResult:
    if document_urn and not write_back:
        raise ValueError("document_urn requires write_back")
    child_env = os.environ.copy()
    child_env.update(
        {
            "DATAHUB_GMS_URL": gms_url,
            "DATAHUB_TELEMETRY_ENABLED": "false",
            "TOOLS_IS_MUTATION_ENABLED": "true" if write_back else "false",
        }
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
                markdown = render_markdown(artifact)
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
        write_back=receipt,
    )


def write_outputs(result: WorkflowResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "decision.json").write_text(
        result.artifact.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "migration-checklist.md").write_text(
        render_markdown(result.artifact), encoding="utf-8"
    )
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
    try:
        change = SchemaChange.model_validate_json(args.scenario.read_text("utf-8"))
        result = asyncio.run(
            run_workflow(
                change,
                gms_url=args.gms_url,
                server_command=args.server_command,
                max_assets=args.max_assets,
                write_back=args.write_back,
                document_urn=args.document_urn,
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
