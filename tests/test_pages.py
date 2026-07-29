import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_pages import build_pages


REPOSITORY_ROOT = Path(__file__).parents[1]


class PagesBuildTests(unittest.TestCase):
    def test_builds_transparent_snapshot_site_from_committed_evidence(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "site"
            build_pages(REPOSITORY_ROOT, output)
            html = (output / "index.html").read_text("utf-8")
            snapshot = json.loads((output / "snapshot.json").read_text("utf-8"))

            self.assertIn('data-demo-mode="snapshot"', html)
            self.assertIn("Verified evidence snapshot", html)
            self.assertNotIn("Runs a real review with the latest", html)
            self.assertEqual(snapshot["mode"], "verified_evidence_snapshot")
            self.assertEqual(snapshot["artifact"]["evidence"]["downstream_total"], 17)
            self.assertTrue(snapshot["verification"]["authenticated_write_back_verified"])

    def test_pages_assets_use_project_relative_urls(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "site"
            build_pages(REPOSITORY_ROOT, output)
            html = (output / "index.html").read_text("utf-8")

            self.assertIn('href="assets/demo.css"', html)
            self.assertIn('src="assets/demo.js"', html)
            self.assertIn('href="./"', html)
            self.assertTrue((output / "assets/favicon.svg").is_file())

    def test_refuses_to_mix_output_with_existing_files(self) -> None:
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "site"
            output.mkdir()
            (output / "unrelated.txt").write_text("preserve me", "utf-8")

            with self.assertRaisesRegex(ValueError, "must be empty"):
                build_pages(REPOSITORY_ROOT, output)

            self.assertEqual((output / "unrelated.txt").read_text("utf-8"), "preserve me")


if __name__ == "__main__":
    unittest.main()
