"""Read-only, fixed-scenario HTTP API for the public LineageGuard demo."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import os
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from importlib.resources import files
from typing import Awaitable, Callable, Sequence

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .mcp_probe import DEFAULT_GMS_URL, default_server_command
from .models import SchemaChange, StrictModel
from .workflow import WorkflowResult, run_workflow


DEMO_SCENARIO_ID = "drop-orders-order-total"
STATIC_CONTENT_TYPES = {
    "demo.css": "text/css; charset=utf-8",
    "demo.js": "application/javascript; charset=utf-8",
    "favicon.svg": "image/svg+xml",
}


class DemoReviewRequest(StrictModel):
    scenario_id: str = DEMO_SCENARIO_ID


@dataclass(frozen=True)
class DemoSettings:
    gms_url: str = DEFAULT_GMS_URL
    server_command: str = default_server_command()
    require_datahub_token: bool = False
    api_key: str = ""
    timeout_seconds: float = 30.0
    max_body_bytes: int = 1024
    rate_limit_requests: int = 10
    rate_limit_window_seconds: float = 60.0
    max_concurrent_requests: int = 2
    concurrency_wait_seconds: float = 0.01

    @classmethod
    def from_environment(cls) -> "DemoSettings":
        require_token = os.environ.get(
            "LINEAGEGUARD_REQUIRE_DATAHUB_AUTH", "false"
        ).casefold()
        if require_token not in {"true", "false"}:
            raise ValueError(
                "LINEAGEGUARD_REQUIRE_DATAHUB_AUTH must be true or false"
            )
        return cls(
            gms_url=os.environ.get("DATAHUB_GMS_URL", DEFAULT_GMS_URL),
            server_command=os.environ.get(
                "LINEAGEGUARD_MCP_SERVER_COMMAND", default_server_command()
            ),
            require_datahub_token=require_token == "true",
            api_key=os.environ.get("LINEAGEGUARD_DEMO_API_KEY", ""),
        )


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                if int(content_length) > self.max_body_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse(
                    {"error": "invalid_content_length"}, status_code=400
                )(scope, receive, send)
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._reject(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"error": "request_too_large"}, status_code=413)(
            scope, receive, send
        )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (
                            b"content-security-policy",
                            b"default-src 'none'; style-src 'self'; "
                            b"script-src 'self'; connect-src 'self'; "
                            b"img-src 'self'; base-uri 'none'; "
                            b"form-action 'none'; frame-ancestors 'none'",
                        ),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SlidingWindowRateLimiter:
    def __init__(self, requests: int, window_seconds: float) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._timestamps: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        async with self._lock:
            timestamps = self._timestamps[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.requests:
                return False
            timestamps.append(now)
            return True


class RequestCapacity:
    def __init__(self, requests: int, wait_seconds: float) -> None:
        self._semaphore = asyncio.Semaphore(requests)
        self._wait_seconds = wait_seconds

    async def acquire(self) -> bool:
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(), timeout=self._wait_seconds
            )
            return True
        except asyncio.TimeoutError:
            return False

    def release(self) -> None:
        self._semaphore.release()


WorkflowRunner = Callable[..., Awaitable[WorkflowResult]]


def _authorized(request: Request, api_key: str) -> bool:
    if not api_key:
        return True
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    return authorization.startswith(prefix) and hmac.compare_digest(
        authorization[len(prefix) :], api_key
    )


def _static_resource(name: str) -> str:
    return files("lineageguard").joinpath("static", name).read_text("utf-8")


def create_app(
    settings: DemoSettings | None = None,
    *,
    workflow_runner: WorkflowRunner = run_workflow,
) -> Starlette:
    configuration = settings or DemoSettings.from_environment()
    limiter = SlidingWindowRateLimiter(
        configuration.rate_limit_requests,
        configuration.rate_limit_window_seconds,
    )
    capacity = RequestCapacity(
        configuration.max_concurrent_requests,
        configuration.concurrency_wait_seconds,
    )

    async def index(_: Request) -> Response:
        return HTMLResponse(_static_resource("index.html"))

    async def static_asset(request: Request) -> Response:
        name = request.path_params["name"]
        media_type = STATIC_CONTENT_TYPES.get(name)
        if media_type is None:
            return Response(status_code=404)
        return Response(_static_resource(name), media_type=media_type)

    async def health(_: Request) -> Response:
        return JSONResponse(
            {
                "status": "ok",
                "mode": "fixed_scenario_read_only",
                "scenario_id": DEMO_SCENARIO_ID,
            }
        )

    async def scenarios(_: Request) -> Response:
        return JSONResponse(
            {
                "scenarios": [
                    {
                        "scenario_id": DEMO_SCENARIO_ID,
                        "title": "Drop dbt orders.order_total",
                        "change_kind": "drop_column",
                    }
                ]
            }
        )

    async def review(request: Request) -> Response:
        request_id = str(uuid.uuid4())
        client_host = request.client.host if request.client else "unknown"
        if not await limiter.allow(client_host):
            return JSONResponse(
                {"error": "rate_limit_exceeded", "request_id": request_id},
                status_code=429,
                headers={
                    "Retry-After": str(int(configuration.rate_limit_window_seconds))
                },
            )
        if not _authorized(request, configuration.api_key):
            return JSONResponse(
                {"error": "unauthorized", "request_id": request_id},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/json":
            return JSONResponse(
                {"error": "content_type_must_be_json", "request_id": request_id},
                status_code=415,
            )
        try:
            payload = json.loads((await request.body()).decode("utf-8"))
            review_request = DemoReviewRequest.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            return JSONResponse(
                {"error": "invalid_request", "request_id": request_id},
                status_code=422,
            )
        if review_request.scenario_id != DEMO_SCENARIO_ID:
            return JSONResponse(
                {"error": "unsupported_scenario", "request_id": request_id},
                status_code=422,
            )

        scenario_json = (
            files("lineageguard").joinpath("demo_scenario.json").read_text("utf-8")
        )
        change = SchemaChange.model_validate_json(scenario_json)
        if not await capacity.acquire():
            return JSONResponse(
                {"error": "server_busy", "request_id": request_id},
                status_code=503,
                headers={"Retry-After": "1"},
            )
        started = time.perf_counter()
        try:
            try:
                result = await asyncio.wait_for(
                    workflow_runner(
                        change,
                        gms_url=configuration.gms_url,
                        server_command=configuration.server_command,
                        max_assets=100,
                        write_back=False,
                        require_token=configuration.require_datahub_token,
                    ),
                    timeout=configuration.timeout_seconds,
                )
            except asyncio.TimeoutError:
                return JSONResponse(
                    {"error": "upstream_timeout", "request_id": request_id},
                    status_code=504,
                )
            except Exception:
                return JSONResponse(
                    {"error": "upstream_unavailable", "request_id": request_id},
                    status_code=503,
                )
        finally:
            capacity.release()
        if result.validation_errors:
            return JSONResponse(
                {"error": "artifact_validation_failed", "request_id": request_id},
                status_code=502,
            )
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        artifact = result.artifact
        return JSONResponse(
            {
                "schema_version": "1.0",
                "request_id": request_id,
                "scenario_id": DEMO_SCENARIO_ID,
                "verdict": artifact.verdict.value,
                "severity": artifact.severity.value,
                "latency_ms": latency_ms,
                "validation_errors": result.validation_errors,
                "artifact": artifact.model_dump(mode="json"),
            }
        )

    application = Starlette(
        debug=False,
        routes=[
            Route("/", index, methods=["GET"]),
            Route("/assets/{name:str}", static_asset, methods=["GET"]),
            Route("/health", health, methods=["GET"]),
            Route("/api/scenarios", scenarios, methods=["GET"]),
            Route("/api/review", review, methods=["POST"]),
        ],
    )
    application.add_middleware(
        BodyLimitMiddleware, max_body_bytes=configuration.max_body_bytes
    )
    application.add_middleware(SecurityHeadersMiddleware)
    return application


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the read-only, fixed-scenario LineageGuard demo API."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--require-datahub-auth",
        action="store_true",
        help="Require DATAHUB_GMS_TOKEN even for a loopback DataHub endpoint.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    import uvicorn

    args = parse_args(argv)
    settings = DemoSettings.from_environment()
    if args.require_datahub_auth:
        settings = replace(settings, require_datahub_token=True)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, workers=1)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
