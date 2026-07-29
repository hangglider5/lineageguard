import asyncio
import unittest
from importlib.resources import files
from pathlib import Path

import httpx

from lineageguard.demo_api import DemoSettings, create_app
from lineageguard.models import DecisionArtifact
from lineageguard.workflow import WorkflowResult


REPOSITORY_ROOT = Path(__file__).parents[1]


class DemoApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.calls: list[dict] = []
        artifact = DecisionArtifact.model_validate_json(
            (
                REPOSITORY_ROOT
                / "examples/drop-orders-order-total/decision.json"
            ).read_text("utf-8")
        )

        async def fake_runner(*args, **kwargs) -> WorkflowResult:
            self.calls.append(kwargs)
            return WorkflowResult(artifact=artifact, validation_errors=[])

        self.fake_runner = fake_runner

    def test_packaged_demo_scenario_matches_canonical_scenario(self) -> None:
        packaged = files("lineageguard").joinpath("demo_scenario.json").read_text(
            "utf-8"
        )
        canonical = (
            REPOSITORY_ROOT / "scenarios/drop_orders_order_total.json"
        ).read_text("utf-8")

        self.assertEqual(packaged, canonical)

    def client(self, settings: DemoSettings | None = None) -> httpx.AsyncClient:
        app = create_app(settings or DemoSettings(), workflow_runner=self.fake_runner)
        transport = httpx.ASGITransport(
            app=app, client=("198.51.100.10", 50000)
        )
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def test_health_is_safe_and_non_cacheable(self) -> None:
        async with self.client() as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "fixed_scenario_read_only")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(self.calls, [])

    async def test_demo_page_and_assets_are_served_with_strict_csp(self) -> None:
        async with self.client() as client:
            page = await client.get("/")
            stylesheet = await client.get("/assets/demo.css")
            script = await client.get("/assets/demo.js")
            favicon = await client.get("/assets/favicon.svg")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Drop orders.order_total?", page.text)
        self.assertIn('src="assets/demo.js"', page.text)
        self.assertIn('data-demo-mode="live"', page.text)
        self.assertNotIn("<script>", page.text)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn("--blue: #075ee6", stylesheet.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn('fetch("/api/review"', script.text)
        self.assertEqual(favicon.status_code, 200)
        self.assertEqual(favicon.headers["content-type"], "image/svg+xml")
        csp = page.headers["content-security-policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(self.calls, [])

    async def test_static_asset_allowlist_rejects_unknown_files(self) -> None:
        async with self.client() as client:
            response = await client.get("/assets/demo_scenario.json")

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("order_total", response.text)

    async def test_review_runs_only_fixed_read_only_workflow(self) -> None:
        async with self.client() as client:
            response = await client.post(
                "/api/review",
                json={"scenario_id": "drop-orders-order-total"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verdict"], "block")
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(self.calls[0]["write_back"])
        self.assertEqual(self.calls[0]["max_assets"], 100)

    async def test_user_cannot_request_write_back_or_another_scenario(self) -> None:
        async with self.client() as client:
            write_response = await client.post(
                "/api/review",
                json={
                    "scenario_id": "drop-orders-order-total",
                    "write_back": True,
                },
            )
            scenario_response = await client.post(
                "/api/review", json={"scenario_id": "user-controlled"}
            )

        self.assertEqual(write_response.status_code, 422)
        self.assertEqual(scenario_response.status_code, 422)
        self.assertEqual(self.calls, [])

    async def test_body_limit_is_enforced(self) -> None:
        settings = DemoSettings(max_body_bytes=16)
        async with self.client(settings) as client:
            response = await client.post(
                "/api/review",
                content=b'{"scenario_id":"too-large"}',
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"], "request_too_large")

    async def test_rate_limit_is_enforced_per_client(self) -> None:
        settings = DemoSettings(rate_limit_requests=1)
        async with self.client(settings) as client:
            first = await client.post("/api/review", json={})
            second = await client.post("/api/review", json={})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    async def test_optional_api_key_is_compared_as_bearer_token(self) -> None:
        settings = DemoSettings(api_key="demo-secret")
        async with self.client(settings) as client:
            missing = await client.post("/api/review", json={})
            accepted = await client.post(
                "/api/review",
                json={},
                headers={"Authorization": "Bearer demo-secret"},
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(accepted.status_code, 200)

    async def test_unauthorized_attempts_are_rate_limited(self) -> None:
        settings = DemoSettings(api_key="demo-secret", rate_limit_requests=1)
        async with self.client(settings) as client:
            rejected = await client.post("/api/review", json={})
            limited = await client.post(
                "/api/review",
                json={},
                headers={"Authorization": "Bearer demo-secret"},
            )

        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(limited.status_code, 429)

    async def test_timeout_returns_generic_error(self) -> None:
        async def slow_runner(*args, **kwargs) -> WorkflowResult:
            await asyncio.sleep(0.05)
            raise AssertionError("unreachable")

        app = create_app(
            DemoSettings(timeout_seconds=0.001), workflow_runner=slow_runner
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post("/api/review", json={})

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error"], "upstream_timeout")

    async def test_invalid_artifact_fails_closed(self) -> None:
        artifact = DecisionArtifact.model_validate_json(
            (
                REPOSITORY_ROOT
                / "examples/drop-orders-order-total/decision.json"
            ).read_text("utf-8")
        )

        async def invalid_runner(*args, **kwargs) -> WorkflowResult:
            return WorkflowResult(
                artifact=artifact, validation_errors=["unsupported asset"]
            )

        app = create_app(DemoSettings(), workflow_runner=invalid_runner)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post("/api/review", json={})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], "artifact_validation_failed")
        self.assertNotIn("validation_errors", response.json())

    async def test_concurrent_workflow_capacity_fails_fast(self) -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        artifact = DecisionArtifact.model_validate_json(
            (
                REPOSITORY_ROOT
                / "examples/drop-orders-order-total/decision.json"
            ).read_text("utf-8")
        )

        async def blocking_runner(*args, **kwargs) -> WorkflowResult:
            started.set()
            await release.wait()
            return WorkflowResult(artifact=artifact, validation_errors=[])

        settings = DemoSettings(
            max_concurrent_requests=1, concurrency_wait_seconds=0.001
        )
        app = create_app(settings, workflow_runner=blocking_runner)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            first_task = asyncio.create_task(client.post("/api/review", json={}))
            await started.wait()
            second = await client.post("/api/review", json={})
            release.set()
            first = await first_task

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 503)
        self.assertEqual(second.json()["error"], "server_busy")


if __name__ == "__main__":
    unittest.main()
