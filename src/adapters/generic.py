"""
Generic / Standard MS dataset adapter.

Applies the standard harmonization pipeline:
Skull stripping (BET) -> Affine registration to MNI152 1mm (FLIRT) -> Bias field correction (N4).
Ground Truth masks are registered using FLAIR's matrix with Nearest-Neighbor interpolation.
"""

from __future__ import annotations

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger


class GenericDatasetAdapter(BaseDatasetAdapter):
    """Default adapter applied to any standard MS dataset with T1, T2, FLAIR, MASK."""

    name: str = "Generic"
    description: str = "Standard pipeline: BET -> FLIRT (MNI152) -> N4, FLAIR-aligned GT"

    def match(self, dataset_name: str) -> bool:
        # Generic adapter acts as fallback
        return True

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        files = self.find_files(ctx)
        t1_raw = files.get("T1")
        t2_raw = files.get("T2")
        flair_raw = files.get("FLAIR")
        gt_raw = files.get("MASK")

        if ctx.flair_only:
            if not flair_raw:
                return PreparedTask(should_skip=True, skip_reason="Missing essential FLAIR image")
        else:
            missing = [mod for mod, path in [("T1", t1_raw), ("T2", t2_raw), ("FLAIR", flair_raw)] if not path]
            if missing:
                return PreparedTask(
                    should_skip=True,
                    skip_reason=f"Missing required modality: {', '.join(missing)}"
                )

        ctx.target_output_dir.mkdir(parents=True, exist_ok=True)

        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "prefix": ctx.file_prefix,
            "t1_file": None if ctx.flair_only else t1_raw,
            "t2_file": None if ctx.flair_only else t2_raw,
            "gt_file": gt_raw,
            "gt_ref": "FLAIR",
            "enabled_steps": ["bet", "flirt", "n4"],
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(pipeline_kwargs=pipeline_kwargs)


# Register as default fallback
DatasetRegistry.set_default_adapter(GenericDatasetAdapter)
