#!/usr/bin/env python3
"""Build a transparent GitHub Pages demo from committed verification evidence."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Sequence


STATIC_ASSETS = ("demo.css", "demo.js", "favicon.svg")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid evidence file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"evidence file must contain an object: {path}")
    return value


def _replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"expected exactly one HTML marker: {old}")
    return source.replace(old, new)


def _validated_snapshot(repository_root: Path) -> dict[str, Any]:
    artifact = _load_json(
        repository_root / "examples/drop-orders-order-total/decision.json"
    )
    live = _load_json(repository_root / "examples/live-evaluation.json")
    fixed = _load_json(repository_root / "examples/evaluation-report.json")
    authenticated = _load_json(repository_root / "examples/authenticated-gate.json")

    evidence = artifact.get("evidence", {})
    actual = live.get("actual", {})
    workflow = authenticated.get("workflow", {})
    required = {
        "artifact verdict": artifact.get("verdict") == "block",
        "artifact severity": artifact.get("severity") == "high",
        "artifact downstream count": evidence.get("downstream_total") == 17,
        "artifact completeness": evidence.get("lineage_complete") is True,
        "artifact asset count": len(artifact.get("impacted_assets", [])) == 17,
        "live gate": live.get("passed") is True,
        "live verdict agreement": actual.get("verdict") == artifact.get("verdict"),
        "live count agreement": actual.get("downstream_total")
        == evidence.get("downstream_total"),
        "fixed evaluation": fixed.get("passed_cases") == fixed.get("total_cases") == 16,
        "fixed checks": fixed.get("passed_checks") == fixed.get("total_checks") == 130,
        "authenticated artifact": workflow.get("artifact_valid") is True,
        "authenticated write-back": workflow.get("write_back_success") is True,
        "document read-back": workflow.get("document_read_back_verified") is True,
        "relationship read-back": workflow.get("source_relationship_verified") is True,
    }
    failed = [name for name, passed in required.items() if not passed]
    if failed:
        raise ValueError("inconsistent committed evidence: " + ", ".join(failed))

    latency = float(live.get("end_to_end_latency_ms", 0))
    return {
        "schema_version": "1.0",
        "mode": "verified_evidence_snapshot",
        "captured_at": authenticated.get("verified_at"),
        "verdict": artifact["verdict"],
        "severity": artifact["severity"],
        "latency_ms": latency,
        "request_id": "verified-evidence-20260728",
        "result_freshness": "Verified evidence · Jul 28, 2026",
        "result_meta": f"{latency:,.0f} ms live MCP gate",
        "artifact": artifact,
        "verification": {
            "datahub_core_version": authenticated.get("datahub_core_version"),
            "mcp_server_datahub_version": authenticated.get(
                "mcp_server_datahub_version"
            ),
            "fixed_cases": fixed.get("total_cases"),
            "fixed_checks": fixed.get("total_checks"),
            "live_gate_passed": True,
            "authenticated_write_back_verified": True,
            "document_read_back_verified": True,
            "source_relationship_verified": True,
        },
    }


def build_pages(repository_root: Path, output: Path) -> Path:
    repository_root = repository_root.resolve()
    output = output.resolve()
    if output == repository_root:
        raise ValueError("output directory cannot be the repository root")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    assets_output = output / "assets"
    assets_output.mkdir()

    static_root = repository_root / "src/lineageguard/static"
    html = (static_root / "index.html").read_text("utf-8")
    html = _replace_once(
        html,
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '    <meta http-equiv="Content-Security-Policy" content="default-src '
        "'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
        "img-src 'self'; base-uri 'none'; form-action 'none'\">",
    )
    html = _replace_once(html, 'data-demo-mode="live"', 'data-demo-mode="snapshot"')
    html = _replace_once(
        html,
        "        Read-only public demo\n      </div>",
        "        Verified evidence snapshot\n      </div>",
    )
    html = _replace_once(html, "Run impact review", "Inspect verified evidence")
    html = _replace_once(
        html,
        "Runs a real review with the latest DataHub lineage.",
        'Replays a committed, validated DataHub result. <a href="https://github.com/'
        'hangglider5/lineageguard/tree/main/examples">View evidence</a>.',
    )
    html = _replace_once(
        html,
        "LineageGuard will read the fixed DataHub scenario, evaluate every discovered dependency, and validate the resulting action plan.",
        "Inspect the evidence captured by the live DataHub MCP gate, including every discovered dependency and the validated action plan.",
    )
    html = _replace_once(
        html,
        "Reading schema, ownership, and downstream lineage…",
        "Loading the committed schema, ownership, and lineage evidence…",
    )
    html = _replace_once(
        html,
        "Read-only public demo · No graph changes",
        "Verified snapshot · Live MCP and write-back evidence linked in the repository",
    )
    (output / "index.html").write_text(html, "utf-8")
    (output / ".nojekyll").write_text("", "utf-8")
    (output / "snapshot.json").write_text(
        json.dumps(_validated_snapshot(repository_root), indent=2) + "\n", "utf-8"
    )
    for name in STATIC_ASSETS:
        shutil.copyfile(static_root / name, assets_output / name)
    return output


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = build_pages(args.repository_root, args.output)
    print(json.dumps({"pages_output": str(output), "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
