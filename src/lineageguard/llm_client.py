"""OpenAI-compatible transports for the bounded LineageGuard planner."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Protocol

import httpx
from pydantic import Field, SecretStr

from .models import StrictModel


class PlannerProvider(str, Enum):
    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"


class PlannerSettings(StrictModel):
    provider: PlannerProvider
    api_key: SecretStr
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: float = Field(default=25.0, gt=0, le=60)
    max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    max_attempts: int = Field(default=2, ge=1, le=2)
    thinking_enabled: bool = False
    openrouter_provider: str | None = Field(
        default=None,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
    )
    openrouter_zdr: bool = False

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
    ) -> "PlannerSettings":
        provider_value = environment.get(
            "LINEAGEGUARD_LLM_PROVIDER", PlannerProvider.DEEPSEEK.value
        ).casefold()
        try:
            provider = PlannerProvider(provider_value)
        except ValueError as exc:
            raise ValueError(
                "LINEAGEGUARD_LLM_PROVIDER must be deepseek or openrouter"
            ) from exc

        provider_key_name = (
            "DEEPSEEK_API_KEY"
            if provider == PlannerProvider.DEEPSEEK
            else "OPENROUTER_API_KEY"
        )
        api_key = environment.get("LINEAGEGUARD_LLM_API_KEY") or environment.get(
            provider_key_name
        )
        if not api_key or not api_key.strip():
            raise ValueError(
                "model planning requires LINEAGEGUARD_LLM_API_KEY or "
                f"{provider_key_name}"
            )

        default_model = (
            "deepseek-v4-flash"
            if provider == PlannerProvider.DEEPSEEK
            else "deepseek/deepseek-v4-flash"
        )
        return cls(
            provider=provider,
            api_key=SecretStr(api_key.strip()),
            model=environment.get("LINEAGEGUARD_LLM_MODEL", default_model).strip(),
            thinking_enabled=_environment_bool(
                environment, "LINEAGEGUARD_LLM_THINKING", default=False
            ),
            openrouter_provider=(
                environment.get("LINEAGEGUARD_OPENROUTER_PROVIDER") or None
            ),
            openrouter_zdr=_environment_bool(
                environment, "LINEAGEGUARD_OPENROUTER_ZDR", default=False
            ),
        )


class PlannerTransportResponse(StrictModel):
    content: str
    request_id: str | None = None
    finish_reason: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(ge=0)
    actual_provider: str | None = None


class PlannerTransportError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class PlannerTransport(Protocol):
    async def complete_json(
        self,
        settings: PlannerSettings,
        messages: Sequence[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> PlannerTransportResponse: ...


def _environment_bool(
    environment: Mapping[str, str], name: str, *, default: bool
) -> bool:
    value = environment.get(name)
    if value is None:
        return default
    normalized = value.casefold().strip()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return normalized == "true"


def _provider_url(provider: PlannerProvider) -> str:
    if provider == PlannerProvider.DEEPSEEK:
        return "https://api.deepseek.com/chat/completions"
    return "https://openrouter.ai/api/v1/chat/completions"


def _response_format(
    provider: PlannerProvider,
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    if provider == PlannerProvider.OPENROUTER:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "lineageguard_migration_proposal",
                "strict": True,
                "schema": json_schema,
            },
        }
    return {"type": "json_object"}


def _request_body(
    settings: PlannerSettings,
    messages: Sequence[dict[str, str]],
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": settings.model,
        "messages": list(messages),
        "max_tokens": settings.max_output_tokens,
        "response_format": _response_format(settings.provider, json_schema),
        "stream": False,
    }
    if settings.provider == PlannerProvider.DEEPSEEK:
        body["thinking"] = {
            "type": "enabled" if settings.thinking_enabled else "disabled"
        }
        if not settings.thinking_enabled:
            body["temperature"] = 0
    else:
        body["reasoning"] = {
            "effort": "high" if settings.thinking_enabled else "none",
            "exclude": True,
        }
        provider: dict[str, Any] = {
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        }
        if settings.openrouter_provider:
            provider["order"] = [settings.openrouter_provider]
        if settings.openrouter_zdr:
            provider["zdr"] = True
        body["provider"] = provider
    return body


class HttpPlannerTransport:
    """Perform one non-streaming request without implicit retries."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def complete_json(
        self,
        settings: PlannerSettings,
        messages: Sequence[dict[str, str]],
        json_schema: dict[str, Any],
    ) -> PlannerTransportResponse:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.timeout_seconds),
                transport=self._transport,
            ) as client:
                response = await client.post(
                    _provider_url(settings.provider),
                    headers={
                        "Authorization": (
                            "Bearer " + settings.api_key.get_secret_value()
                        ),
                        "Content-Type": "application/json",
                        "User-Agent": "LineageGuard/0.1",
                    },
                    json=_request_body(settings, messages, json_schema),
                )
        except httpx.TimeoutException as exc:
            raise PlannerTransportError(
                "planner request timed out", retryable=True
            ) from exc
        except httpx.RequestError as exc:
            raise PlannerTransportError(
                "planner network request failed", retryable=True
            ) from exc

        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise PlannerTransportError(
                f"planner request returned HTTP {response.status_code}",
                retryable=retryable,
            )
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise PlannerTransportError(
                "planner response was not a JSON envelope", retryable=True
            ) from exc
        try:
            choice = payload["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise PlannerTransportError(
                "planner response envelope was incomplete", retryable=True
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise PlannerTransportError(
                "planner returned empty content", retryable=True
            )

        usage = payload.get("usage") if isinstance(payload, dict) else None
        usage = usage if isinstance(usage, dict) else {}

        def safe_token_count(name: str) -> int:
            value = usage.get(name)
            return value if isinstance(value, int) and value >= 0 else 0

        return PlannerTransportResponse(
            content=content,
            request_id=(
                str(payload["id"])
                if isinstance(payload, dict) and payload.get("id")
                else response.headers.get("x-request-id")
            ),
            finish_reason=(
                str(choice["finish_reason"])
                if choice.get("finish_reason") is not None
                else None
            ),
            input_tokens=safe_token_count("prompt_tokens"),
            output_tokens=safe_token_count("completion_tokens"),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            actual_provider=(
                str(payload["provider"])
                if isinstance(payload, dict) and payload.get("provider")
                else settings.provider.value
            ),
        )


def request_body_for_test(
    settings: PlannerSettings,
    messages: Sequence[dict[str, str]],
    json_schema: dict[str, Any],
) -> dict[str, Any]:
    """Expose the deterministic request shape for offline contract tests."""

    return _request_body(settings, messages, json_schema)
