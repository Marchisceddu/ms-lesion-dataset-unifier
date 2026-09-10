"""
CLI utility to run the standardization pipeline on a single subject or timepoint.
Useful for testing, parameter exploration, and debugging individual cases.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import processing
from .utils import Logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the standardization pipeline on a single subject / timepoint."
    )
    parser.add_argument("--output_dir", required=True, help="Destination directory for processed files")
    parser.add_argument("--t1_file", default=None, help="Path to raw T1 NIfTI file")
    parser.add_argument("--t2_file", default=None, help="Path to raw T2 NIfTI file")
    parser.add_argument("--flair_file", default=None, help="Path to raw FLAIR NIfTI file")
    parser.add_argument("--gt_file", default=None, help="Path to Ground Truth lesion mask NIfTI file")
    parser.add_argument(
        "--align_ref",
        default=None,
        choices=["T1", "T2", "FLAIR"],
        help="Reference modality for global alignment (one registration matrix applied to all modalities)",
    )
    parser.add_argument(
        "--gt_ref",
        default=None,
        choices=["T1", "T2", "FLAIR"],
        help="Reference modality whose registration matrix is reused to align the Ground Truth",
    )
    parser.add_argument(
        "--enabled_steps",
        nargs="+",
        default=["bet", "flirt", "n4"],
        choices=["flirt", "bet", "n4"],
        help="Ordered list of steps to execute (default: bet flirt n4)",
    )
    parser.add_argument(
        "--template_type",
        default=None,
        choices=["head", "brain"],
        help="Override MNI152 template type ('head' or 'brain'). Inferred by default.",
    )
    parser.add_argument("--prefix", default="", help="Prefix prepended to output file names")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--keep_intermediates",
        action="store_true",
        default=False,
        help="Keep intermediate files produced by the pipeline steps",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not (args.t1_file or args.t2_file or args.flair_file):
        parser.error("At least one modality (--t1_file, --t2_file, or --flair_file) must be provided.")

    logger = Logger(verbose=True)
    processing.check_fsl_installed(logger)

    print("======================================================================")
    print(" MS Lesion Dataset Unifier - Single Case Processing")
    print("======================================================================")
    print(f"Output Directory : {args.output_dir}")
    print(f"Enabled Steps    : {args.enabled_steps}")
    print(f"Global Align Ref : {args.align_ref or 'None'}")
    print(f"GT Reference     : {args.gt_ref or 'None'}")
    print("----------------------------------------------------------------------")

    final_files = processing.run_pipeline(
        output_dir=args.output_dir,
        t1_file=args.t1_file,
        t2_file=args.t2_file,
        flair_file=args.flair_file,
        gt_file=args.gt_file,
        align_ref=args.align_ref,
        gt_ref=args.gt_ref,
        enabled_steps=args.enabled_steps,
        template_type_override=args.template_type,
        prefix=args.prefix,
        verbose=args.verbose,
        keep_intermediates=args.keep_intermediates,
    )

    print("\nProcessing finished successfully. Generated files:")
    for mod, path in final_files.items():
        print(f"  [{mod}] -> {path}")
    print("======================================================================")


if __name__ == "__main__":
    main()
