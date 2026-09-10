"""
Core MRI image processing routines (FLIRT registration, BET skull-stripping, N4 bias correction).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from shlex import quote
from typing import Dict, List, Optional, Tuple

from .utils import Logger, run_cmd


def check_fsl_installed(logger: Optional[Logger] = None):
    """
    Checks if FSLDIR environment variable is defined and flirt/bet executables are accessible.

    Raises:
        EnvironmentError: If FSL is not properly configured.
    """
    if "FSLDIR" not in os.environ:
        msg = (
            "FSLDIR environment variable is not set. "
            "Please install FSL and configure FSLDIR (e.g. export FSLDIR=/usr/local/fsl)."
        )
        if logger:
            logger.error(msg)
        raise EnvironmentError(msg)

    # Verify that flirt executable can be executed
    result = subprocess.run("flirt -version", shell=True, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        msg = (
            "FSL 'flirt' command was not found in PATH or failed to execute. "
            "Ensure '$FSLDIR/bin' (or '$FSLDIR/share/fsl/bin') is in your PATH."
        )
        if logger:
            logger.error(msg)
        raise EnvironmentError(msg)


def get_fsl_standard(logger: Optional[Logger] = None, res: str = "1mm", template_type: str = "head") -> str:
    """
    Retrieves the absolute path to the standard MNI152 template provided by FSL.

    Args:
        logger: Optional Logger instance.
        res: Resolution string, typically '1mm' or '2mm'.
        template_type: Either 'head' (full head) or 'brain' (skull-stripped brain).

    Returns:
        Absolute string path to standard MNI152 template.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    fsl_dir = Path(os.environ["FSLDIR"])

    if template_type == "brain":
        template_name = f"MNI152_T1_{res}_brain.nii.gz"
    else:
        template_name = f"MNI152_T1_{res}.nii.gz"

    candidate_paths = [
        fsl_dir / "data" / "standard" / template_name,
        fsl_dir / "share" / "fsl" / "data" / "standard" / template_name,
    ]

    for standard_template in candidate_paths:
        if standard_template.exists():
            return str(standard_template.resolve())

    err_msg = f"Standard MNI template not found. Checked: {[str(p) for p in candidate_paths]}"
    if logger:
        logger.error(err_msg)
    raise FileNotFoundError(err_msg)


def run_n4_bias_correction(input_image_path: str, output_image_path: str, logger: Optional[Logger] = None):
    """
    Applies N4 Bias Field Correction using SimpleITK with foreground binary masking.

    Args:
        input_image_path: Path to input NIfTI volume.
        output_image_path: Path where corrected NIfTI volume will be written.
        logger: Optional Logger instance.
    """
    try:
        import SimpleITK as sitk
    except ImportError as e:
        err = (
            "SimpleITK is required for N4 bias correction. "
            "Please install it using: pip install SimpleITK"
        )
        if logger:
            logger.error(err)
        raise ImportError(err) from e

    if logger:
        logger.log(f"   [N4] Running N4 Bias Correction for {Path(input_image_path).name}...")

    try:
        image = sitk.ReadImage(str(input_image_path), sitk.sitkFloat32)
        # Create binary mask for non-background brain tissue (threshold > 1e-5)
        mask_image = sitk.BinaryThreshold(image, lowerThreshold=1e-5, upperThreshold=1e9)

        corrector = sitk.N4BiasFieldCorrectionImageFilter()
        corrected_image = corrector.Execute(image, mask_image)

        sitk.WriteImage(corrected_image, str(output_image_path))
    except Exception as e:
        if logger:
            logger.error(f"Error during N4 Bias Correction on {input_image_path}: {e}")
        raise


