"""
Base classes and registry for dataset-specific adapters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..utils import Logger, find_file


@dataclass
class TaskContext:
    """Encapsulates context information for processing a patient's timepoint."""
    dataset_name: str
    patient_id: str
    timepoint_id: str
    timepoint_dir: Path
    dataset_dir: Path
    output_root: Path
    verbose: bool = False
    flair_only: bool = False
    keep_intermediates: bool = False

    @property
    def task_id(self) -> str:
        return f"{self.dataset_name}/{self.patient_id}/{self.timepoint_id}"

    @property
    def file_prefix(self) -> str:
        return f"{self.patient_id}_{self.timepoint_id}_"

    @property
    def target_output_dir(self) -> Path:
        return self.output_root / self.dataset_name / self.patient_id / self.timepoint_id


@dataclass
class PreparedTask:
    """Contains configured arguments ready to be passed to processing.run_pipeline."""
    pipeline_kwargs: Dict[str, Any] = field(default_factory=dict)
    temp_files_to_clean: List[str] = field(default_factory=list)
    should_skip: bool = False
    skip_reason: str = ""


class BaseDatasetAdapter:
    """
    Abstract base adapter for MS MRI datasets.
    
    Subclasses define matching rules, custom pre-alignment, and pipeline parameters
    for specific datasets.
    """

    name: str = "Base"
    description: str = "Base dataset adapter"

    # Default file glob patterns
    DEFAULT_PATTERNS = {
        "T1": "*T1.nii*",
        "T2": "*T2.nii*",
        "FLAIR": "*FLAIR.nii*",
        "MASK": "*MASK.nii*",
    }

    def match(self, dataset_name: str) -> bool:
        """Determines if this adapter is applicable to the given dataset folder name."""
        return self.name.lower() in dataset_name.lower()

    def find_files(self, ctx: TaskContext) -> Dict[str, Optional[str]]:
        """
        Locates required MRI modalities and mask in the timepoint directory.
        
        Returns:
            Dict mapping 'T1', 'T2', 'FLAIR', 'MASK' to absolute paths (or None).
        """
        return {
            "T1": find_file(ctx.timepoint_dir, self.DEFAULT_PATTERNS["T1"]),
            "T2": find_file(ctx.timepoint_dir, self.DEFAULT_PATTERNS["T2"]),
            "FLAIR": find_file(ctx.timepoint_dir, self.DEFAULT_PATTERNS["FLAIR"]),
            "MASK": find_file(ctx.timepoint_dir, self.DEFAULT_PATTERNS["MASK"]),
        }

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        """
        Prepares and configures pipeline parameters for the task.
        Performs any required pre-alignment or checks.
        """
        raise NotImplementedError("Subclasses must implement prepare().")

    def postprocess(self, ctx: TaskContext, pipeline_result: Dict[str, str], logger: Logger):
        """Hook called after the main processing pipeline completes."""
        pass


class DatasetRegistry:
    """Registry maintaining available dataset adapters and resolving them by name."""

    _adapters: List[Type[BaseDatasetAdapter]] = []
    _default_adapter_cls: Optional[Type[BaseDatasetAdapter]] = None

    @classmethod
    def register(cls, adapter_cls: Type[BaseDatasetAdapter]) -> Type[BaseDatasetAdapter]:
        """Class decorator to register an adapter."""
        if adapter_cls not in cls._adapters:
            cls._adapters.append(adapter_cls)
        return adapter_cls

    @classmethod
    def set_default_adapter(cls, adapter_cls: Type[BaseDatasetAdapter]):
        """Sets the fallback adapter for unmatched datasets."""
        cls._default_adapter_cls = adapter_cls

    @classmethod
    def get_adapter(cls, dataset_name: str) -> BaseDatasetAdapter:
        """
        Returns an instantiated adapter matching the given dataset name.
        Falls back to default generic adapter if no specific adapter matches.
        """
        for adapter_cls in cls._adapters:
            adapter = adapter_cls()
            if adapter.match(dataset_name):
                return adapter

        if cls._default_adapter_cls is not None:
            return cls._default_adapter_cls()

        raise RuntimeError(f"No adapter registered for dataset '{dataset_name}' and no default set.")

    @classmethod
    def list_adapters(cls) -> List[str]:
        """Returns names of all registered adapters."""
        return [a.name for a in cls._adapters]
