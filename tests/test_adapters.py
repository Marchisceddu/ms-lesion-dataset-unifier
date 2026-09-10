"""
Tests for DatasetRegistry and adapters.
"""

import tempfile
import unittest
from pathlib import Path

from src.adapters import (
    BaseDatasetAdapter,
    DatasetRegistry,
    GenericDatasetAdapter,
    ISBI2015Adapter,
    MSLesSegAdapter,
    MSSEG2016Adapter,
    PubMRIAdapter,
    TaskContext,
)
from src.utils import Logger


class TestDatasetAdapters(unittest.TestCase):

    def test_registry_resolution(self):
        """Tests that known datasets resolve to their specialized adapters."""
        self.assertIsInstance(DatasetRegistry.get_adapter("MSSEG-2016"), MSSEG2016Adapter)
        self.assertIsInstance(DatasetRegistry.get_adapter("msseg_2016_raw"), MSSEG2016Adapter)
        self.assertIsInstance(DatasetRegistry.get_adapter("PubMRI_Center1"), PubMRIAdapter)
        self.assertIsInstance(DatasetRegistry.get_adapter("MSLesSeg_v1"), MSLesSegAdapter)
        self.assertIsInstance(DatasetRegistry.get_adapter("ISBI-2015-test"), ISBI2015Adapter)

    def test_generic_fallback(self):
        """Tests that any novel / unknown dataset falls back to GenericDatasetAdapter."""
        adapter = DatasetRegistry.get_adapter("UnseenNewMSDataset")
        self.assertIsInstance(adapter, GenericDatasetAdapter)
        self.assertEqual(adapter.name, "Generic")

    def test_custom_adapter_registration(self):
        """Tests dynamically registering a new custom adapter."""
        @DatasetRegistry.register
        class NovelCenterAdapter(BaseDatasetAdapter):
            name = "NovelCenter"
            def match(self, dataset_name: str) -> bool:
                return "novelcenter" in dataset_name.lower()

        adapter = DatasetRegistry.get_adapter("NovelCenter_CohortA")
        self.assertIsInstance(adapter, NovelCenterAdapter)
        self.assertEqual(adapter.name, "NovelCenter")

    def test_generic_adapter_prepare(self):
        """Tests file discovery and task preparation in GenericDatasetAdapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            timepoint_dir = tmppath / "DatasetA" / "Patient01" / "TP1"
            timepoint_dir.mkdir(parents=True)
            output_root = tmppath / "out"

            # Create dummy NIfTI files
            (timepoint_dir / "Patient01_TP1_T1.nii.gz").touch()
            (timepoint_dir / "Patient01_TP1_T2.nii.gz").touch()
            (timepoint_dir / "Patient01_TP1_FLAIR.nii.gz").touch()
            (timepoint_dir / "Patient01_TP1_MASK.nii.gz").touch()

            ctx = TaskContext(
                dataset_name="DatasetA",
                patient_id="Patient01",
                timepoint_id="TP1",
                timepoint_dir=timepoint_dir,
                dataset_dir=tmppath / "DatasetA",
                output_root=output_root,
            )

            adapter = GenericDatasetAdapter()
            logger = Logger(verbose=False)
            prepared = adapter.prepare(ctx, logger)

            self.assertFalse(prepared.should_skip)
            kwargs = prepared.pipeline_kwargs
            self.assertIn("flair_file", kwargs)
            self.assertIn("t1_file", kwargs)
            self.assertIn("t2_file", kwargs)
            self.assertIn("gt_file", kwargs)
            self.assertEqual(kwargs["enabled_steps"], ["bet", "flirt", "n4"])
            self.assertEqual(kwargs["gt_ref"], "FLAIR")


if __name__ == "__main__":
    unittest.main()
