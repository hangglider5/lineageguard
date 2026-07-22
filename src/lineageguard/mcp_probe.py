"""Probe the official DataHub MCP server over its stdio transport."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, Sequence

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


DEFAULT_GMS_URL = "http://localhost:8080"
INTERFACE_TOOLS = (
    "search",
    "get_entities",
    "list_schema_fields",
    "get_lineage",
    "get_lineage_paths_between",
    "update_description",
    "add_structured_properties",
    "save_document",
)


def default_server_command() -> str:
    """Return the MCP executable installed beside the active Python."""

    executable = Path(sys.executable).with_name("mcp-server-datahub")
    return str(executable)


def summarize_tools(tools: Sequence[Any]) -> dict[str, Any]:
    """Return stable, JSON-serializable schemas for LineageGuard interfaces."""

    by_name = {tool.name: tool for tool in tools}
    return {
        "available_tool_count": len(tools),
        "required_interfaces": {
            name: {
                "available": name in by_name,
                "input_schema": by_name[name].inputSchema if name in by_name else None,
            }
            for name in INTERFACE_TOOLS
        },
    }


def tool_payload(result: Any) -> dict[str, Any]:
    """Extract the structured payload from an MCP tool result."""

    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    for item in result.content:
        text = getattr(item, "text", None)
        if text:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
    raise ValueError("MCP tool result did not contain a JSON object")


def summarize_lineage_result(result: Any, direction: str) -> dict[str, Any]:
    """Reduce a verbose lineage response to stable evidence for smoke tests."""

    payload = tool_payload(result)
    section = payload[f"{direction}s"]
    search_results = section.get("searchResults", [])
    return {
        "is_error": result.isError,
        "total": section.get("total"),
        "returned": len(search_results),
        "urns": [item["entity"]["urn"] for item in search_results],
    }


async def probe(
    gms_url: str,
    server_command: str,
    *,
    exercise_search: bool = False,
    write_probe_document: bool = False,
) -> dict[str, Any]:
    """Initialize MCP and return the advertised LineageGuard tool schemas."""

    child_env = os.environ.copy()
    child_env.update(
        {
            "DATAHUB_GMS_URL": gms_url,
            "DATAHUB_TELEMETRY_ENABLED": "false",
            "TOOLS_IS_MUTATION_ENABLED": "true",
        }
    )
    parameters = StdioServerParameters(command=server_command, env=child_env)

    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialize_result = await session.initialize()
            tools_result = await session.list_tools()
            search_result = None
            upstream_result = None
            downstream_result = None
            save_result = None
            read_back_result = None
            search_urn = None
            if exercise_search:
                search_result = await session.call_tool(
                    "search",
                    {
                        "query": "/q orders",
                        "filter": "entity_type = dataset",
                        "num_results": 5,
                    },
                )
                search_payload = tool_payload(search_result)
                search_urn = search_payload["searchResults"][0]["entity"]["urn"]
                upstream_result = await session.call_tool(
                    "get_lineage",
                    {
                        "urn": search_urn,
                        "upstream": True,
                        "max_hops": 3,
                        "max_results": 20,
                    },
                )
                downstream_result = await session.call_tool(
                    "get_lineage",
                    {
                        "urn": search_urn,
                        "upstream": False,
                        "max_hops": 3,
                        "max_results": 20,
                    },
                )
                if write_probe_document:
                    upstream_summary = summarize_lineage_result(
                        upstream_result, "upstream"
                    )
                    downstream_summary = summarize_lineage_result(
                        downstream_result, "downstream"
                    )
                    save_result = await session.call_tool(
                        "save_document",
                        {
                            "document_type": "Decision",
                            "title": "LineageGuard local interface validation",
                            "content": (
                                "# LineageGuard local interface validation\n\n"
                                "This document is a harmless smoke-test artifact proving that "
                                "the agent can write a reviewable decision back to DataHub.\n\n"
                                f"- Source asset: `{search_urn}`\n"
                                f"- Upstream assets: {upstream_summary['total']}\n"
                                f"- Downstream assets: {downstream_summary['total']}\n\n"
                                "This is interface evidence only, not approval for a production "
                                "schema change."
                            ),
                            "topics": ["lineageguard", "interface-probe"],
                            "related_assets": [search_urn],
                        },
                    )
                    save_payload = tool_payload(save_result)
                    if save_payload.get("success") and save_payload.get("urn"):
                        read_back_result = await session.call_tool(
                            "get_entities", {"urns": save_payload["urn"]}
                        )

    report = summarize_tools(tools_result.tools)
    report["server"] = {
        "name": initialize_result.serverInfo.name,
        "protocol_server_version": initialize_result.serverInfo.version,
        "package_version": version("mcp-server-datahub"),
    }
    report["gms_url"] = gms_url
    if search_result is not None:
        search_payload = tool_payload(search_result)
        report["search_probe"] = {
            "is_error": search_result.isError,
            "total": search_payload.get("total"),
            "urns": [
                item["entity"]["urn"]
                for item in search_payload.get("searchResults", [])
            ],
        }
        assert search_urn is not None
        assert upstream_result is not None
        assert downstream_result is not None
        report["lineage_probe"] = {
            "source_urn": search_urn,
            "upstream": summarize_lineage_result(upstream_result, "upstream"),
            "downstream": summarize_lineage_result(downstream_result, "downstream"),
        }
    if save_result is not None:
        save_payload = tool_payload(save_result)
        saved_urn = save_payload.get("urn")
        report["write_probe"] = {
            "save": save_payload,
            "read_back": {
                "is_error": read_back_result.isError if read_back_result else None,
                "verified": bool(
                    read_back_result
                    and saved_urn
                    and saved_urn in json.dumps(tool_payload(read_back_result))
                ),
            },
        }
    return report


def report_succeeded(report: dict[str, Any]) -> bool:
    """Return whether every interface requested by the probe was verified."""

    interfaces_ok = all(
        details["available"]
        for details in report["required_interfaces"].values()
    )
    search = report.get("search_probe")
    search_ok = search is None or not search["is_error"]
    lineage = report.get("lineage_probe")
    lineage_ok = lineage is None or all(
        not lineage[direction]["is_error"]
        and lineage[direction]["total"] is not None
        for direction in ("upstream", "downstream")
    )
    write = report.get("write_probe")
    write_ok = write is None or (
        write["save"].get("success")
        and not write["read_back"]["is_error"]
        and write["read_back"]["verified"]
    )
    return bool(interfaces_ok and search_ok and lineage_ok and write_ok)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the DataHub MCP handshake and LineageGuard tool schemas."
    )
    parser.add_argument(
        "--gms-url",
        default=os.environ.get("DATAHUB_GMS_URL", DEFAULT_GMS_URL),
    )
    parser.add_argument("--server-command", default=default_server_command())
    parser.add_argument(
        "--exercise-search",
        action="store_true",
        help="Also call the read-only search tool for sample order datasets.",
    )
    parser.add_argument(
        "--write-probe-document",
        action="store_true",
        help="Create and read back one harmless DataHub Decision document.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = asyncio.run(
        probe(
            args.gms_url,
            args.server_command,
            exercise_search=args.exercise_search or args.write_probe_document,
            write_probe_document=args.write_probe_document,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report_succeeded(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
