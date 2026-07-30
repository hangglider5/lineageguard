import unittest

from lineageguard.subprocess_env import mcp_child_environment


class McpChildEnvironmentTests(unittest.TestCase):
    def test_only_allowlisted_environment_reaches_mcp_process(self) -> None:
        child = mcp_child_environment(
            {
                "PATH": "/usr/bin",
                "HOME": "/tmp/example-home",
                "DATAHUB_GMS_TOKEN": "datahub-token",
                "LINEAGEGUARD_LLM_API_KEY": "llm-secret",
                "DEEPSEEK_API_KEY": "deepseek-secret",
                "OPENROUTER_API_KEY": "openrouter-secret",
                "UNRELATED_SECRET": "other-secret",
            },
            gms_url="https://datahub.example.com",
            mutation_enabled=False,
        )

        self.assertEqual(child["DATAHUB_GMS_TOKEN"], "datahub-token")
        self.assertEqual(child["DATAHUB_GMS_URL"], "https://datahub.example.com")
        self.assertEqual(child["TOOLS_IS_MUTATION_ENABLED"], "false")
        self.assertEqual(child["DATAHUB_TELEMETRY_ENABLED"], "false")
        self.assertNotIn("LINEAGEGUARD_LLM_API_KEY", child)
        self.assertNotIn("DEEPSEEK_API_KEY", child)
        self.assertNotIn("OPENROUTER_API_KEY", child)
        self.assertNotIn("UNRELATED_SECRET", child)

    def test_mutation_mode_is_explicit(self) -> None:
        child = mcp_child_environment(
            {}, gms_url="http://localhost:8080", mutation_enabled=True
        )

        self.assertEqual(child["TOOLS_IS_MUTATION_ENABLED"], "true")


if __name__ == "__main__":
    unittest.main()
