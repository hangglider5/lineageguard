from types import SimpleNamespace
import unittest

from lineageguard.mcp_probe import (
    INTERFACE_TOOLS,
    report_succeeded,
    summarize_lineage_result,
    summarize_tools,
    tool_payload,
)


class SummarizeToolsTests(unittest.TestCase):
    def test_reports_available_and_missing_interfaces(self) -> None:
        tools = [
            SimpleNamespace(name="search", inputSchema={"type": "object"}),
            SimpleNamespace(name="get_lineage", inputSchema={"type": "object"}),
        ]

        report = summarize_tools(tools)

        self.assertEqual(report["available_tool_count"], 2)
        self.assertTrue(report["required_interfaces"]["search"]["available"])
        self.assertEqual(
            report["required_interfaces"]["search"]["input_schema"],
            {"type": "object"},
        )
        self.assertFalse(
            report["required_interfaces"]["add_structured_properties"]["available"]
        )

    def test_interface_names_are_unique(self) -> None:
        self.assertEqual(len(INTERFACE_TOOLS), len(set(INTERFACE_TOOLS)))

    def test_prefers_structured_tool_payload(self) -> None:
        result = SimpleNamespace(
            structuredContent={"total": 1},
            content=[SimpleNamespace(text='{"total": 2}')],
        )

        self.assertEqual(tool_payload(result), {"total": 1})

    def test_falls_back_to_text_tool_payload(self) -> None:
        result = SimpleNamespace(
            structuredContent=None,
            content=[SimpleNamespace(text='{"total": 2}')],
        )

        self.assertEqual(tool_payload(result), {"total": 2})

    def test_summarizes_lineage_result(self) -> None:
        result = SimpleNamespace(
            structuredContent={
                "downstreams": {
                    "total": 2,
                    "searchResults": [
                        {"entity": {"urn": "urn:one"}},
                        {"entity": {"urn": "urn:two"}},
                    ],
                }
            },
            content=[],
            isError=False,
        )

        self.assertEqual(
            summarize_lineage_result(result, "downstream"),
            {
                "is_error": False,
                "total": 2,
                "returned": 2,
                "urns": ["urn:one", "urn:two"],
            },
        )

    def test_report_succeeds_when_requested_checks_pass(self) -> None:
        report = {
            "required_interfaces": {"search": {"available": True}},
            "search_probe": {"is_error": False},
            "lineage_probe": {
                "upstream": {"is_error": False, "total": 1},
                "downstream": {"is_error": False, "total": 2},
            },
            "write_probe": {
                "save": {"success": True},
                "read_back": {"is_error": False, "verified": True},
            },
        }

        self.assertTrue(report_succeeded(report))

    def test_report_fails_when_write_read_back_is_missing(self) -> None:
        report = {
            "required_interfaces": {"search": {"available": True}},
            "write_probe": {
                "save": {"success": True},
                "read_back": {"is_error": None, "verified": False},
            },
        }

        self.assertFalse(report_succeeded(report))


if __name__ == "__main__":
    unittest.main()