def process_single_image(
    input_file: str,
    modality_name: str,
    standard_ref: str,
    out_path: Path,
    matrix_file: Optional[str] = None,
    calculated_mat_path: Optional[Path] = None,
    enabled_steps: Optional[List[str]] = None,
    prefix: str = "",
    logger: Optional[Logger] = None,
) -> Tuple[str, List[str]]:
    """
    Executes a sequence of operations ('bet', 'flirt', 'n4') for a single image modality.

    Args:
        input_file: Path to input file.
        modality_name: Modality tag (e.g. 'T1', 'T2', 'FLAIR').
        standard_ref: Path to standard reference template (MNI152).
        out_path: Destination directory.
        matrix_file: Pre-existing transformation matrix to apply in FLIRT (if any).
        calculated_mat_path: Path to save newly estimated FLIRT matrix.
        enabled_steps: List and order of steps to execute (default: ['bet', 'flirt', 'n4']).
        prefix: Prefix for output filename.
        logger: Logger instance.

    Returns:
        Tuple: (final_output_path, intermediate_files_to_cleanup)
    """
    if logger is None:
        logger = Logger()

    if enabled_steps is None:
        enabled_steps = ["bet", "flirt", "n4"]

    logger.log(f"--- Processing {modality_name} with steps: {enabled_steps} ---")

    intermediate_files: List[str] = []
    current_step_input = input_file
    step_count = len(enabled_steps)

    if step_count == 0:
        logger.log(f"No steps specified for {modality_name}. Returning input file.")
        return input_file, []

    final_output_path = str(out_path / f"{prefix}{modality_name}.nii.gz")

    for i, step_name in enumerate(enabled_steps):
        is_last_step = (i == step_count - 1)
        if is_last_step:
            current_step_output = final_output_path
        else:
            current_step_output = str(out_path / f"{prefix}{modality_name}_temp_step_{i+1}_{step_name}.nii.gz")
            intermediate_files.append(current_step_output)

        if step_name == "flirt":
            logger.log(f"   [FLIRT] Step {i+1}/{step_count}: Running registration for {modality_name}")
            if matrix_file:
                mat_path = Path(matrix_file)
                if not mat_path.exists():
                    raise FileNotFoundError(f"Matrix file for {modality_name} not found: {matrix_file}")
                cmd = (
                    f"flirt -in {quote(current_step_input)} -ref {quote(standard_ref)} "
                    f"-applyxfm -init {quote(str(mat_path))} -out {quote(current_step_output)}"
                )
            else:
                if calculated_mat_path is None:
                    calculated_mat_path = out_path / f"{modality_name}_to_mni.mat"
                cmd = (
                    f"flirt -in {quote(current_step_input)} -ref {quote(standard_ref)} "
                    f"-out {quote(current_step_output)} -omat {quote(str(calculated_mat_path))} "
                    f"-cost corratio -dof 12"
                )
            run_cmd(cmd, logger)

        elif step_name == "bet":
            logger.log(f"   [BET] Step {i+1}/{step_count}: Running brain extraction (skull stripping) for {modality_name}")
            cmd = f"bet {quote(current_step_input)} {quote(current_step_output)} -R"
            run_cmd(cmd, logger)

        elif step_name == "n4":
            logger.log(f"   [N4] Step {i+1}/{step_count}: Running bias field correction for {modality_name}")
            run_n4_bias_correction(
                input_image_path=current_step_input,
                output_image_path=current_step_output,
                logger=logger
            )

        else:
            logger.warn(f"Unrecognized processing step '{step_name}'. Skipping.")
            continue

        current_step_input = current_step_output

    return final_output_path, intermediate_files


