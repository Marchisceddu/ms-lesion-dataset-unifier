"""
Adapter for the PubMRI dataset.

Characteristics:
- T1 and T2 are co-registered in native space, but T2 has a distinct FOV causing
  direct T2 -> FLAIR registration to be unstable.
- Solution: Calculate 6-DOF registration for T1 -> FLAIR, save the transformation matrix,
  and propagate it to T2. Then execute independent MNI registration with GT aligned via FLAIR.
"""

from __future__ import annotations

from pathlib import Path
from shlex import quote

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger, run_cmd


@DatasetRegistry.register
class PubMRIAdapter(BaseDatasetAdapter):
    """Adapter for PubMRI dataset."""

    name: str = "PubMRI"
    description: str = "T1->FLAIR 6-DOF registration propagated to T2 + Independent MNI registration"

    def match(self, dataset_name: str) -> bool:
        return "pubmri" in dataset_name.lower()

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        files = self.find_files(ctx)
        t1_raw = files.get("T1")
        t2_raw = files.get("T2")
        flair_raw = files.get("FLAIR")
        gt_raw = files.get("MASK")

        if not flair_raw:
            return PreparedTask(should_skip=True, skip_reason="Missing essential FLAIR image")

        ctx.target_output_dir.mkdir(parents=True, exist_ok=True)
        temp_files = []

        if ctx.flair_only:
            pipeline_kwargs = {
                "output_dir": str(ctx.target_output_dir),
                "flair_file": flair_raw,
                "prefix": ctx.file_prefix,
                "gt_file": gt_raw,
                "gt_ref": "FLAIR",
                "enabled_steps": ["bet", "flirt", "n4"],
                "verbose": ctx.verbose,
                "keep_intermediates": ctx.keep_intermediates,
            }
            return PreparedTask(pipeline_kwargs=pipeline_kwargs)

        if not (t1_raw and t2_raw):
            return PreparedTask(
                should_skip=True,
                skip_reason="Missing T1 or T2 modality required for PubMRI FOV propagation"
            )

        logger.log(f"[{ctx.task_id}] [PRE-ALIGN] Calculating T1 -> FLAIR matrix and propagating to T2...")

        t1_align = ctx.target_output_dir / f"{ctx.file_prefix}T1_prealign.nii.gz"
        t2_align = ctx.target_output_dir / f"{ctx.file_prefix}T2_prealign.nii.gz"
        t1_to_flair_mat = ctx.target_output_dir / f"{ctx.file_prefix}T1_to_FLAIR.mat"

        # 1. Register T1 -> FLAIR (6 DOF) and save matrix
        run_cmd(
            f"flirt -in {quote(t1_raw)} -ref {quote(flair_raw)} "
            f"-out {quote(str(t1_align))} -omat {quote(str(t1_to_flair_mat))} -dof 6",
            logger
        )

        # 2. Apply computed matrix to T2
        run_cmd(
            f"flirt -in {quote(t2_raw)} -ref {quote(flair_raw)} "
            f"-applyxfm -init {quote(str(t1_to_flair_mat))} -out {quote(str(t2_align))}",
            logger
        )

        # Matrix is temporary
        if t1_to_flair_mat.exists():
            t1_to_flair_mat.unlink()

        temp_files.extend([str(t1_align), str(t2_align)])

        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "t1_file": str(t1_align),
            "t2_file": str(t2_align),
            "gt_file": gt_raw,
            "prefix": ctx.file_prefix,
            "gt_ref": "FLAIR",
            "enabled_steps": ["bet", "flirt", "n4"],
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(
            pipeline_kwargs=pipeline_kwargs,
            temp_files_to_clean=temp_files
        )
