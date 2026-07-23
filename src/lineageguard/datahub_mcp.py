"""Compact, attributable DataHub MCP reads for LineageGuard."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from .mcp_probe import tool_payload
from .models import (
    AssetImpact,
    ChangeKind,
    ImpactSnapshot,
    SchemaChange,
    SchemaFieldEvidence,
    TargetSelector,
)


DATASET_URN = re.compile(
    r"^urn:li:dataset:\(urn:li:dataPlatform:(?P<platform>[^,]+),.+,(?P<env>[^,)]+)\)$"
)
ENTITY_TYPE = re.compile(r"^urn:li:(?P<entity_type>[^:(]+)")


class McpSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class DataHubEvidenceError(RuntimeError):
    """Raised when MCP evidence is missing, ambiguous, or malformed."""


def _unique_strings(values: list[Any]) -> list[str]:
    return sorted({value for value in values if isinstance(value, str) and value})


def unwrap_result(payload: Any) -> Any:
    """Unwrap FastMCP's structured ``result`` envelope when present."""

    if isinstance(payload, dict) and set(payload) == {"result"}:
        return payload["result"]
    return payload


async def call_payload(
    session: McpSession, name: str, arguments: dict[str, Any]
) -> Any:
    result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        details = " ".join(
            str(getattr(item, "text", "")) for item in getattr(result, "content", [])
        ).strip()
        raise DataHubEvidenceError(f"DataHub MCP tool {name} failed: {details}")
    try:
        return unwrap_result(tool_payload(result))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise DataHubEvidenceError(
            f"DataHub MCP tool {name} returned an unsupported payload"
        ) from exc


def _dataset_coordinates(urn: str) -> tuple[str | None, str | None]:
    match = DATASET_URN.match(urn)
    if not match:
        return None, None
    return match.group("platform"), match.group("env")


def _entity_name(entity: dict[str, Any]) -> str:
    properties = entity.get("properties") or {}
    return str(entity.get("name") or properties.get("name") or entity.get("urn") or "")


def select_source_urn(payload: dict[str, Any], target: TargetSelector) -> str:
    """Resolve one exact source; never silently choose an ambiguous search hit."""

    candidates: list[str] = []
    for item in payload.get("searchResults", []):
        entity = item.get("entity") or {}
        urn = entity.get("urn")
        if not isinstance(urn, str):
            continue
        platform, env = _dataset_coordinates(urn)
        if (
            platform == target.platform
            and env == target.env
            and _entity_name(entity).casefold() == target.name.casefold()
        ):
            candidates.append(urn)

    relation_matches = [
        urn for urn in candidates if target.relation.casefold() in urn.casefold()
    ]
    if relation_matches:
        candidates = relation_matches
    candidates = sorted(set(candidates))
    if not candidates:
        raise DataHubEvidenceError(
            f"No exact {target.platform}/{target.env} dataset named {target.name!r} "
            "was found"
        )
    if len(candidates) > 1:
        raise DataHubEvidenceError(
            "Source selection is ambiguous: " + ", ".join(candidates)
        )
    return candidates[0]


def normalize_entity(
    entity: dict[str, Any], *, degree: int, impacted_columns: list[str] | None = None
) -> AssetImpact:
    urn = entity.get("urn")
    if not isinstance(urn, str):
        raise DataHubEvidenceError("DataHub entity is missing its URN")
    platform_value = entity.get("platform") or {}
    platform, _ = _dataset_coordinates(urn)
    platform = platform_value.get("name") or platform
    entity_match = ENTITY_TYPE.match(urn)
    entity_type = entity.get("type") or (
        entity_match.group("entity_type").upper() if entity_match else "UNKNOWN"
    )
    ownership = (entity.get("ownership") or {}).get("owners") or []
    domain = (entity.get("domain") or {}).get("domain") or {}
    tags = (entity.get("tags") or {}).get("tags") or []
    terms = (entity.get("glossaryTerms") or {}).get("terms") or []
    return AssetImpact(
        urn=urn,
        entity_type=str(entity_type).upper(),
        name=_entity_name(entity),
        platform=str(platform) if platform else None,
        degree=degree,
        owner_urns=_unique_strings(
            [(entry.get("owner") or {}).get("urn") for entry in ownership]
        ),
        domain_urns=_unique_strings([domain.get("urn")]),
        tag_urns=_unique_strings(
            [(entry.get("tag") or {}).get("urn") for entry in tags]
        ),
        term_urns=_unique_strings(
            [(entry.get("term") or {}).get("urn") for entry in terms]
        ),
        impacted_columns=_unique_strings(impacted_columns or []),
    )


