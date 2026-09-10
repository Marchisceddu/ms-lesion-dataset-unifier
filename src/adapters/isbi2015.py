"""
Adapter for the ISBI-2015 Longitudinal MS Lesion dataset.

Characteristics:
- Uses preprocessed challenge volumes (already skull-stripped and bias-corrected).
- Only requires affine alignment to MNI152 space: enabled_steps = ['flirt'].
- Uses MNI152 'brain' template override.
- Ground truth mask is transformed using nearest neighbor interpolation based on FLAIR.
"""

from __future__ import annotations

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger


@DatasetRegistry.register
class ISBI2015Adapter(BaseDatasetAdapter):
    """Adapter for ISBI-2015 dataset."""

    name: str = "ISBI-2015"
    description: str = "FLIRT only to MNI152 brain template with nearest-neighbor GT transformation"

    def match(self, dataset_name: str) -> bool:
        norm = dataset_name.lower().replace("_", "-")
        return "isbi-2015" in norm or "isbi2015" in norm or "isbi" in norm

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        files = self.find_files(ctx)
        t1_raw = files.get("T1")
        t2_raw = files.get("T2")
        flair_raw = files.get("FLAIR")
        gt_raw = files.get("MASK")

        if not flair_raw:
            return PreparedTask(should_skip=True, skip_reason="Missing essential FLAIR image")

        ctx.target_output_dir.mkdir(parents=True, exist_ok=True)

        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "t1_file": None if ctx.flair_only else t1_raw,
            "t2_file": None if ctx.flair_only else t2_raw,
            "gt_file": gt_raw,
            "prefix": ctx.file_prefix,
            "align_ref": "FLAIR",
            "enabled_steps": ["flirt"],
            "template_type_override": "brain",
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(pipeline_kwargs=pipeline_kwargs)
