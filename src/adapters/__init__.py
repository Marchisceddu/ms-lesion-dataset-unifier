"""
Dataset adapters package for MS Lesion Dataset Unifier.
"""

from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from .generic import GenericDatasetAdapter
from .mslesseg import MSLesSegAdapter
from .msseg2016 import MSSEG2016Adapter
from .pubmri import PubMRIAdapter
from .isbi2015 import ISBI2015Adapter

__all__ = [
    "BaseDatasetAdapter",
    "DatasetRegistry",
    "PreparedTask",
    "TaskContext",
    "GenericDatasetAdapter",
    "MSLesSegAdapter",
    "MSSEG2016Adapter",
    "PubMRIAdapter",
    "ISBI2015Adapter",
]