def find_schema_field(
    payload: dict[str, Any], field_path: str
) -> SchemaFieldEvidence | None:
    fields = payload.get("fields") or []
    exact = [field for field in fields if field.get("fieldPath") == field_path]
    if not exact:
        exact = [
            field
            for field in fields
            if str(field.get("fieldPath", "")).casefold() == field_path.casefold()
        ]
    if not exact:
        return None
    if len(exact) > 1:
        raise DataHubEvidenceError(f"Schema field selection is ambiguous: {field_path}")
    field = exact[0]
    return SchemaFieldEvidence(
        field_path=str(field["fieldPath"]),
        native_type=field.get("nativeDataType") or field.get("type"),
        description=field.get("editedDescription") or field.get("description"),
        tag_names=_unique_strings(
            list(field.get("tags") or []) + list(field.get("editedTags") or [])
        ),
        term_names=_unique_strings(
            list(field.get("glossaryTerms") or [])
            + list(field.get("editedGlossaryTerms") or [])
        ),
    )


async def _read_lineage(
    session: McpSession,
    source_urn: str,
    field_path: str,
    *,
    max_assets: int,
) -> tuple[int, list[AssetImpact], bool, list[str]]:
    assets: dict[str, AssetImpact] = {}
    offset = 0
    reported_total: int | None = None
    warnings: list[str] = []

    while offset < max_assets:
        payload = await call_payload(
            session,
            "get_lineage",
            {
                "urn": source_urn,
                "column": field_path,
                "upstream": False,
                "max_hops": 3,
                # The server applies offset after its GraphQL window. Request the
                # whole safety-bounded window on every page so offset remains usable.
                "max_results": max_assets,
                "offset": offset,
            },
        )
        if not isinstance(payload, dict) or not isinstance(
            payload.get("downstreams"), dict
        ):
            raise DataHubEvidenceError("get_lineage omitted the downstream result")
        downstreams = payload["downstreams"]
        page_total = downstreams.get("total")
        if not isinstance(page_total, int) or page_total < 0:
            raise DataHubEvidenceError("get_lineage omitted a valid downstream total")
        if reported_total is None:
            reported_total = page_total
        elif reported_total != page_total:
            reported_total = max(reported_total, page_total)
            warnings.append("Downstream lineage total changed while paging.")

        page = downstreams.get("searchResults") or []
        if not isinstance(page, list):
            raise DataHubEvidenceError("get_lineage returned malformed searchResults")
        for item in page:
            entity = item.get("entity") or {}
            asset = normalize_entity(
                entity,
                degree=int(item.get("degree") or 0),
                impacted_columns=item.get("lineageColumns") or [],
            )
            assets[asset.urn] = asset

        page_size = len(page)
        offset += page_size
        target_count = min(reported_total, max_assets)
        if len(assets) >= target_count or page_size == 0:
            break

    total = reported_total or 0
    ordered_assets = sorted(assets.values(), key=lambda asset: asset.urn)
    complete = total == len(ordered_assets)
    if total > max_assets:
        warnings.append(
            f"Lineage safety cap reached: evaluated {len(ordered_assets)} of {total} assets."
        )
    elif not complete:
        warnings.append(
            f"Lineage retrieval stopped after {len(ordered_assets)} of {total} assets."
        )
    return total, ordered_assets, complete, warnings


async def collect_snapshot(
    session: McpSession, change: SchemaChange, *, max_assets: int = 100
) -> ImpactSnapshot:
    """Read and compact the graph context required by the policy engine."""

    if max_assets < 1:
        raise ValueError("max_assets must be positive")
    search = await call_payload(
        session,
        "search",
        {
            "query": change.target.query,
            "filter": "entity_type = dataset",
            "num_results": 50,
        },
    )
    if not isinstance(search, dict):
        raise DataHubEvidenceError("search returned a non-object payload")
    source_urn = select_source_urn(search, change.target)

    source_payload = await call_payload(session, "get_entities", {"urns": source_urn})
    if not isinstance(source_payload, dict):
        raise DataHubEvidenceError("get_entities returned a non-object source")
    source = normalize_entity(source_payload, degree=0)

    fields = await call_payload(
        session,
        "list_schema_fields",
        {"urn": source_urn, "keywords": [change.field_path], "limit": 100},
    )
    if not isinstance(fields, dict):
        raise DataHubEvidenceError("list_schema_fields returned a non-object payload")
    field = find_schema_field(fields, change.field_path)

    if change.kind == ChangeKind.ADD_COLUMN:
        return ImpactSnapshot(
            source=source,
            field=field,
            downstream_total=0,
            downstream=[],
            lineage_complete=True,
            warnings=["Additive changes do not consume existing column lineage."],
        )
    if field is None:
        return ImpactSnapshot(
            source=source,
            field=None,
            downstream_total=0,
            downstream=[],
            lineage_complete=False,
            warnings=["Column lineage was not queried because the source field was absent."],
        )

    total, downstream, complete, warnings = await _read_lineage(
        session,
        source_urn,
        field.field_path,
        max_assets=max_assets,
    )
    return ImpactSnapshot(
        source=source,
        field=field,
        downstream_total=total,
        downstream=downstream,
        lineage_complete=complete,
        warnings=warnings,
    )
