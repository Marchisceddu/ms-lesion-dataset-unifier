"""
Tests for pipeline CLI argument parsing and task collection.
"""

import tempfile
import unittest
from pathlib import Path

from src.pipeline import build_parser as build_pipeline_parser, collect_tasks
from src.process_single import build_parser as build_single_parser


class TestPipelineCLI(unittest.TestCase):

    def test_pipeline_parser(self):
        """Verify pipeline CLI arguments."""
        parser = build_pipeline_parser()
        args = parser.parse_args(["--input_dir", "raw", "--output_dir", "proc", "--workers", "4", "-v", "--flair_only"])
        self.assertEqual(args.input_dir, "raw")
        self.assertEqual(args.output_dir, "proc")
        self.assertEqual(args.workers, 4)
        self.assertTrue(args.verbose)
        self.assertTrue(args.flair_only)
        self.assertFalse(args.keep_intermediates)

    def test_single_parser(self):
        """Verify process_single CLI arguments."""
        parser = build_single_parser()
        args = parser.parse_args([
            "--output_dir", "out",
            "--flair_file", "flair.nii.gz",
            "--align_ref", "FLAIR",
            "--enabled_steps", "flirt", "bet",
            "--keep_intermediates"
        ])
        self.assertEqual(args.output_dir, "out")
        self.assertEqual(args.flair_file, "flair.nii.gz")
        self.assertEqual(args.align_ref, "FLAIR")
        self.assertEqual(args.enabled_steps, ["flirt", "bet"])
        self.assertTrue(args.keep_intermediates)

    def test_collect_tasks_skips_hidden_and_support_dirs(self):
        """Ensures collect_tasks skips hidden files and support directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            raw = tmppath / "raw"
            proc = tmppath / "proc"
            raw.mkdir()

            # Normal dataset
            (raw / "MSLesSeg" / "Patient01" / "TP1").mkdir(parents=True)
            (raw / "MSLesSeg" / "Patient02" / "TP1").mkdir(parents=True)

            # Support directory (should be skipped from being treated as patient)
            (raw / "MSLesSeg" / "support_MSLesSeg").mkdir(parents=True)

            # Hidden directory (should be skipped)
            (raw / ".hidden_dataset" / "Pat" / "TP").mkdir(parents=True)

            tasks = collect_tasks(raw, proc)
            self.assertEqual(len(tasks), 2)
            patient_ids = {t["patient_id"] for t in tasks}
            self.assertEqual(patient_ids, {"Patient01", "Patient02"})


if __name__ == "__main__":
    unittest.main()
