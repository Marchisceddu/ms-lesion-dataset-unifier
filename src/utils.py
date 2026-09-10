"""
Utility functions and logging helpers for the MS Lesion Dataset Unifier.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union, List


class Logger:
    """Handles conditional logging, supporting progress bars (tqdm) and verbosity."""

    def __init__(self, progress_bar=None, verbose: bool = False):
        self.progress_bar = progress_bar
        self.verbose = verbose

    def log(self, message: str, file=sys.stdout, flush: bool = True):
        """Prints message only if verbose is True."""
        if self.verbose:
            if self.progress_bar:
                self.progress_bar.write(str(message), file=file)
            else:
                print(message, file=file, flush=flush)

    def info(self, message: str, file=sys.stdout, flush: bool = True):
        """Prints informational message (always visible)."""
        if self.progress_bar:
            self.progress_bar.write(str(message), file=file)
        else:
            print(message, file=file, flush=flush)

    def warn(self, message: str, flush: bool = True):
        """Prints warning message."""
        warning_msg = f"[WARNING] {message}"
        if self.progress_bar:
            self.progress_bar.write(warning_msg, file=sys.stderr)
        else:
            print(warning_msg, file=sys.stderr, flush=flush)

    def error(self, message: str, flush: bool = True):
        """Prints error message (always visible)."""
        error_msg = f"[ERROR] {message}"
        if self.progress_bar:
            self.progress_bar.write(error_msg, file=sys.stderr)
        else:
            print(error_msg, file=sys.stderr, flush=flush)


def run_cmd(command: str, logger: Optional[Logger] = None) -> subprocess.CompletedProcess:
    """
    Executes a shell command with error checking.

    Args:
        command: Command string to execute in subshell.
        logger: Optional Logger instance.

    Returns:
        CompletedProcess instance.

    Raises:
        RuntimeError: If command returns a non-zero exit code.
    """
    if logger:
        logger.log(f"[EXEC] $ {command}")

    stdout_dest = None if (logger and logger.verbose) else subprocess.PIPE
    stderr_dest = None if (logger and logger.verbose) else subprocess.PIPE

    result = subprocess.run(
        command,
        shell=True,
        check=False,
        text=True,
        stdout=stdout_dest,
        stderr=stderr_dest
    )

    if result.returncode != 0:
        err_header = f"\nCommand execution failed with exit code {result.returncode}:"
        err_details = f"Command: {command}\nStderr: {result.stderr or 'N/A'}\nStdout: {result.stdout or 'N/A'}"
        if logger:
            logger.error(err_header)
            logger.error(err_details)
        raise RuntimeError(f"{err_header}\n{err_details}")

    return result


def find_file(directory: Union[str, Path], pattern: str) -> Optional[str]:
    """
    Finds the first file matching a glob pattern inside a directory.

    Args:
        directory: Directory path to search in.
        pattern: Glob pattern (e.g. '*T1.nii*', '*MASK.nii*').

    Returns:
        Absolute string path if found, or None.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        return None

    matches = sorted(list(dir_path.glob(pattern)))
    if matches:
        return str(matches[0].resolve())

    # Case-insensitive fallback
    lower_pattern = pattern.lower()
    for item in dir_path.iterdir():
        if item.is_file() and item.name.lower().endswith(lower_pattern.replace("*", "")):
            return str(item.resolve())

    return None


def clean_temp_files(file_list: List[Optional[str]], logger: Optional[Logger] = None):
    """Safely removes temporary files produced during intermediate pipeline stages."""
    if not file_list:
        return

    for f in file_list:
        if not f:
            continue
        p = Path(f)
        if p.exists() and p.is_file():
            try:
                p.unlink()
                if logger:
                    logger.log(f"   [CLEANUP] Removed temporary file: {p.name}")
            except OSError as e:
                if logger:
                    logger.warn(f"Could not remove temporary file {p}: {e}")
