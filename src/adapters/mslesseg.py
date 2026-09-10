"""
Adapter for the MSLesSeg dataset.

Characteristics:
- Authors provide pre-calculated transformation matrices (.mat) mapping raw scans to MNI space.
- The pipeline executes: FLIRT (with pre-calculated matrices) -> BET -> N4.
- The Ground Truth mask is already defined in MNI space, so it is directly copied
  without redundant re-sampling.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger, find_file


@DatasetRegistry.register
class MSLesSegAdapter(BaseDatasetAdapter):
    """Adapter for MSLesSeg dataset."""

    name: str = "MSLesSeg"
    description: str = "Pre-calculated MNI matrices (FLIRT -> BET -> N4) + direct GT copy"

    def match(self, dataset_name: str) -> bool:
        return "mslesseg" in dataset_name.lower()

    def _find_matrix(self, modality: str, ctx: TaskContext) -> Optional[str]:
        """Looks for pre-calculated matrix in timepoint directory or support directory."""
        mod = modality.lower()
        patterns = [f"*{mod}*matrix*.mat", f"*matrix*{mod}*.mat", f"*{mod}*.mat"]

        # 1. Search in timepoint directory
        for pat in patterns:
            found = find_file(ctx.timepoint_dir, pat)
            if found:
                return found

        # 2. Search in support directory (e.g. Datasets_raw/MSLesSeg/support_MSLesSeg/...)
        support_dirs = [
            ctx.dataset_dir / "support_MSLesSeg",
            ctx.dataset_dir / "support",
        ]
        for sdir in support_dirs:
            if sdir.is_dir():
                for pat in [
                    f"*{ctx.patient_id}*{ctx.timepoint_id}*{mod}*.mat",
                    f"*{ctx.patient_id}*{mod}*.mat",
                    *patterns
                ]:
                    found = find_file(sdir, pat)
                    if found:
                        return found

        return None

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        files = self.find_files(ctx)
        t1_raw = files.get("T1")
        t2_raw = files.get("T2")
        flair_raw = files.get("FLAIR")
        gt_raw = files.get("MASK")

        if not flair_raw:
            return PreparedTask(should_skip=True, skip_reason="Missing essential FLAIR image")

        ctx.target_output_dir.mkdir(parents=True, exist_ok=True)

        flair_mat = self._find_matrix("flair", ctx)
        t1_mat = self._find_matrix("t1", ctx) if not ctx.flair_only else None
        t2_mat = self._find_matrix("t2", ctx) if not ctx.flair_only else None

        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "matrix_flair": flair_mat,
            "t1_file": None if ctx.flair_only else t1_raw,
            "matrix_t1": t1_mat,
            "t2_file": None if ctx.flair_only else t2_raw,
            "matrix_t2": t2_mat,
            "gt_file": None,  # Handled directly in postprocess
            "prefix": ctx.file_prefix,
            "enabled_steps": ["flirt", "bet", "n4"],
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(pipeline_kwargs=pipeline_kwargs)

    def postprocess(self, ctx: TaskContext, pipeline_result: dict, logger: Logger):
        """Copies Ground Truth directly to output directory as it is already in MNI space."""
        files = self.find_files(ctx)
        gt_raw = files.get("MASK")
        if gt_raw:
            dest_gt = ctx.target_output_dir / f"{ctx.file_prefix}MASK.nii.gz"
            logger.log(f"[{ctx.task_id}] [GT] Direct copy of Ground Truth (MSLesSeg MNI space): {dest_gt.name}")
            shutil.copy2(gt_raw, dest_gt)
            pipeline_result["GT"] = str(dest_gt)
