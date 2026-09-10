"""
Adapter for the MSSEG-2016 dataset.

Characteristics:
- T1 and T2 acquisitions are not aligned with FLAIR.
- Ground Truth is aligned with the raw FLAIR volume.
- Solution: 6-DOF rigid intra-subject pre-alignment of T1 and T2 onto FLAIR,
  followed by Global Alignment Mode with FLAIR as stereotactic reference.
"""

from __future__ import annotations

from pathlib import Path
from shlex import quote

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger, run_cmd


@DatasetRegistry.register
class MSSEG2016Adapter(BaseDatasetAdapter):
    """Adapter for MSSEG-2016 challenge dataset."""

    name: str = "MSSEG-2016"
    description: str = "Rigid 6-DOF pre-alignment (T1/T2 -> FLAIR) + Global Alignment (FLAIR ref)"

    def match(self, dataset_name: str) -> bool:
        norm = dataset_name.lower().replace("_", "-")
        return "msseg-2016" in norm or "msseg2016" in norm

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
            # FLAIR is already aligned with GT; no T1/T2 pre-alignment required
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
                skip_reason="Missing T1 or T2 modality required for multi-modal MSSEG-2016 alignment"
            )

        logger.log(f"[{ctx.task_id}] [PRE-ALIGN] Registering T1 and T2 onto FLAIR (6 DOF)...")

        t1_align = ctx.target_output_dir / f"{ctx.file_prefix}T1_prealign.nii.gz"
        t2_align = ctx.target_output_dir / f"{ctx.file_prefix}T2_prealign.nii.gz"

        run_cmd(f"flirt -in {quote(t1_raw)} -ref {quote(flair_raw)} -out {quote(str(t1_align))} -dof 6", logger)
        run_cmd(f"flirt -in {quote(t2_raw)} -ref {quote(flair_raw)} -out {quote(str(t2_align))} -dof 6", logger)

        temp_files.extend([str(t1_align), str(t2_align)])

        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "t1_file": str(t1_align),
            "t2_file": str(t2_align),
            "gt_file": gt_raw,
            "prefix": ctx.file_prefix,
            "align_ref": "FLAIR",
            "enabled_steps": ["bet", "flirt", "n4"],
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(
            pipeline_kwargs=pipeline_kwargs,
            temp_files_to_clean=temp_files
        )
