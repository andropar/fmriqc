"""Computation and saving of aggregate maps and statistics.

This module handles the creation of aggregate maps at subject, session, and
study levels. It also manages asset copying and the generation of hierarchical
reports with proper file organization.
"""

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import nibabel as nib
import numpy as np
from tqdm import tqdm

from .consistency import generate_consistency_report
from .reporting import generate_study_report, generate_subject_report
from .structures import RunResult, StudyResults
from .visualization import create_aggregate_maps_figure


def compute_average_maps(
    run_group: List[RunResult],
) -> Optional[Tuple[Dict[str, np.ndarray], np.ndarray, object]]:
    """Compute average maps across a group of runs.

    Parameters
    ----------
    run_group : List[RunResult]
        Group of runs to average

    Returns
    -------
    Optional[Tuple[Dict[str, np.ndarray], np.ndarray, object]]
        Tuple of (averaged maps dict, affine, header) or None if computation fails
    """
    if not run_group:
        return None

    reference_run = None
    for candidate in run_group:
        if "mean" in candidate.maps:
            reference_run = candidate
            break

    if reference_run is None:
        return None

    ref_shape = reference_run.maps["mean"].shape
    map_keys = [
        key
        for key in ["mean", "tsnr", "cov", "dropout", "ar1"]
        if key in reference_run.maps
    ]
    if not map_keys:
        return None

    accumulators = {key: np.zeros(ref_shape, dtype=np.float64) for key in map_keys}
    included = 0

    for run in run_group:
        if run.maps.get("mean") is None:
            continue
        if run.maps["mean"].shape != ref_shape:
            continue
        missing_key = False
        for key in map_keys:
            if key not in run.maps:
                missing_key = True
                break
        if missing_key:
            continue

        for key in map_keys:
            accumulators[key] += run.maps[key]
        included += 1

    if included == 0:
        return None

    averaged = {key: data / included for key, data in accumulators.items()}
    return averaged, reference_run.affine, reference_run.header


def save_aggregate_level(
    run_group: List[RunResult],
    output_dir: Path,
    prefix: str,
    map_names: List[str],
    compute_average_maps_fn: Callable,
) -> Tuple[Optional[Path], Dict[str, Path]]:
    """Save aggregate maps for a specific level (subject/session/study).

    Consolidates the common pattern of checking cache, computing averages,
    saving NIfTI files, and creating figures for different aggregation levels.

    Parameters
    ----------
    run_group : List[RunResult]
        Group of runs to aggregate
    output_dir : Path
        Directory where aggregate files will be saved
    prefix : str
        Filename prefix (e.g., "sub-01", "sub-01_ses-01", "study")
    map_names : List[str]
        Names of maps to aggregate (e.g., ["mean", "tsnr", "cov", "dropout", "ar1"])
    compute_average_maps_fn : callable
        Function to compute average maps from run_group

    Returns
    -------
    Tuple[Optional[Path], Dict[str, Path]]
        Figure path and dictionary of map name -> NIfTI path, or (None, {}) if failed
    """
    # Define paths
    figure_path = output_dir / f"{prefix}_aggregate_maps.png"
    nifti_paths = {
        name: output_dir / f"{prefix}_aggregate_{name}.nii.gz" for name in map_names
    }

    # Check if aggregate maps already exist (cache hit)
    all_exist = figure_path.exists() and all(p.exists() for p in nifti_paths.values())
    if all_exist:
        return figure_path, nifti_paths

    # Compute aggregate maps if not cached
    computed = compute_average_maps_fn(run_group)
    if computed is None:
        return None, {}

    averaged, affine, header = computed

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save NIfTI files
    map_paths: Dict[str, Path] = {}
    for name, data in averaged.items():
        nifti_path = output_dir / f"{prefix}_aggregate_{name}.nii.gz"
        img = nib.Nifti1Image(data.astype(np.float32), affine, header)
        nib.save(img, nifti_path)
        map_paths[name] = nifti_path

    # Create figure
    figure_path = create_aggregate_maps_figure(
        averaged, output_dir / f"{prefix}_aggregate_maps.png"
    )

    return figure_path, map_paths


