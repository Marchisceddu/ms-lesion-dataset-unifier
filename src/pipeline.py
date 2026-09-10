"""
Dataset-wide parallel harmonization pipeline for MS MRI datasets.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from . import processing
from .adapters import DatasetRegistry, TaskContext
from .utils import Logger, clean_temp_files


def process_single_task(task_context_dict: Dict) -> bool:
    """
    Executes the standardization pipeline for a single timepoint / patient.
    Called by worker processes in parallel execution.
    """
    ctx = TaskContext(
        dataset_name=task_context_dict["dataset_name"],
        patient_id=task_context_dict["patient_id"],
        timepoint_id=task_context_dict["timepoint_id"],
        timepoint_dir=Path(task_context_dict["timepoint_dir"]),
        dataset_dir=Path(task_context_dict["dataset_dir"]),
        output_root=Path(task_context_dict["output_root"]),
        verbose=task_context_dict["verbose"],
        flair_only=task_context_dict["flair_only"],
        keep_intermediates=task_context_dict["keep_intermediates"],
    )

    logger = Logger(progress_bar=None, verbose=ctx.verbose)

    try:
        adapter = DatasetRegistry.get_adapter(ctx.dataset_name)
        logger.log(f"[{ctx.task_id}] Using adapter: {adapter.name} ({adapter.description})")

        prepared = adapter.prepare(ctx, logger)
        if prepared.should_skip:
            logger.info(f"[{ctx.task_id}] [SKIP] {prepared.skip_reason}")
            return False

        # Execute core processing steps
        results = processing.run_pipeline(**prepared.pipeline_kwargs)

        # Dataset-specific post-processing hook
        adapter.postprocess(ctx, results, logger)

        # Cleanup any temporary files created by pre-alignment
        if not ctx.keep_intermediates:
            clean_temp_files(prepared.temp_files_to_clean, logger)

        return True

    except Exception as e:
        print(f"\n[EXCEPTION] Error processing {ctx.task_id}: {e}", file=sys.stderr)
        return False


def collect_tasks(
    input_dir: Path,
    output_dir: Path,
    verbose: bool = False,
    flair_only: bool = False,
    keep_intermediates: bool = False,
) -> List[Dict]:
    """
    Traverses input_dir to build a list of task configurations.
    Expected hierarchy: input_dir / <Dataset> / <Patient> / <Timepoint> / ...
    """
    tasks: List[Dict] = []

    for dataset_dir in sorted(input_dir.iterdir()):
        if not dataset_dir.is_dir() or dataset_dir.name.startswith("."):
            continue

        dataset_name = dataset_dir.name

        for patient_dir in sorted(dataset_dir.iterdir()):
            if not patient_dir.is_dir() or patient_dir.name.startswith((".", "support")):
                continue

            for timepoint_dir in sorted(patient_dir.iterdir()):
                if not timepoint_dir.is_dir() or timepoint_dir.name.startswith("."):
                    continue

                tasks.append({
                    "dataset_name": dataset_name,
                    "patient_id": patient_dir.name,
                    "timepoint_id": timepoint_dir.name,
                    "timepoint_dir": str(timepoint_dir.resolve()),
                    "dataset_dir": str(dataset_dir.resolve()),
                    "output_root": str(output_dir.resolve()),
                    "verbose": verbose,
                    "flair_only": flair_only,
                    "keep_intermediates": keep_intermediates,
                })

    return tasks


def run(
    input_dir: str,
    output_dir: str,
    workers: int = 1,
    verbose: bool = False,
    flair_only: bool = False,
    keep_intermediates: bool = False,
):
    """
    Main function to execute the harmonization pipeline across all scanned datasets.

    Args:
        input_dir: Root directory containing raw input datasets.
        output_dir: Root directory where processed datasets will be saved.
        workers: Number of parallel worker processes.
        verbose: Verbose logging flag.
        flair_only: Whether to process only FLAIR modality.
        keep_intermediates: Whether to preserve intermediate files.
    """
    logger = Logger(verbose=True)
    processing.check_fsl_installed(logger)

    raw_root = Path(input_dir).resolve()
    out_root = Path(output_dir).resolve()

    if not raw_root.exists():
        raise FileNotFoundError(f"Input directory does not exist: {raw_root}")

    out_root.mkdir(parents=True, exist_ok=True)

    print("======================================================================")
    print(" MS Lesion Dataset Unifier - Standardization Pipeline")
    print("======================================================================")
    print(f"Input Directory  : {raw_root}")
    print(f"Output Directory : {out_root}")
    print(f"Parallel Workers : {workers}")
    print(f"Registered Adapters: {', '.join(DatasetRegistry.list_adapters())}")
    print("----------------------------------------------------------------------")

    all_tasks = collect_tasks(
        raw_root,
        out_root,
        verbose=verbose,
        flair_only=flair_only,
        keep_intermediates=keep_intermediates,
    )

    total_tasks = len(all_tasks)
    if total_tasks == 0:
        print(f"No valid patient timepoint directories found in {raw_root}.")
        print("Please check that the hierarchy is: <Dataset>/<Patient>/<Timepoint>/files")
        return

    print(f"Found {total_tasks} scan(s) across datasets. Starting processing...\n")

    successful_count = 0

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process_single_task, task) for task in all_tasks]
            with tqdm(total=total_tasks, desc="Overall Progress", dynamic_ncols=True) as pbar:
                for future in as_completed(futures):
                    try:
                        if future.result():
                            successful_count += 1
                    except Exception as exc:
                        print(f"Task generated an exception: {exc}", file=sys.stderr)
                    finally:
                        pbar.update(1)
    else:
        with tqdm(all_tasks, desc="Overall Progress", dynamic_ncols=True) as pbar:
            for task in pbar:
                if process_single_task(task):
                    successful_count += 1

    print("\n======================================================================")
    print(f"Processing Complete! Successfully processed: {successful_count}/{total_tasks} scans.")
    print(f"Standardized datasets are located at: {out_root}")
    print("======================================================================")


def build_parser() -> argparse.ArgumentParser:
    """Builds argument parser for the pipeline CLI."""
    parser = argparse.ArgumentParser(
        description="MS Lesion Dataset Unifier: Standardize heterogeneous MS MRI datasets into MNI152 space."
    )
    parser.add_argument("--input_dir", required=True, help="Path to raw datasets root directory")
    parser.add_argument("--output_dir", required=True, help="Destination path for standardized datasets")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, multiprocessing.cpu_count() - 1),
        help=f"Number of parallel workers (default: {max(1, multiprocessing.cpu_count() - 1)})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose step-by-step logging")
    parser.add_argument(
        "--flair_only",
        action="store_true",
        help="Process only FLAIR (and Ground Truth) if multi-modal sequences are unavailable",
    )
    parser.add_argument(
        "--keep_intermediates",
        action="store_true",
        default=False,
        help="Keep intermediate FLIRT/BET files and calculated registration matrices",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    run(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        workers=args.workers,
        verbose=args.verbose,
        flair_only=args.flair_only,
        keep_intermediates=args.keep_intermediates,
    )


if __name__ == "__main__":
    main()