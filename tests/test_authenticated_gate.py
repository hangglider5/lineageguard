import json
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]


class AuthenticatedGateEvidenceTests(unittest.TestCase):
    def test_receipt_records_authenticated_read_write_without_a_secret(self) -> None:
        receipt = json.loads(
            (REPOSITORY_ROOT / "examples/authenticated-gate.json").read_text("utf-8")
        )

        self.assertEqual(receipt["authentication"]["unauthenticated_graphql_status"], 401)
        self.assertEqual(
            receipt["authentication"]["environment_variable"],
            "DATAHUB_GMS_TOKEN",
        )
        self.assertFalse(receipt["authentication"]["token_recorded"])
        self.assertFalse(receipt["authentication"]["scoped_permissions_verified"])
        self.assertTrue(receipt["workflow"]["write_back_success"])
        self.assertTrue(receipt["workflow"]["document_read_back_verified"])
        self.assertTrue(receipt["workflow"]["source_relationship_verified"])
        self.assertFalse(receipt["public_api"]["write_surface_exposed"])


if __name__ == "__main__":
    unittest.main()