def save_aggregate_maps(
    results: List[RunResult], output_dir: Path
) -> Tuple[
    Dict[str, Path],
    Dict[str, Dict[str, Path]],
    Optional[Path],
    Dict[str, Path],
    Dict[str, Path],
    Dict[str, Dict[str, Path]],
]:
    """Save subject-level, session-level, and optional study-level aggregate maps.

    Creates and saves aggregate maps at multiple levels of the study hierarchy,
    including both visualization figures and NIfTI files.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    output_dir : Path
        Output directory

    Returns
    -------
    Tuple containing:
        - Mapping from subject IDs to the path of their aggregate PNG figure.
        - Mapping from subject IDs to a mapping of map name -> NIfTI file path.
        - Optional path to the study-level aggregate PNG figure (if computed).
        - Mapping of study-level map name -> NIfTI file path.
        - Mapping from session identifiers to the path of their aggregate PNG figure.
        - Mapping from session identifiers to a mapping of map name -> NIfTI file path.
    """

    if not results:
        return {}, {}, None, {}, {}, {}

    aggregate_root = output_dir / "aggregate_maps"
    aggregate_root.mkdir(parents=True, exist_ok=True)

    subject_groups: Dict[str, List[RunResult]] = defaultdict(list)
    for res in results:
        subject_groups[res.info.subject].append(res)

    subject_figures: Dict[str, Path] = {}
    subject_map_paths: Dict[str, Dict[str, Path]] = {}

    session_figures: Dict[str, Path] = {}
    session_map_paths: Dict[str, Dict[str, Path]] = {}
    session_groups: Dict[str, List[RunResult]] = defaultdict(list)

    for res in results:
        session_key = f"{res.info.subject}_{res.info.session}"
        session_groups[session_key].append(res)

    map_names = ["mean", "tsnr", "cov", "dropout", "ar1"]

    # Subject-level aggregates
    for subject_id, run_group in subject_groups.items():
        subject_dir = aggregate_root / f"sub-{subject_id}"
        figure_path, map_paths = save_aggregate_level(
            run_group, subject_dir, f"sub-{subject_id}", map_names, compute_average_maps
        )
        if figure_path:
            subject_figures[subject_id] = figure_path
            subject_map_paths[subject_id] = map_paths

    # Session-level aggregates
    for session_key, session_runs in session_groups.items():
        subject_id, session_id = session_key.split("_", 1)
        session_dir = aggregate_root / f"sub-{subject_id}" / f"ses-{session_id}"
        figure_path, map_paths = save_aggregate_level(
            session_runs,
            session_dir,
            f"sub-{subject_id}_ses-{session_id}",
            map_names,
            compute_average_maps,
        )
        if figure_path:
            session_figures[session_key] = figure_path
            session_map_paths[session_key] = map_paths

    # Optional study-wide aggregates
    overall_figure, overall_paths = save_aggregate_level(
        results, aggregate_root, "study", map_names, compute_average_maps
    )

    return (
        subject_figures,
        subject_map_paths,
        overall_figure,
        overall_paths,
        session_figures,
        session_map_paths,
    )


def copy_and_update_asset(
    source_path: Optional[Path], target_path: Path, asset_type: str = "asset"
) -> Optional[Path]:
    """Copy an asset file and return the target path.

    Consolidates the common pattern of copying figures, carpetplots, and other
    assets while handling errors gracefully.

    Parameters
    ----------
    source_path : Optional[Path]
        Source file path to copy from. If None or doesn't exist, returns None.
    target_path : Path
        Destination path to copy to.
    asset_type : str, optional
        Type of asset for logging purposes (default: "asset").

    Returns
    -------
    Optional[Path]
        Target path if copy successful or paths are identical, None otherwise.

    Examples
    --------
    >>> new_path = copy_and_update_asset(run.figure_path, session_dir / "figure.png", "run figure")
    >>> if new_path:
    ...     run.figure_path = new_path
    """
    if source_path is None or not source_path.exists():
        return None

    if not source_path.is_file():
        return None

    # If paths are already the same, no need to copy
    if source_path == target_path:
        return target_path

    try:
        # Check if target exists and is a directory (shouldn't happen, but be safe)
        if target_path.exists() and target_path.is_dir():
            print(f"Warning: Target path is a directory, skipping: {target_path}")
            return None

        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        shutil.copy2(source_path, target_path)
        return target_path
    except Exception as e:
        print(f"Warning: Could not copy {asset_type}: {e}")
        return None