def run_pipeline(
    output_dir: str,
    t1_file: Optional[str] = None,
    matrix_t1: Optional[str] = None,
    t2_file: Optional[str] = None,
    matrix_t2: Optional[str] = None,
    flair_file: Optional[str] = None,
    matrix_flair: Optional[str] = None,
    gt_file: Optional[str] = None,
    align_ref: Optional[str] = None,
    gt_ref: Optional[str] = None,
    enabled_steps: Optional[List[str]] = None,
    template_type_override: Optional[str] = None,
    prefix: str = "",
    progress_bar=None,
    verbose: bool = False,
    keep_intermediates: bool = False,
) -> Dict[str, str]:
    """
    Coordinates the full MRI preprocessing pipeline for a single subject / timepoint.

    Args:
        output_dir: Output directory where standardized files will be written.
        t1_file: Path to T1 NIfTI image.
        matrix_t1: Precomputed T1 -> MNI matrix path.
        t2_file: Path to T2 NIfTI image.
        matrix_t2: Precomputed T2 -> MNI matrix path.
        flair_file: Path to FLAIR NIfTI image.
        matrix_flair: Precomputed FLAIR -> MNI matrix path.
        gt_file: Path to Ground Truth lesion mask NIfTI.
        align_ref: Reference modality for global intra-subject alignment ('T1', 'T2', 'FLAIR').
        gt_ref: Reference modality for GT transformation ('T1', 'T2', 'FLAIR').
        enabled_steps: Steps to execute in order (e.g. ['bet', 'flirt', 'n4']).
        template_type_override: Force 'head' or 'brain' MNI152 template.
        prefix: Prefix for output files (e.g. '{patient}_{timepoint}_').
        progress_bar: Optional tqdm progress bar.
        verbose: Verbose logging flag.
        keep_intermediates: If True, intermediate step files and matrices are preserved.

    Returns:
        Dict mapping modality names ('T1', 'T2', 'FLAIR', 'GT') to their final output paths.
    """
    logger = Logger(progress_bar, verbose)

    if enabled_steps is None:
        enabled_steps = ["bet", "flirt", "n4"]

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Determine reference template: 'brain' if skull-stripping (bet) precedes flirt; otherwise 'head'
    template_to_use = "head"
    if template_type_override in {"head", "brain"}:
        template_to_use = template_type_override
        logger.log(f"Using template override: MNI152 '{template_to_use}' template.")
    elif "flirt" in enabled_steps:
        flirt_idx = enabled_steps.index("flirt")
        if "bet" in enabled_steps and enabled_steps.index("bet") < flirt_idx:
            template_to_use = "brain"
            logger.log("Brain extraction ('bet') precedes 'flirt': selecting MNI152 'brain' template.")
        else:
            template_to_use = "head"
            logger.log("Selecting MNI152 'head' template.")

    standard_ref = get_fsl_standard(logger, res="1mm", template_type=template_to_use)

    final_output_files: Dict[str, str] = {}
    all_intermediate_files: List[str] = []

    # Paths for newly calculated matrices
    t1_calc_mat = out_path / f"{prefix}T1_to_mni.mat"
    t2_calc_mat = out_path / f"{prefix}T2_to_mni.mat"
    flair_calc_mat = out_path / f"{prefix}FLAIR_to_mni.mat"

    t1_matrix_to_use = matrix_t1
    t2_matrix_to_use = matrix_t2
    flair_matrix_to_use = matrix_flair

    gt_transform_to_use: Optional[Path] = None
    ref_name_for_print = "N/A"

    processing_order: List[str] = []
    if t1_file:
        processing_order.append("T1")
    if t2_file:
        processing_order.append("T2")
    if flair_file:
        processing_order.append("FLAIR")

    if align_ref:
        logger.log(f"Global Alignment Mode active: Reference = {align_ref}")
        ref_name_for_print = align_ref
        if align_ref == "T1":
            ref_mat = Path(matrix_t1) if matrix_t1 else t1_calc_mat
            if t2_file:
                t2_matrix_to_use = str(ref_mat)
            if flair_file:
                flair_matrix_to_use = str(ref_mat)
        elif align_ref == "T2":
            ref_mat = Path(matrix_t2) if matrix_t2 else t2_calc_mat
            if t1_file:
                t1_matrix_to_use = str(ref_mat)
            if flair_file:
                flair_matrix_to_use = str(ref_mat)
        elif align_ref == "FLAIR":
            ref_mat = Path(matrix_flair) if matrix_flair else flair_calc_mat
            if t1_file:
                t1_matrix_to_use = str(ref_mat)
            if t2_file:
                t2_matrix_to_use = str(ref_mat)
        else:
            raise ValueError(f"Invalid align_ref '{align_ref}'. Expected 'T1', 'T2', or 'FLAIR'.")

        if gt_file:
            gt_transform_to_use = ref_mat

        # Ensure reference modality is processed first so its matrix is computed first
        if align_ref in processing_order:
            processing_order.insert(0, processing_order.pop(processing_order.index(align_ref)))

    elif gt_ref:
        logger.log(f"GT Reference Mode active: Reference = {gt_ref}")
        ref_name_for_print = gt_ref
        if gt_ref == "T1":
            gt_transform_to_use = Path(matrix_t1) if matrix_t1 else t1_calc_mat
        elif gt_ref == "T2":
            gt_transform_to_use = Path(matrix_t2) if matrix_t2 else t2_calc_mat
        elif gt_ref == "FLAIR":
            gt_transform_to_use = Path(matrix_flair) if matrix_flair else flair_calc_mat
        else:
            raise ValueError(f"Invalid gt_ref '{gt_ref}'. Expected 'T1', 'T2', or 'FLAIR'.")

        if gt_ref in processing_order:
            processing_order.insert(0, processing_order.pop(processing_order.index(gt_ref)))
    else:
        logger.log("Independent Modalities Mode active.")
        if gt_file:
            ref_name_for_print = "GT"

    try:
        # Process each modality
        for modality in processing_order:
            if modality == "T1" and t1_file:
                out_f, inter = process_single_image(
                    input_file=t1_file,
                    modality_name="T1",
                    standard_ref=standard_ref,
                    out_path=out_path,
                    matrix_file=t1_matrix_to_use,
                    calculated_mat_path=t1_calc_mat,
                    enabled_steps=enabled_steps,
                    prefix=prefix,
                    logger=logger,
                )
                final_output_files["T1"] = out_f
                all_intermediate_files.extend(inter)

            elif modality == "T2" and t2_file:
                out_f, inter = process_single_image(
                    input_file=t2_file,
                    modality_name="T2",
                    standard_ref=standard_ref,
                    out_path=out_path,
                    matrix_file=t2_matrix_to_use,
                    calculated_mat_path=t2_calc_mat,
                    enabled_steps=enabled_steps,
                    prefix=prefix,
                    logger=logger,
                )
                final_output_files["T2"] = out_f
                all_intermediate_files.extend(inter)

            elif modality == "FLAIR" and flair_file:
                out_f, inter = process_single_image(
                    input_file=flair_file,
                    modality_name="FLAIR",
                    standard_ref=standard_ref,
                    out_path=out_path,
                    matrix_file=flair_matrix_to_use,
                    calculated_mat_path=flair_calc_mat,
                    enabled_steps=enabled_steps,
                    prefix=prefix,
                    logger=logger,
                )
                final_output_files["FLAIR"] = out_f
                all_intermediate_files.extend(inter)

        # Ground Truth processing
        if gt_file:
            gt_path = Path(gt_file)
            if not gt_path.exists():
                raise FileNotFoundError(f"Ground Truth file not found: {gt_file}")

            gt_reg_out = out_path / f"{prefix}MASK.nii.gz"

            if gt_transform_to_use:
                if not gt_transform_to_use.exists():
                    raise FileNotFoundError(
                        f"Registration matrix for GT reference '{ref_name_for_print}' not found: {gt_transform_to_use}"
                    )
                logger.log(f"   [GT] Transforming Ground Truth using {ref_name_for_print} matrix...")
                cmd_gt = (
                    f"flirt -in {quote(str(gt_path))} -ref {quote(standard_ref)} "
                    f"-applyxfm -init {quote(str(gt_transform_to_use))} "
                    f"-out {quote(str(gt_reg_out))} "
                    f"-interp nearestneighbour"
                )
            else:
                logger.log("   [GT] Calculating independent registration for Ground Truth...")
                gt_calc_mat = out_path / f"{prefix}GT_to_mni.mat"
                cmd_gt = (
                    f"flirt -in {quote(str(gt_path))} -ref {quote(standard_ref)} "
                    f"-out {quote(str(gt_reg_out))} -omat {quote(str(gt_calc_mat))} "
                    f"-cost corratio -dof 12 -interp nearestneighbour"
                )
                if not keep_intermediates:
                    all_intermediate_files.append(str(gt_calc_mat))

            run_cmd(cmd_gt, logger)
            final_output_files["GT"] = str(gt_reg_out)

    finally:
        # Cleanup temporary files
        if not keep_intermediates:
            for f in all_intermediate_files:
                p = Path(f)
                if p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            # Clean calculated matrices if they were temporary
            for mat in [t1_calc_mat, t2_calc_mat, flair_calc_mat]:
                if mat.exists():
                    try:
                        mat.unlink()
                    except OSError:
                        pass

    return final_output_files