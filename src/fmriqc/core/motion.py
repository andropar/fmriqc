"""Motion loading, FD extraction, and motion provenance helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fmriqc.core.constants import MotionConstants
from fmriqc.io.structures import InputRun, MotionInfo

FMRIPREP_MOTION_COLUMNS = ["rot_x", "rot_y", "rot_z", "trans_x", "trans_y", "trans_z"]


def compute_fd_from_motion_params(params: np.ndarray) -> np.ndarray:
    """Compute Power FD from six rigid-body motion parameters."""
    if params.ndim == 1:
        params = params[None, :]
    if params.shape[1] < 6:
        raise ValueError("Motion parameter file must contain at least 6 columns")

    rot = params[:, :3] * MotionConstants.MC_ROT_RADIUS_MM
    trans = params[:, 3:6]
    motion = np.hstack([rot, trans])
    diffs = np.diff(motion, axis=0, prepend=motion[[0]])
    diffs[0] = 0.0
    return np.sum(np.abs(diffs), axis=1)


def compute_fd_from_fsl_par(path: Path) -> np.ndarray:
    """Load FSL MCFLIRT .par parameters and compute FD."""
    params = np.loadtxt(path)
    return compute_fd_from_motion_params(params)


def load_fd_from_confounds_tsv(path: Path) -> tuple[np.ndarray, MotionInfo]:
    """Load FD from an fMRIPrep-style confounds TSV."""
    warnings: list[str] = []
    df = pd.read_csv(path, sep="\t", skip_blank_lines=False)

    if "framewise_displacement" in df.columns:
        fd = pd.to_numeric(df["framewise_displacement"], errors="coerce").to_numpy(float)
        if len(fd) and np.isnan(fd[0]):
            fd[0] = 0.0
        if np.isnan(fd[1:]).any():
            warnings.append("Confounds FD contains NaNs after the first volume")
        return fd, MotionInfo(
            path=path,
            source="provided_confounds",
            fd_source="framewise_displacement_column",
            warnings=warnings,
        )

    if all(column in df.columns for column in FMRIPREP_MOTION_COLUMNS):
        params = df[FMRIPREP_MOTION_COLUMNS].apply(pd.to_numeric, errors="coerce").to_numpy(float)
        if np.isnan(params).any():
            warnings.append("Motion columns contain NaNs; FD may contain NaNs")
        fd = compute_fd_from_motion_params(params)
        return fd, MotionInfo(
            path=path,
            source="provided_confounds",
            fd_source="computed_from_6params",
            warnings=warnings,
        )

    warnings.append("Confounds file has no framewise_displacement or six motion columns")
    return np.array([], dtype=float), MotionInfo(
        path=path,
        source="provided_confounds",
        fd_source="none",
        warnings=warnings,
    )


def load_fd_series(
    path: Path,
    *,
    generated: bool = False,
    diagnostic_only: bool = False,
) -> tuple[np.ndarray, MotionInfo]:
    """Load FD from a supported motion file and return provenance."""
    path = Path(path)
    if path.suffix == ".tsv" or path.name.endswith(".tsv"):
        fd, info = load_fd_from_confounds_tsv(path)
        info.diagnostic_only = diagnostic_only
        return fd, info

    fd = compute_fd_from_fsl_par(path)
    source = "generated_from_snapshot_mcflirt" if generated else "provided_fsl_par"
    return fd, MotionInfo(
        path=path,
        source=source,
        fd_source="computed_from_6params",
        generated=generated,
        diagnostic_only=diagnostic_only,
    )


def has_usable_motion(input_run: InputRun) -> bool:
    """Return true when an InputRun points to an existing supported motion input."""
    for path in (input_run.confounds_path, input_run.motion_path):
        if path is not None and Path(path).exists():
            return True
    return False


def choose_motion_path(input_run: InputRun) -> Path | None:
    """Prefer confounds over motion when both are provided."""
    if input_run.confounds_path is not None:
        return input_run.confounds_path
    return input_run.motion_path