def assign_aggregate_paths(
    results: List[RunResult],
    output_dir: Path,
    study: StudyResults,
) -> None:
    """Assign aggregate map paths to study structure.

    Creates aggregate maps at subject, session, and study levels, then
    assigns the resulting figure and map paths to the appropriate objects
    in the study hierarchy.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    output_dir : Path
        Output directory
    study : StudyResults
        Study results object to update with paths
    """
    print("Creating aggregate maps...")
    (
        subject_figures,
        subject_map_paths,
        study_aggregate_path,
        study_map_paths,
        session_figures,
        session_map_paths,
    ) = save_aggregate_maps(results, output_dir)

    subject_lookup = {subject.subject: subject for subject in study.subjects}
    for subject_id, figure_path in subject_figures.items():
        if subject_id in subject_lookup:
            subject_lookup[subject_id].aggregate_figure_path = figure_path
    for subject_id, map_paths in subject_map_paths.items():
        if subject_id in subject_lookup:
            subject_lookup[subject_id].aggregate_map_paths = map_paths.copy()

    # Assign session aggregates
    for session_key, figure_path in session_figures.items():
        subject_id, session_id = session_key.split("_", 1)
        if subject_id in subject_lookup:
            subject = subject_lookup[subject_id]
            for session in subject.sessions:
                if session.session == session_id:
                    session.aggregate_figure_path = figure_path
                    if session_key in session_map_paths:
                        session.aggregate_map_paths = session_map_paths[
                            session_key
                        ].copy()
                    break

    study.aggregate_figure_path = study_aggregate_path
    study.aggregate_map_paths = study_map_paths


def generate_hierarchical_reports(
    study: StudyResults,
    output_dir: Path,
    study_aggregate_path: Optional[Path] = None,
) -> None:
    """Generate hierarchical HTML reports.

    Creates a hierarchical directory structure with reports at study, subject,
    and session levels. Handles copying of figures and assets to appropriate
    locations.

    Parameters
    ----------
    study : StudyResults
        Study results object
    output_dir : Path
        Output directory
    study_aggregate_path : Path, optional
        Path to study-level aggregate figure
    """
    print("Generating hierarchical reports...")

    # Generate reports for each level
    for subject in tqdm(study.subjects, desc="Subjects"):
        subject_dir = output_dir / f"sub-{subject.subject}"
        subject_dir.mkdir(parents=True, exist_ok=True)

        aggregates_dir = subject_dir / "aggregates"
        if subject.aggregate_figure_path or subject.aggregate_map_paths:
            aggregates_dir.mkdir(exist_ok=True)

            if subject.aggregate_figure_path:
                target_figure = aggregates_dir / subject.aggregate_figure_path.name
                new_path = copy_and_update_asset(
                    subject.aggregate_figure_path,
                    target_figure,
                    "subject aggregate figure",
                )
                if new_path:
                    subject.aggregate_figure_path = new_path

            if subject.aggregate_map_paths:
                copied_maps: Dict[str, Path] = {}
                for map_name, map_path in subject.aggregate_map_paths.items():
                    target_map = aggregates_dir / map_path.name
                    new_path = copy_and_update_asset(
                        map_path, target_map, f"subject aggregate map '{map_name}'"
                    )
                    if new_path:
                        copied_maps[map_name] = new_path
                if copied_maps:
                    subject.aggregate_map_paths = copied_maps

        session_consistency: Dict[str, Dict] = {}
        for session in subject.sessions:
            session_dir = subject_dir / f"ses-{session.session}"
            session_dir.mkdir(parents=True, exist_ok=True)

            # Generate consistency report for session
            consistency_report = generate_consistency_report(session)
            consistency_path = session_dir / "consistency_metrics.json"
            with open(consistency_path, "w") as f:
                json.dump(consistency_report, f, indent=2)
            session_consistency[session.session] = consistency_report

            # Copy/move run figures to session directory
            for run in session.runs:
                # Copy figure if it exists
                if run.figure_path:
                    # Use run identifier in filename to avoid conflicts with directories
                    run_label = run.info.run.replace("run-", "").replace("_", "-")
                    # Preserve original extension
                    ext = run.figure_path.suffix or ".png"
                    safe_name = f"sub-{subject.subject}_ses-{session.session}_{run_label}_qa_figure{ext}"
                    new_figure_path = session_dir / safe_name
                    new_path = copy_and_update_asset(
                        run.figure_path, new_figure_path, "run figure"
                    )
                    if new_path:
                        run.figure_path = new_path

                # Copy carpetplot if it exists
                if run.carpetplot_path:
                    # Use run identifier in filename to avoid conflicts with directories
                    run_label = run.info.run.replace("run-", "").replace("_", "-")
                    # Preserve original extension
                    ext = run.carpetplot_path.suffix or ".png"
                    safe_name = f"sub-{subject.subject}_ses-{session.session}_{run_label}_carpetplot{ext}"
                    new_carpetplot_path = session_dir / safe_name
                    new_path = copy_and_update_asset(
                        run.carpetplot_path, new_carpetplot_path, "run carpetplot"
                    )
                    if new_path:
                        run.carpetplot_path = new_path

        # Generate subject report
        generate_subject_report(subject, subject_dir, session_consistency)

    # Generate study report
    generate_study_report(study, output_dir, study_aggregate_path)
