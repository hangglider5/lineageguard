"""Validate local and external Devpost submission readiness."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse


REQUIRED_DEVPOST_SECTIONS = {
    "Problem",
    "Solution",
    "How it works",
    "How we use DataHub",
    "Validation",
    "What makes it different",
    "Built with",
    "Challenges",
    "What's next",
    "Disclosures",
}
REQUIRED_JUDGE_GUIDE_SECTIONS = {
    "60-second path",
    "Evidence map",
    "Five-minute source verification",
    "Full live reproduction",
    "What the video proves",
}
EXTERNAL_URL_FIELDS = ("repository_url", "project_url", "video_url")
VIDEO_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "vimeo.com", "youku.com", "www.youku.com"}
REQUIRED_AVAILABILITY_UNTIL = "2026-09-01T05:00:00+08:00"
REQUIRED_SAMPLE_OUTPUTS = {
    "examples/drop-orders-order-total/decision.json",
    "examples/drop-orders-order-total/migration-checklist.md",
    "examples/drop-orders-order-total/migration-plan.json",
    "examples/drop-orders-order-total/planner-receipt.json",
    "examples/drop-orders-order-total/planner-rehearsal.json",
    "examples/drop-orders-order-total/integrated-migration-plan.json",
    "examples/drop-orders-order-total/integrated-planner-receipt.json",
    "examples/drop-orders-order-total/integrated-workflow.json",
    "examples/drop-orders-order-total/integrated-write-back.json",
    "examples/evaluation-report.json",
    "examples/live-evaluation.json",
    "examples/authenticated-gate.json",
}


@dataclass(frozen=True)
class SubmissionReport:
    local_errors: tuple[str, ...]
    external_blockers: tuple[str, ...]
    narration_words: int

    @property
    def local_materials_passed(self) -> bool:
        return not self.local_errors

    @property
    def submission_ready(self) -> bool:
        return self.local_materials_passed and not self.external_blockers

    def as_dict(self) -> dict[str, Any]:
        return {
            "local_materials_passed": self.local_materials_passed,
            "submission_ready": self.submission_ready,
            "narration_words": self.narration_words,
            "local_errors": list(self.local_errors),
            "external_blockers": list(self.external_blockers),
        }


def _read_text(repository_root: Path, relative_path: str, errors: list[str]) -> str:
    path = repository_root / relative_path
    if not path.is_file():
        errors.append(f"missing required file: {relative_path}")
        return ""
    content = path.read_text("utf-8")
    if not content.strip():
        errors.append(f"required file is empty: {relative_path}")
    return content


def _headings(markdown: str) -> set[str]:
    return {
        match.group(1).strip()
        for match in re.finditer(r"^##\s+(.+?)\s*$", markdown, re.MULTILINE)
    }


def _narration_word_count(markdown: str) -> int:
    narration = " ".join(
        line.removeprefix("> ")
        for line in markdown.splitlines()
        if line.startswith("> ")
    )
    return len(re.findall(r"\b[\w'-]+\b", narration))


def _valid_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname)


def validate_submission_manifest(
    manifest_path: Path,
    *,
    repository_root: Path | None = None,
) -> SubmissionReport:
    repository_root = (
        repository_root.resolve()
        if repository_root is not None
        else manifest_path.resolve().parents[1]
    )
    errors: list[str] = []
    blockers: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return SubmissionReport((f"invalid manifest: {exc}",), (), 0)

    if manifest.get("schema_version") != "1.0":
        errors.append("manifest schema_version must be 1.0")
    if manifest.get("project_name") != "LineageGuard":
        errors.append("manifest project_name must be LineageGuard")
    if manifest.get("primary_category") != "Agents That Do Real Work":
        errors.append("primary_category must be Agents That Do Real Work")
    if manifest.get("availability_until") != REQUIRED_AVAILABILITY_UNTIL:
        errors.append(
            "availability_until must be " + REQUIRED_AVAILABILITY_UNTIL
        )

    materials = manifest.get("materials")
    if not isinstance(materials, dict):
        errors.append("manifest materials must be an object")
        materials = {}
    sample_outputs = materials.get("sample_outputs")
    if not isinstance(sample_outputs, list):
        errors.append("materials sample_outputs must be a list")
        sample_outputs = []
    missing_outputs = REQUIRED_SAMPLE_OUTPUTS - set(
        path for path in sample_outputs if isinstance(path, str)
    )
    if missing_outputs:
        errors.append(
            "materials sample_outputs omitted required evidence: "
            + ", ".join(sorted(missing_outputs))
        )
    required_paths = [
        materials.get("description"),
        materials.get("demo_script"),
        materials.get("judge_guide"),
        materials.get("license"),
        materials.get("readme"),
        *sample_outputs,
    ]
    if any(not isinstance(path, str) or not path for path in required_paths):
        errors.append("every material path must be a non-empty string")
        required_paths = [path for path in required_paths if isinstance(path, str)]
    contents = {
        path: _read_text(repository_root, path, errors) for path in required_paths
    }

    description_path = materials.get("description", "")
    description = contents.get(description_path, "")
    missing_sections = REQUIRED_DEVPOST_SECTIONS - _headings(description)
    if missing_sections:
        errors.append(
            "Devpost draft is missing sections: " + ", ".join(sorted(missing_sections))
        )
    if re.search(r"\b(TODO|TBD)\b|example\.com", description, re.IGNORECASE):
        errors.append("Devpost draft contains a placeholder")

    judge_guide_path = materials.get("judge_guide", "")
    judge_guide = contents.get(judge_guide_path, "")
    missing_guide_sections = REQUIRED_JUDGE_GUIDE_SECTIONS - _headings(judge_guide)
    if missing_guide_sections:
        errors.append(
            "judge guide is missing sections: "
            + ", ".join(sorted(missing_guide_sections))
        )

    demo_script_path = materials.get("demo_script", "")
    demo_script = contents.get(demo_script_path, "")
    narration_words = _narration_word_count(demo_script)
    if narration_words < 250:
        errors.append("demo narration must contain at least 250 words")
    if narration_words > 420:
        errors.append("demo narration exceeds the 420-word safety cap")
    if "02:55" not in demo_script:
        errors.append("demo script must end by the 02:55 safety mark")

    license_path = materials.get("license", "")
    license_text = contents.get(license_path, "")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        errors.append("LICENSE is not recognizable as Apache-2.0")

    disclosures = manifest.get("disclosures")
    if not isinstance(disclosures, dict) or not all(
        isinstance(disclosures.get(key), str) and disclosures[key].strip()
        for key in ("pre_existing_work", "ai_assistance")
    ):
        errors.append("pre-existing work and AI assistance disclosures are required")

    for field in EXTERNAL_URL_FIELDS:
        value = manifest.get(field)
        if not _valid_https_url(value):
            blockers.append(f"{field} is not configured with an HTTPS URL")
    repository_url = manifest.get("repository_url")
    if _valid_https_url(repository_url) and urlparse(repository_url).hostname not in {
        "github.com",
        "www.github.com",
    }:
        blockers.append("repository_url must point to a public GitHub repository")
    video_url = manifest.get("video_url")
    if _valid_https_url(video_url) and urlparse(video_url).hostname not in VIDEO_HOSTS:
        blockers.append("video_url must use YouTube, Vimeo, or Youku")

    return SubmissionReport(tuple(errors), tuple(blockers), narration_words)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when public repository, project, or video URLs are absent.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = validate_submission_manifest(args.manifest)
    print(json.dumps(report.as_dict(), indent=2))
    if not report.local_materials_passed:
        return 1
    if args.strict and not report.submission_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
