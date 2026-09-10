# MS Lesion Dataset Unifier

A modular, extensible Python framework to standardize and unify multi-source Magnetic Resonance Imaging (MRI) datasets of Multiple Sclerosis (MS) patients into a cohesive stereotactic space (**MNI152 1mm³**).

Designed to aggregate MS Lesion datasets (such as **MSLesSeg**, **MSSEG-2016**, **PubMRI**, **ISBI-2015**, or any novel MS cohort) with minimal configuration.

---

## Table of Contents
1. [Pipeline Overview](#1-pipeline-overview)
2. [Directory Structure](#2-directory-structure)
   - [Input Directory Structure](#input-directory-structure)
   - [Output Directory Structure](#output-directory-structure)
3. [Installation & Requirements](#3-installation--requirements)
4. [Usage](#4-usage)
   - [Batch Processing (Entire Datasets)](#batch-processing-entire-datasets)
   - [Single Scan / Subject Debugging](#single-scan--subject-debugging)
   - [Command-Line Arguments](#command-line-arguments)
5. [Supported Built-in Datasets](#5-supported-built-in-datasets)
6. [How to Add New MS Datasets](#6-how-to-add-new-ms-datasets)
   - [Case 1: Standard MS Dataset (Zero Code)](#case-1-standard-ms-dataset-zero-code)
   - [Case 2: Custom MS Dataset (With Specialized Pre-Alignment or Naming)](#case-2-custom-ms-dataset-with-specialized-pre-alignment-or-naming)
7. [Citation](#7-citation)
8. [License](#8-license)

---

## 1. Pipeline Overview

MRI acquisitions across different medical centers and challenges present significant variability in:
* Resolution, matrix dimensions, and Field of View (FOV)
* Native space orientations and intra-subject misalignment
* Scanner-induced magnetic field inhomogeneities (bias field)
* Ground Truth (GT) lesion delineation spaces

To solve this, the pipeline applies a standardized, 3-stage harmonization flow:

```text
Raw MRI Scans (T1, T2, FLAIR)
  │
  ├── 1. Brain Extraction (FSL BET -R)
  │      └─ Removes non-brain tissues (skull, scalp, neck) with robust center estimation.
  │
  ├── 2. Spatial Registration (FSL FLIRT, 12 DOF)
  │      └─ Affine alignment to MNI152 stereotactic space (1mm³ isotropic resolution).
  │
  ├── 3. Bias Field Correction (SimpleITK N4)
  │      └─ Corrects low-frequency intensity non-uniformity artifacts.
  │
  └── Ground Truth Lesion Mask Alignment
         └─ Registered to MNI152 using Nearest-Neighbor interpolation
            to preserve strict discrete binary labels ({0, 1}) without blurry borders.
```

---

## 2. Directory Structure

### Input Directory Structure
The raw data directory (`Datasets_raw/` by default) must follow the hierarchy: `Dataset -> Patient -> Timepoint -> Files`.

Files are identified by suffix matching (`*T1.nii*`, `*T2.nii*`, `*FLAIR.nii*`, `*MASK.nii*`):

```text
Datasets_raw/
├── MSLesSeg/
│   ├── support_MSLesSeg/            # Optional auxiliary files (e.g. pre-calculated matrices)
│   ├── Patient_01/
│   │   ├── Timepoint_01/
│   │   │   ├── Patient01_TP1_T1.nii.gz
│   │   │   ├── Patient01_TP1_T2.nii.gz
│   │   │   ├── Patient01_TP1_FLAIR.nii.gz
│   │   │   └── Patient01_TP1_MASK.nii.gz
│   │   └── ...
│   └── ...
├── MSSEG-2016/
│   ├── 01/
│   │   ├── timepoint01/
│   │   │   ├── Raw_T1.nii.gz
│   │   │   ├── Raw_T2.nii.gz
│   │   │   ├── Raw_FLAIR.nii.gz
│   │   │   └── Raw_MASK.nii.gz
│   │   └── ...
│   └── ...
├── PubMRI/ ...
├── ISBI-2015/ ...
└── Your_Custom_Dataset/ ...
```

> [!NOTE]
> Directories starting with `.` or `support` are automatically ignored as patient candidates.

### Output Directory Structure
The pipeline produces an identical hierarchy in `Datasets_Processed/`, with unified file naming: `{Patient_ID}_{Timepoint_ID}_{Modality}.nii.gz`:

```text
Datasets_Processed/
├── Dataset_Name/
│   ├── Patient_ID/
│   │   ├── Timepoint_ID/
│   │   │   ├── PatientID_TimepointID_T1.nii.gz
│   │   │   ├── PatientID_TimepointID_T2.nii.gz
│   │   │   ├── PatientID_TimepointID_FLAIR.nii.gz
│   │   │   └── PatientID_TimepointID_MASK.nii.gz
│   │   └── ...
│   └── ...
└── ...
```

---

## 3. Installation & Requirements

### System Requirements
* **FSL (FMRIB Software Library)**: Required for `flirt` and `bet`.
  Ensure `FSLDIR` is set in your environment:
  ```bash
  export FSLDIR=/usr/local/fsl        # or /Users/your_username/fsl
  source $FSLDIR/etc/fslconf/fsl.sh
  export PATH=$PATH:$FSLDIR/bin
  ```
  Verify with: `flirt -version`

### Python Environment
Install Python requirements (Python >= 3.9 recommended):

```bash
git clone https://github.com/Marchisceddu/ms-lesion-dataset-unifier.git
cd ms-lesion-dataset-unifier
pip install -r requirements.txt
```

*(Optional) Install in editable mode:*
```bash
pip install -e .
```

---

## 4. Usage

### Batch Processing (Entire Datasets)
Process all datasets present in the raw folder with parallel multi-core execution:

```bash
# Using main.py
python main.py --input_dir "path/to/Datasets_raw" --output_dir "path/to/Datasets_Processed" --workers 4

# Or using python module
python -m src.pipeline --input_dir "path/to/Datasets_raw" --output_dir "path/to/Datasets_Processed" --workers 4
```

For verbose output during processing:
```bash
python main.py --input_dir "path/to/Datasets_raw" --output_dir "path/to/Datasets_Processed" -v
```

If only FLAIR scans and masks are available:
```bash
python main.py --input_dir "path/to/Datasets_raw" --output_dir "path/to/Datasets_Processed" --flair_only
```

### Single Scan / Subject Debugging
To test or debug the pipeline on an individual subject or timepoint:

```bash
python -m src.process_single \
    --output_dir "./test_output" \
    --flair_file "path/to/flair.nii.gz" \
    --t1_file "path/to/t1.nii.gz" \
    --t2_file "path/to/t2.nii.gz" \
    --gt_file "path/to/mask.nii.gz" \
    --align_ref "FLAIR" \
    --prefix "Patient01_TP1_" \
    -v
```

### Command-Line Arguments

#### `main.py` / `src.pipeline`
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--input_dir` | `str` | **Required** | Root directory containing raw input datasets. |
| `--output_dir` | `str` | **Required** | Root directory where processed datasets will be saved. |
| `--workers` | `int` | `CPU_COUNT - 1` | Number of parallel worker processes. |
| `-v`, `--verbose` | `flag` | `False` | Enable detailed step-by-step logging. |
| `--flair_only` | `flag` | `False` | Process only FLAIR (and Ground Truth) if T1/T2 are unavailable. |
| `--keep_intermediates` | `flag` | `False` | Retain intermediate per-step NIfTI files and computed `.mat` matrices. |

#### `src.process_single`
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--output_dir` | `str` | **Required** | Output directory for processed images. |
| `--flair_file` | `str` | `None` | Path to raw FLAIR volume. |
| `--t1_file` | `str` | `None` | Path to raw T1 volume. |
| `--t2_file` | `str` | `None` | Path to raw T2 volume. |
| `--gt_file` | `str` | `None` | Path to raw Ground Truth mask volume. |
| `--align_ref` | `str` | `None` | Modality (`T1`, `T2`, `FLAIR`) used for global intra-subject alignment. |
| `--gt_ref` | `str` | `None` | Modality whose matrix is reused to align Ground Truth. |
| `--enabled_steps` | `list` | `['bet', 'flirt', 'n4']` | Ordered sequence of steps (`bet`, `flirt`, `n4`). |
| `--template_type` | `str` | `None` | Override MNI152 template type (`head` or `brain`). |
| `--prefix` | `str` | `""` | Output filename prefix. |

---

## 5. Supported Built-in Datasets

The repository includes pre-configured adapters for major public MS datasets, matching their specific literature protocols:

| Dataset | Matching Rule | Strategy & Protocol |
| :--- | :--- | :--- |
| **Generic** | *Fallback* | Standard sequence: `bet` -> `flirt` (12 DOF MNI152) -> `n4`. Mask aligned using FLAIR transformation. |
| **MSLesSeg** | Folder contains `mslesseg` | Authors provide pre-calculated MNI matrices. Pipeline runs `flirt` (reusing `.mat`) -> `bet` -> `n4`. GT is already in MNI space and is copied directly. |
| **MSSEG-2016** | Folder contains `msseg-2016` or `msseg2016` | T1 and T2 are not native-aligned with FLAIR. Performs 6-DOF rigid intra-subject pre-alignment (T1/T2 -> FLAIR), then Global Alignment (`align_ref="FLAIR"`). |
| **PubMRI** | Folder contains `pubmri` | T2 has different FOV causing direct T2->FLAIR FLIRT to fail. Pipeline computes T1->FLAIR (6 DOF) and propagates the matrix to T2, followed by independent MNI registration. |
| **ISBI-2015** | Folder contains `isbi` or `isbi-2015` | Uses official preprocessed volumes (already skull-stripped). Runs MNI registration with `flirt` only against the MNI152 `brain` template. |

---

## 6. How to Add New MS Datasets

The architecture uses an extensible **Adapter Pattern** with dynamic registration (`DatasetRegistry`).

### Case 1: Standard MS Dataset (Zero Code)
If your new dataset has:
* Standard multi-modal NIfTI files (`*T1.nii*`, `*T2.nii*`, `*FLAIR.nii*`, `*MASK.nii*`)
* Images that are co-registered in native space (or standard clinical acquisition)

**You do NOT need to write any Python code!**
Simply place your dataset under `Datasets_raw/`:
```text
Datasets_raw/
└── HospitalCohort_2026/
    └── Patient_01/
        └── Timepoint_01/
            ├── T1.nii.gz
            ├── T2.nii.gz
            ├── FLAIR.nii.gz
            └── MASK.nii.gz
```
The pipeline automatically falls back to `GenericDatasetAdapter` and processes the data seamlessly.

---

### Case 2: Custom MS Dataset (With Specialized Pre-Alignment or Naming)
If your dataset requires custom logic (e.g. unusual file patterns, a specific pre-alignment step, custom step ordering, or pre-computed matrices), follow these simple steps:

#### Step 1: Create an Adapter File
Create a new file in `src/adapters/` (e.g., `src/adapters/my_new_dataset.py`):

```python
from pathlib import Path
from shlex import quote
from .base import BaseDatasetAdapter, DatasetRegistry, PreparedTask, TaskContext
from ..utils import Logger, find_file, run_cmd


@DatasetRegistry.register
class MyNewDatasetAdapter(BaseDatasetAdapter):
    name = "MyNewDataset"
    description = "Custom adapter for MyNewDataset with rigid co-registration"

    def match(self, dataset_name: str) -> bool:
        """Define how folder names match this adapter."""
        return "mynewdataset" in dataset_name.lower()

    def find_files(self, ctx: TaskContext) -> dict:
        """Override if your dataset uses non-standard file naming."""
        return {
            "T1": find_file(ctx.timepoint_dir, "*_t1_axial*.nii*"),
            "T2": find_file(ctx.timepoint_dir, "*_t2_spin_echo*.nii*"),
            "FLAIR": find_file(ctx.timepoint_dir, "*_flair_3d*.nii*"),
            "MASK": find_file(ctx.timepoint_dir, "*_lesion_gt*.nii*"),
        }

    def prepare(self, ctx: TaskContext, logger: Logger) -> PreparedTask:
        """Custom pre-alignment or pipeline configuration."""
        files = self.find_files(ctx)
        flair_raw = files.get("FLAIR")
        t1_raw = files.get("T1")
        t2_raw = files.get("T2")
        gt_raw = files.get("MASK")

        if not flair_raw:
            return PreparedTask(should_skip=True, skip_reason="Missing essential FLAIR image")

        ctx.target_output_dir.mkdir(parents=True, exist_ok=True)

        # Configure pipeline options
        pipeline_kwargs = {
            "output_dir": str(ctx.target_output_dir),
            "flair_file": flair_raw,
            "t1_file": t1_raw,
            "t2_file": t2_raw,
            "gt_file": gt_raw,
            "prefix": ctx.file_prefix,
            "align_ref": "FLAIR",             # FLAIR registration matrix applied to T1, T2, GT
            "enabled_steps": ["bet", "flirt", "n4"],
            "verbose": ctx.verbose,
            "keep_intermediates": ctx.keep_intermediates,
        }

        return PreparedTask(pipeline_kwargs=pipeline_kwargs)
```

#### Step 2: Export the Adapter
Add one line to `src/adapters/__init__.py`:

```python
from .my_new_dataset import MyNewDatasetAdapter
```

#### Step 3: Run the Pipeline
Place your dataset folder (e.g. `Datasets_raw/MyNewDataset_CohortA/...`) and execute:

```bash
python main.py --input_dir Datasets_raw --output_dir Datasets_Processed
```

The pipeline automatically identifies `MyNewDataset_CohortA`, binds it to `MyNewDatasetAdapter`, and runs your custom protocol!

---

## 7. Citation

If you use this data standardization pipeline or dataset harmonization protocols in your research, please cite:

* **Thesis & Framework Reference**:
  * Marco Pilia, Simone Dessì. *DinoSCGA-Unet: un’architettura cross-dataset per la segmentazione di lesioni da sclerosi multipla*. Università degli Studi di Cagliari, A.A. 2025/2026. Relatore: Dott. Andrea Loddo, Correlatore: Dott. Luca Zedda.

* **Integrated Datasets**:
  * **MSLesSeg**: Guarnera, F., et al. *MSLesSeg: baseline and benchmarking of a new Multiple Sclerosis Lesion Segmentation dataset*. Sci Data 12, 920 (2025).
  * **MSSEG-2016**: Commowick, O., et al. *MSSEG Challenge Proceedings: Multiple Sclerosis Lesions Segmentation Challenge*. MICCAI 2016.
  * **PubMRI**: Lesjak, Ž., et al. *A Novel Public MR Image Dataset of Multiple Sclerosis Patients With Lesion Segmentations Based on Multi-rater Consensus*. Neuroinformatics (2018).
  * **ISBI-2015**: Carass, A., et al. *Longitudinal multiple sclerosis lesion segmentation: Resource and challenge*. NeuroImage 148 (2017).

---

## 8. License

This project is open source and available under the terms of the [MIT License](LICENSE).
Copyright (c) 2026 Marco Pilia, Simone Dessì.

