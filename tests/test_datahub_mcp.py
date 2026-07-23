import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from lineageguard.datahub_mcp import (
    DataHubEvidenceError,
    collect_snapshot,
    select_source_urn,
)
from lineageguard.artifacts import render_markdown
from lineageguard.models import ChangeKind, SchemaChange, TargetSelector
from lineageguard.policy import decide
from lineageguard.workflow import WorkflowResult, _write_back, write_outputs


SOURCE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "tenant.order_entry_db.order_entry.orders,PROD)"
)


def result(payload: dict, *, is_error: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        structuredContent=payload,
        content=[],
        isError=is_error,
    )


def change(kind: ChangeKind = ChangeKind.DROP_COLUMN) -> SchemaChange:
    values = {
        "scenario_id": "drop-orders-order-total",
        "target": {
            "query": "/q orders",
            "platform": "dbt",
            "name": "orders",
            "env": "PROD",
            "relation": "order_entry_db.order_entry.orders",
        },
        "kind": kind,
        "field_path": "order_total",
    }
    if kind == ChangeKind.ADD_COLUMN:
        values["after_type"] = "FLOAT"
    else:
        values["before_type"] = "FLOAT"
    return SchemaChange.model_validate(values)


def dataset(urn: str, name: str, platform: str, *, owner: str | None = None) -> dict:
    owners = [] if owner is None else [{"owner": {"urn": owner}}]
    return {
        "urn": urn,
        "type": "DATASET",
        "name": name,
        "properties": {"name": name},
        "platform": {"name": platform},
        "ownership": {"owners": owners},
        "domain": {"domain": {"urn": "urn:li:domain:data-platform"}},
        "tags": {"tags": [{"tag": {"urn": "urn:li:tag:critical"}}]},
        "glossaryTerms": {
            "terms": [{"term": {"urn": "urn:li:glossaryTerm:revenue"}}]
        },
    }


class FakeSession:
    def __init__(self, *, lineage_total: int = 2) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.lineage_total = lineage_total

    async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
        self.calls.append((name, arguments))
        if name == "search":
            return result(
                {
                    "searchResults": [
                        {
                            "entity": {
                                "urn": SOURCE_URN,
                                "properties": {"name": "orders"},
                            }
                        }
                    ]
                }
            )
        if name == "get_entities":
            return result(
                {
                    "result": dataset(
                        SOURCE_URN,
                        "orders",
                        "dbt",
                        owner="urn:li:corpuser:source-owner",
                    )
                }
            )
        if name == "list_schema_fields":
            return result(
                {
                    "fields": [
                        {
                            "fieldPath": "order_total",
                            "nativeDataType": "FLOAT",
                            "description": "Order value",
                            "editedGlossaryTerms": ["Order Total"],
                        }
                    ]
                }
            )
        if name == "get_lineage":
            all_items = [
                {
                    "degree": 1,
                    "lineageColumns": ["order_total"],
                    "entity": dataset(
                        "urn:li:dataset:(urn:li:dataPlatform:snowflake,details,PROD)",
                        "details",
                        "snowflake",
                        owner="urn:li:corpuser:downstream-owner",
                    ),
                },
                {
                    "degree": 3,
                    "lineageColumns": ["total_revenue"],
                    "entity": dataset(
                        "urn:li:dataset:(urn:li:dataPlatform:looker,revenue,PROD)",
                        "revenue",
                        "looker",
                    ),
                },
            ][: self.lineage_total]
            offset = arguments["offset"]
            limit = arguments["max_results"]
            return result(
                {
                    "downstreams": {
                        "total": self.lineage_total,
                        "searchResults": all_items[offset : offset + limit],
                    }
                }
            )
        raise AssertionError(f"unexpected tool: {name}")


class FakeWriteSession:
    def __init__(self, source_urn: str, document_urn: str) -> None:
        self.source_urn = source_urn
        self.document_urn = document_urn
        self.save_arguments: dict | None = None

    async def call_tool(self, name: str, arguments: dict) -> SimpleNamespace:
        if name == "save_document":
            self.save_arguments = arguments
            return result({"success": True, "urn": self.document_urn})
        if name == "get_entities" and arguments["urns"] == self.document_urn:
            return result({"result": {"urn": self.document_urn}})
        if name == "get_entities" and arguments["urns"] == self.source_urn:
            return result(
                {
                    "result": {
                        "urn": self.source_urn,
                        "relatedDocuments": {
                            "documents": [{"urn": self.document_urn}]
                        },
                    }
                }
            )
        raise AssertionError(f"unexpected tool call: {name} {arguments}")


class DataHubMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_collects_exact_column_lineage_and_compacts_metadata(self) -> None:
        session = FakeSession()

        snapshot = await collect_snapshot(session, change())

        self.assertTrue(snapshot.lineage_complete)
        self.assertEqual(snapshot.downstream_total, 2)
        self.assertEqual(snapshot.field.native_type, "FLOAT")
        self.assertEqual(snapshot.field.term_names, ["Order Total"])
        self.assertEqual(snapshot.downstream[0].domain_urns, ["urn:li:domain:data-platform"])
        lineage_call = next(call for call in session.calls if call[0] == "get_lineage")
        self.assertEqual(lineage_call[1]["column"], "order_total")

    async def test_safety_cap_marks_lineage_incomplete(self) -> None:
        snapshot = await collect_snapshot(FakeSession(), change(), max_assets=1)

        self.assertFalse(snapshot.lineage_complete)
        self.assertEqual(len(snapshot.downstream), 1)
        self.assertTrue(any("safety cap" in warning for warning in snapshot.warnings))

    async def test_addition_skips_column_lineage(self) -> None:
        session = FakeSession()

        snapshot = await collect_snapshot(session, change(ChangeKind.ADD_COLUMN))

        self.assertEqual(snapshot.downstream, [])
        self.assertFalse(any(name == "get_lineage" for name, _ in session.calls))

    async def test_write_back_verifies_document_and_source_relationship(self) -> None:
        snapshot = await collect_snapshot(FakeSession(), change())
        artifact = decide(change(), snapshot)
        document_urn = "urn:li:document:lineageguard-test"
        session = FakeWriteSession(artifact.source.urn, document_urn)

        receipt = await _write_back(
            session,  # type: ignore[arg-type]
            artifact,
            render_markdown(artifact),
            document_urn=document_urn,
        )

        self.assertTrue(receipt.document_read_back_verified)
        self.assertTrue(receipt.source_relationship_verified)
        self.assertEqual(receipt.related_assets_requested, 3)
        self.assertEqual(session.save_arguments["urn"], document_urn)

    async def test_write_back_rejects_non_document_update_urn(self) -> None:
        snapshot = await collect_snapshot(FakeSession(), change())
        artifact = decide(change(), snapshot)
        session = FakeWriteSession(
            artifact.source.urn, "urn:li:dataset:not-a-document"
        )

        with self.assertRaises(ValueError):
            await _write_back(
                session,  # type: ignore[arg-type]
                artifact,
                render_markdown(artifact),
                document_urn="urn:li:dataset:not-a-document",
            )

    async def test_read_only_output_removes_stale_write_back_receipt(self) -> None:
        snapshot = await collect_snapshot(FakeSession(), change())
        artifact = decide(change(), snapshot)
        workflow_result = WorkflowResult(artifact=artifact, validation_errors=[])

        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir)
            receipt = output_dir / "write-back.json"
            receipt.write_text("stale", encoding="utf-8")

            write_outputs(workflow_result, output_dir)

            self.assertFalse(receipt.exists())

    def test_ambiguous_source_is_rejected(self) -> None:
        target = TargetSelector(
            query="/q orders",
            platform="dbt",
            name="orders",
            env="PROD",
            relation="warehouse.orders",
        )
        payload = {
            "searchResults": [
                {
                    "entity": {
                        "urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,a.orders,PROD)",
                        "properties": {"name": "orders"},
                    }
                },
                {
                    "entity": {
                        "urn": "urn:li:dataset:(urn:li:dataPlatform:dbt,b.orders,PROD)",
                        "properties": {"name": "orders"},
                    }
                },
            ]
        }

        with self.assertRaises(DataHubEvidenceError):
            select_source_urn(payload, target)

    def test_committed_scenario_is_strictly_valid(self) -> None:
        scenario_path = Path(__file__).parents[1] / "scenarios/drop_orders_order_total.json"

        scenario = SchemaChange.model_validate_json(scenario_path.read_text("utf-8"))

        self.assertEqual(scenario.before_type, "FLOAT")
        self.assertEqual(scenario.kind, ChangeKind.DROP_COLUMN)


if __name__ == "__main__":
    unittest.main()
