import unittest

from lineageguard.workflow import validate_connection_policy


class ConnectionPolicyTests(unittest.TestCase):
    def test_local_http_without_token_is_allowed(self) -> None:
        validate_connection_policy("http://localhost:8080", environment={})
        validate_connection_policy("http://127.0.0.1:8080", environment={})
        validate_connection_policy("http://[::1]:8080", environment={})

    def test_remote_http_is_rejected_even_with_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "require HTTPS"):
            validate_connection_policy(
                "http://datahub.example.com",
                environment={"DATAHUB_GMS_TOKEN": "secret"},
            )

    def test_remote_https_without_token_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires DATAHUB_GMS_TOKEN"):
            validate_connection_policy("https://datahub.example.com", environment={})

    def test_remote_https_with_token_is_allowed(self) -> None:
        validate_connection_policy(
            "https://datahub.example.com",
            environment={"DATAHUB_GMS_TOKEN": "secret"},
        )

    def test_embedded_credentials_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "embedded credentials"):
            validate_connection_policy(
                "https://user:password@datahub.example.com",
                environment={"DATAHUB_GMS_TOKEN": "secret"},
            )

    def test_local_token_can_be_explicitly_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires DATAHUB_GMS_TOKEN"):
            validate_connection_policy(
                "http://localhost:8080", require_token=True, environment={}
            )

    def test_invalid_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute HTTP or HTTPS URL"):
            validate_connection_policy("localhost:8080", environment={})


if __name__ == "__main__":
    unittest.main()
