import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lineageguard.submission_gate import validate_submission_manifest


REPOSITORY_ROOT = Path(__file__).parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "submission/manifest.json"


class SubmissionGateTests(unittest.TestCase):
    def test_local_submission_materials_pass_with_external_blockers(self) -> None:
        report = validate_submission_manifest(MANIFEST_PATH)

        self.assertTrue(report.local_materials_passed)
        self.assertFalse(report.submission_ready)
        self.assertGreaterEqual(report.narration_words, 250)
        self.assertLessEqual(report.narration_words, 420)
        self.assertEqual(
            report.external_blockers,
            (
                "video_url is not configured with an HTTPS URL",
            ),
        )

    def test_complete_https_urls_clear_external_blockers(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
        manifest.update(
            {
                "repository_url": "https://github.com/hangglider5/lineageguard",
                "project_url": "https://lineageguard.example.org",
                "video_url": "https://youtu.be/lineageguard-demo",
            }
        )
        with TemporaryDirectory() as temporary:
            nested = Path(temporary) / "submission"
            nested.mkdir()
            nested_manifest = nested / "manifest.json"
            nested_manifest.write_text(json.dumps(manifest), "utf-8")
            report = validate_submission_manifest(
                nested_manifest, repository_root=REPOSITORY_ROOT
            )

        self.assertTrue(report.submission_ready)

    def test_unapproved_video_host_remains_blocked(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
        manifest.update(
            {
                "repository_url": "https://github.com/hangglider5/lineageguard",
                "project_url": "https://lineageguard.example.org",
                "video_url": "https://videos.example.org/demo",
            }
        )
        with TemporaryDirectory() as temporary:
            nested = Path(temporary) / "submission"
            nested.mkdir()
            nested_manifest = nested / "manifest.json"
            nested_manifest.write_text(json.dumps(manifest), "utf-8")
            report = validate_submission_manifest(
                nested_manifest, repository_root=REPOSITORY_ROOT
            )

        self.assertFalse(report.submission_ready)
        self.assertIn(
            "video_url must use YouTube, Vimeo, or Youku",
            report.external_blockers,
        )

    def test_required_judging_availability_is_enforced(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
        manifest["availability_until"] = "2026-08-11T05:00:00+08:00"
        with TemporaryDirectory() as temporary:
            nested = Path(temporary) / "submission"
            nested.mkdir()
            nested_manifest = nested / "manifest.json"
            nested_manifest.write_text(json.dumps(manifest), "utf-8")
            report = validate_submission_manifest(
                nested_manifest, repository_root=REPOSITORY_ROOT
            )

        self.assertFalse(report.local_materials_passed)
        self.assertIn(
            "availability_until must be 2026-09-01T05:00:00+08:00",
            report.local_errors,
        )

    def test_integrated_evidence_cannot_be_omitted(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text("utf-8"))
        manifest["materials"]["sample_outputs"].remove(
            "examples/drop-orders-order-total/integrated-workflow.json"
        )
        with TemporaryDirectory() as temporary:
            nested = Path(temporary) / "submission"
            nested.mkdir()
            nested_manifest = nested / "manifest.json"
            nested_manifest.write_text(json.dumps(manifest), "utf-8")
            report = validate_submission_manifest(
                nested_manifest, repository_root=REPOSITORY_ROOT
            )

        self.assertFalse(report.local_materials_passed)
        self.assertIn(
            "materials sample_outputs omitted required evidence: "
            "examples/drop-orders-order-total/integrated-workflow.json",
            report.local_errors,
        )


if __name__ == "__main__":
    unittest.main()
