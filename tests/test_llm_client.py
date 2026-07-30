import unittest
import json

import httpx
from pydantic import SecretStr

from lineageguard.llm_client import (
    HttpPlannerTransport,
    PlannerProvider,
    PlannerSettings,
    PlannerTransportError,
    request_body_for_test,
)
from lineageguard.planner import MigrationProposal


MESSAGES = [
    {"role": "system", "content": "Return JSON."},
    {"role": "user", "content": "{}"},
]


class PlannerClientSettingsTests(unittest.TestCase):
    def test_deepseek_defaults_and_generic_key(self) -> None:
        settings = PlannerSettings.from_environment(
            {"LINEAGEGUARD_LLM_API_KEY": "secret-value"}
        )

        self.assertEqual(settings.provider, PlannerProvider.DEEPSEEK)
        self.assertEqual(settings.model, "deepseek-v4-flash")
        self.assertEqual(settings.api_key.get_secret_value(), "secret-value")
        self.assertNotIn("secret-value", repr(settings))

    def test_provider_specific_openrouter_key_and_controls(self) -> None:
        settings = PlannerSettings.from_environment(
            {
                "LINEAGEGUARD_LLM_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "router-secret",
                "LINEAGEGUARD_LLM_MODEL": "deepseek/deepseek-v4-pro",
                "LINEAGEGUARD_OPENROUTER_PROVIDER": "deepseek",
                "LINEAGEGUARD_OPENROUTER_ZDR": "true",
                "LINEAGEGUARD_LLM_THINKING": "true",
            }
        )

        self.assertEqual(settings.provider, PlannerProvider.OPENROUTER)
        self.assertEqual(settings.model, "deepseek/deepseek-v4-pro")
        self.assertEqual(settings.openrouter_provider, "deepseek")
        self.assertTrue(settings.openrouter_zdr)
        self.assertTrue(settings.thinking_enabled)

    def test_missing_key_and_invalid_boolean_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires"):
            PlannerSettings.from_environment({})
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            PlannerSettings.from_environment(
                {
                    "DEEPSEEK_API_KEY": "secret",
                    "LINEAGEGUARD_LLM_THINKING": "sometimes",
                }
            )

    def test_deepseek_request_disables_thinking_and_uses_json_object(self) -> None:
        settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("secret"),
            model="deepseek-v4-flash",
        )

        body = request_body_for_test(
            settings, MESSAGES, MigrationProposal.model_json_schema()
        )

        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(body["temperature"], 0)
        self.assertNotIn("secret", str(body))

    def test_openrouter_request_requires_schema_and_disables_fallbacks(self) -> None:
        settings = PlannerSettings(
            provider=PlannerProvider.OPENROUTER,
            api_key=SecretStr("secret"),
            model="deepseek/deepseek-v4-flash",
            openrouter_provider="deepseek",
            openrouter_zdr=True,
        )

        body = request_body_for_test(
            settings, MESSAGES, MigrationProposal.model_json_schema()
        )

        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(body["reasoning"]["effort"], "none")
        self.assertFalse(body["provider"]["allow_fallbacks"])
        self.assertTrue(body["provider"]["require_parameters"])
        self.assertEqual(body["provider"]["data_collection"], "deny")
        self.assertTrue(body["provider"]["zdr"])
        self.assertEqual(body["provider"]["order"], ["deepseek"])


class HttpPlannerTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_parses_success_without_exposing_key_in_body(self) -> None:
        observed = {}

        def handler(request: httpx.Request) -> httpx.Response:
            observed["url"] = str(request.url)
            observed["authorization"] = request.headers["authorization"]
            observed["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "response-1",
                    "provider": "DeepSeek",
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "{}"},
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 3},
                },
            )

        settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("transport-secret"),
            model="deepseek-v4-flash",
        )
        client = HttpPlannerTransport(httpx.MockTransport(handler))

        result = await client.complete_json(
            settings, MESSAGES, MigrationProposal.model_json_schema()
        )

        self.assertEqual(observed["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(observed["authorization"], "Bearer transport-secret")
        self.assertNotIn("transport-secret", json.dumps(observed["body"]))
        self.assertEqual(result.request_id, "response-1")
        self.assertEqual(result.input_tokens, 12)
        self.assertEqual(result.output_tokens, 3)
        self.assertEqual(result.actual_provider, "DeepSeek")

    async def test_http_error_classification_is_bounded_and_redacted(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "do not copy provider body"})

        settings = PlannerSettings(
            provider=PlannerProvider.OPENROUTER,
            api_key=SecretStr("secret"),
            model="deepseek/deepseek-v4-flash",
        )
        client = HttpPlannerTransport(httpx.MockTransport(handler))

        with self.assertRaises(PlannerTransportError) as caught:
            await client.complete_json(
                settings, MESSAGES, MigrationProposal.model_json_schema()
            )

        self.assertTrue(caught.exception.retryable)
        self.assertEqual(str(caught.exception), "planner request returned HTTP 429")

    async def test_empty_content_is_retryable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": ""}}
                    ]
                },
            )

        settings = PlannerSettings(
            provider=PlannerProvider.DEEPSEEK,
            api_key=SecretStr("secret"),
            model="deepseek-v4-flash",
        )
        client = HttpPlannerTransport(httpx.MockTransport(handler))

        with self.assertRaises(PlannerTransportError) as caught:
            await client.complete_json(
                settings, MESSAGES, MigrationProposal.model_json_schema()
            )

        self.assertTrue(caught.exception.retryable)
        self.assertEqual(str(caught.exception), "planner returned empty content")


if __name__ == "__main__":
    unittest.main()
