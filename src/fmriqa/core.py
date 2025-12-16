"""Main QA orchestration and command-line interface."""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import scipy

from joblib import Parallel, delayed
from tqdm import tqdm

from fmriqa.config import QAConfig
from fmriqa.constants import QualityThresholds, StatisticalConstants
from fmriqa.structures import RunResult, SessionResults, SubjectResults, StudyResults
from fmriqa.io import QACache, load_default_derivatives, load_all_results_from_previous_run, find_mask_path, create_run_info, create_run_info_from_manifest
from fmriqa.processing import process_single_run
from fmriqa.manifest import QAManifest, ManifestRun
from fmriqa.outliers import generate_outlier_report
from fmriqa.consistency import generate_consistency_report
from fmriqa.reporting import generate_subject_report, generate_study_report
from fmriqa.visualization import create_aggregate_maps_figure, create_subject_comparison_plot
from fmriqa.exclusions import (
    ExclusionStringency,
    generate_exclusion_report,
    export_exclusion_list,
    export_censor_files,
    generate_methods_text,
)
import nibabel as nib
import re


def _get_session_key(run_path: Path) -> str:
    """Extract subject-session key from run path for grouping."""
    # Parse subject and session from path
    path_str = str(run_path)
    sub_match = re.search(r'sub-([^/\\]+)', path_str)
    ses_match = re.search(r'ses-([^/\\]+)', path_str)
    subject = sub_match.group(1) if sub_match else "unknown"
    session = ses_match.group(1) if ses_match else "unknown"
    return f"{subject}_{session}"


@dataclass
class ManifestRunContext:
    """Context for a run from a manifest (includes mask/motion paths)."""
    bold_path: Path
    subject_id: str
    session_id: str
    run_label: str
    mask_path: Optional[Path] = None
    motion_path: Optional[Path] = None


def _discover_runs_from_manifest(manifest: QAManifest) -> List[ManifestRunContext]:
    """Extract run contexts from a manifest."""
    runs = []
    for subject in manifest.subjects:
        for session in subject.sessions:
            for run in session.runs:
                if run.bold:
                    runs.append(ManifestRunContext(
                        bold_path=run.bold,
                        subject_id=subject.id,
                        session_id=session.id,
                        run_label=run.label,
                        mask_path=run.mask,
                        motion_path=run.motion,
                    ))
    return runs





def organize_results(results: List[RunResult], analysis_metadata: Optional[Dict] = None) -> StudyResults:
    """Organize flat list of results into hierarchical structure."""
    # Group by subject and session
    grouped: Dict[str, Dict[str, List[RunResult]]] = defaultdict(lambda: defaultdict(list))

    for result in results:
        grouped[result.info.subject][result.info.session].append(result)

    # Create hierarchical structure
    subjects = []
    for subject_id in sorted(grouped.keys()):
        sessions = []
        for session_id in sorted(grouped[subject_id].keys()):
            session_runs = grouped[subject_id][session_id]
            sessions.append(SessionResults(
                subject=subject_id,
                session=session_id,
                runs=session_runs
            ))
        subjects.append(SubjectResults(
            subject=subject_id,
            sessions=sessions
        ))

    return StudyResults(subjects=subjects, analysis_metadata=analysis_metadata or {})


def compute_overall_metrics(results: List[RunResult]) -> Dict:
    """Compute overall study metrics."""
    if not results:
        return {}
    
    return {
        "runs": len(results),
        "tsnr_median": float(np.median([r.metrics["tsnr_median"] for r in results])),
        "tsnr_mean": float(np.mean([r.metrics["tsnr_median"] for r in results])),
        "fd_median": float(np.median([r.metrics.get("fd_median", 0) for r in results])),
        "fd_mean": float(np.mean([r.metrics.get("fd_median", 0) for r in results])),
        "dvars_percent_above_mean": float(np.mean([r.metrics["dvars_percent_above"] for r in results])),
        "outlier_percent_above_mean": float(np.mean([r.metrics["outlier_percent_above"] for r in results])),
        "smoothness_mean": float(np.mean([r.metrics["smoothness_fwhm"] for r in results])),
        "gcor_mean": float(np.mean([r.metrics["gcor"] for r in results])),
        "ar1_median": float(np.median([r.metrics["ar1_median"] for r in results])),
    }


def _save_aggregate_level(
    run_group: List[RunResult],
    output_dir: Path,
    prefix: str,
    map_names: List[str],
    compute_average_maps_fn,
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
    nifti_paths = {name: output_dir / f"{prefix}_aggregate_{name}.nii.gz" for name in map_names}

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
) -> Tuple[Dict[str, Path], Dict[str, Dict[str, Path]], Optional[Path], Dict[str, Path], Dict[str, Path], Dict[str, Dict[str, Path]]]:
    """Save subject-level, session-level, and optional study-level aggregate maps.

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

    def _compute_average_maps(run_group: List[RunResult]) -> Optional[Tuple[Dict[str, np.ndarray], np.ndarray, object]]:
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

    session_figures: Dict[str, Path] = {}
    session_map_paths: Dict[str, Dict[str, Path]] = {}
    session_groups: Dict[str, List[RunResult]] = defaultdict(list)
    
    for res in results:
        session_key = f"{res.info.subject}_{res.info.session}"
        session_groups[session_key].append(res)

    map_names = ["mean", "tsnr", "cov", "dropout", "ar1"]
    for subject_id, run_group in subject_groups.items():
        subject_dir = aggregate_root / f"sub-{subject_id}"
        figure_path, map_paths = _save_aggregate_level(
            run_group,
            subject_dir,
            f"sub-{subject_id}",
            map_names,
            _compute_average_maps
        )
        if figure_path:
            subject_figures[subject_id] = figure_path
            subject_map_paths[subject_id] = map_paths

    # Session-level aggregates
    for session_key, session_runs in session_groups.items():
        subject_id, session_id = session_key.split("_", 1)
        session_dir = aggregate_root / f"sub-{subject_id}" / f"ses-{session_id}"
        figure_path, map_paths = _save_aggregate_level(
            session_runs,
            session_dir,
            f"sub-{subject_id}_ses-{session_id}",
            map_names,
            _compute_average_maps
        )
        if figure_path:
            session_figures[session_key] = figure_path
            session_map_paths[session_key] = map_paths

    # Optional study-wide aggregates
    overall_figure, overall_paths = _save_aggregate_level(
        results,
        aggregate_root,
        "study",
        map_names,
        _compute_average_maps
    )

    return subject_figures, subject_map_paths, overall_figure, overall_paths, session_figures, session_map_paths


def _copy_and_update_asset(
    source_path: Optional[Path],
    target_path: Path,
    asset_type: str = "asset"
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
    >>> new_path = _copy_and_update_asset(run.figure_path, session_dir / "figure.png", "run figure")
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


def generate_hierarchical_reports(
    study: StudyResults,
    output_dir: Path,
    study_aggregate_path: Optional[Path] = None,
) -> None:
    """Generate hierarchical HTML reports."""
    import shutil
    
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
                new_path = _copy_and_update_asset(
                    subject.aggregate_figure_path,
                    target_figure,
                    "subject aggregate figure"
                )
                if new_path:
                    subject.aggregate_figure_path = new_path

            if subject.aggregate_map_paths:
                copied_maps: Dict[str, Path] = {}
                for map_name, map_path in subject.aggregate_map_paths.items():
                    target_map = aggregates_dir / map_path.name
                    new_path = _copy_and_update_asset(
                        map_path,
                        target_map,
                        f"subject aggregate map '{map_name}'"
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
            with open(consistency_path, 'w') as f:
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
                    new_path = _copy_and_update_asset(run.figure_path, new_figure_path, "run figure")
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
                    new_path = _copy_and_update_asset(run.carpetplot_path, new_carpetplot_path, "run carpetplot")
                    if new_path:
                        run.carpetplot_path = new_path

        # Generate subject report
        generate_subject_report(subject, subject_dir, session_consistency)
    
    # Generate study report
    generate_study_report(study, output_dir, study_aggregate_path)


def _discover_runs(
    config: QAConfig,
) -> Tuple[List[Path], Dict[Path, ManifestRunContext], Path]:
    """Discover runs from manifest or glob pattern.

    Handles both manifest-based and glob-based run discovery, validating
    inputs and determining the appropriate output directory location.

    Parameters
    ----------
    config : QAConfig
        Configuration object with data source settings

    Returns
    -------
    Tuple[List[Path], Dict[Path, ManifestRunContext], Path]
        - run_paths: List of paths to BOLD files
        - manifest_contexts: Dictionary mapping paths to manifest contexts (empty for glob mode)
        - base_output: Base directory for output

    Raises
    ------
    SystemExit
        If manifest validation fails or no runs are found
    """
    manifest_contexts: Dict[Path, ManifestRunContext] = {}

    # Check for manifest-based input
    if config.is_manifest_mode():
        manifest = config.get_manifest()
        if manifest is None:
            raise SystemExit(f"Could not load manifest from: {config.manifest_path}")

        # Validate manifest
        errors = manifest.validate()
        if errors:
            print("Manifest validation errors:")
            for error in errors[:10]:
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
            raise SystemExit("Manifest validation failed")

        print(f"Data source: manifest ({config.manifest_path})")
        print(manifest.summary())

        # Extract run contexts from manifest
        run_context_list = _discover_runs_from_manifest(manifest)
        run_paths = [ctx.bold_path for ctx in run_context_list]
        manifest_contexts = {ctx.bold_path: ctx for ctx in run_context_list}

        # For manifest mode, output goes next to manifest or in specified dir
        if config.derivatives_dir:
            base_output = config.derivatives_dir
        elif manifest.base_path:
            base_output = manifest.base_path
        else:
            base_output = config.manifest_path.parent

    else:
        # Standard glob-based discovery
        # Determine derivatives directory
        if config.derivatives_dir is None:
            if config.config_file and config.config_file.exists():
                config.derivatives_dir = load_default_derivatives(config.config_file)
            if config.derivatives_dir is None:
                raise SystemExit("Unable to determine derivatives directory")

        config.derivatives_dir = config.derivatives_dir.resolve()
        base_output = config.derivatives_dir

        # Get glob pattern from preset or use explicit pattern
        effective_pattern = config.get_effective_glob_pattern()
        print(f"Data source: {config.data_source}")
        print(f"Using pattern: {effective_pattern}")

        # Find runs
        run_paths = sorted(config.derivatives_dir.glob(effective_pattern))

    if not run_paths:
        if config.is_manifest_mode():
            raise SystemExit("No valid runs found in manifest")
        else:
            raise SystemExit(f"No runs matched the glob pattern: {config.get_effective_glob_pattern()}")

    print(f"Found {len(run_paths)} runs")

    return run_paths, manifest_contexts, base_output


def _setup_output_and_cache(
    config: QAConfig,
    base_output: Path,
    run_paths: List[Path],
) -> Tuple[Path, Optional[QACache], List[Path], Dict[Path, RunResult], int]:
    """Setup output directory and cache system.

    Creates output directory structure, initializes cache, and identifies
    which runs need processing vs can use cached results.

    Parameters
    ----------
    config : QAConfig
        Configuration object
    base_output : Path
        Base directory for output
    run_paths : List[Path]
        List of run paths to process

    Returns
    -------
    Tuple[Path, Optional[QACache], List[Path], Dict[Path, RunResult], int]
        - output_dir: Directory for QA outputs
        - cache: QA cache object (or None if disabled)
        - runs_to_process: List of runs that need processing
        - results_by_path: Dictionary of cached results
        - cached_results_used: Count of cached results
    """
    # Setup output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_output / config.output_dir_name / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    reuse_dir = None

    # Save config
    config.to_yaml(output_dir / "qa_config.yaml")

    # Initialize cache
    print(f"Initializing cache: {output_dir}")
    cache = QACache(output_dir, reuse_dir=reuse_dir) if config.use_cache else None

    results_by_path: Dict[Path, RunResult] = {}
    runs_to_process: List[Path] = []
    cached_results_used = 0

    if cache and not config.force_reprocess:
        print("Checking cache for existing results...")
        for run_path in tqdm(run_paths, desc="Checking cache"):
            if cache.needs_reprocessing(run_path):
                runs_to_process.append(run_path)
                continue
            cached_result = cache.load_run_result(run_path, output_dir)
            if cached_result is not None:
                results_by_path[run_path] = cached_result
                cached_results_used += 1
            else:
                runs_to_process.append(run_path)
        if cached_results_used:
            print(f"Reused cached QA outputs for {cached_results_used} runs")
    else:
        runs_to_process = list(run_paths)

    return output_dir, cache, runs_to_process, results_by_path, cached_results_used


def _process_runs(
    runs_to_process: List[Path],
    manifest_contexts: Dict[Path, ManifestRunContext],
    config: QAConfig,
    output_dir: Path,
    run_paths: List[Path],
    results_by_path: Dict[Path, RunResult],
) -> List[RunResult]:
    """Process runs in parallel or serial.

    Executes QA processing for all runs that need it, handling both
    manifest and glob-based modes with appropriate masking.

    Parameters
    ----------
    runs_to_process : List[Path]
        Runs that need processing (not cached)
    manifest_contexts : Dict[Path, ManifestRunContext]
        Manifest contexts for each run (empty for glob mode)
    config : QAConfig
        Configuration object
    output_dir : Path
        Output directory
    run_paths : List[Path]
        Original ordered list of all run paths
    results_by_path : Dict[Path, RunResult]
        Existing results (from cache), will be updated

    Returns
    -------
    List[RunResult]
        Complete list of results in original order
    """
    processed_results: List[Optional[RunResult]] = []

    if runs_to_process:
        def worker(path: Path) -> Optional[RunResult]:
            # For manifest mode, use mask from manifest
            if path in manifest_contexts:
                ctx = manifest_contexts[path]
                return process_single_run(
                    path, config, output_dir,
                    reference_mask_path=ctx.mask_path,
                    manifest_context=ctx,
                )
            # For glob mode, let process_single_run find its own mask
            return process_single_run(path, config, output_dir)

        print(f"Processing {len(runs_to_process)} runs...")
        if config.n_jobs == 1:
            processed_results = [worker(path) for path in tqdm(runs_to_process, desc="QA")]
        else:
            processed_results = Parallel(n_jobs=config.n_jobs)(
                delayed(worker)(path) for path in tqdm(runs_to_process, desc="QA")
            )

        for path, result in zip(runs_to_process, processed_results):
            if result is not None:
                results_by_path[path] = result

        successful = sum(1 for r in processed_results if r is not None)
        print(f"Successfully processed {successful} / {len(runs_to_process)} runs")

    results = [results_by_path[path] for path in run_paths if path in results_by_path]
    return results


def _build_analysis_metadata(config: QAConfig, run_paths: List[Path]) -> Dict[str, Any]:
    """Build analysis metadata for provenance.

    Creates a comprehensive metadata dictionary documenting the analysis
    configuration, thresholds, and software versions for reproducibility.

    Parameters
    ----------
    config : QAConfig
        Configuration object
    run_paths : List[Path]
        List of all run paths

    Returns
    -------
    Dict[str, Any]
        Metadata dictionary with timestamp, parameters, and versions
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "data_source": config.data_source,
        "glob_pattern": config.get_effective_glob_pattern() if not config.is_manifest_mode() else "manifest",
        "manifest_path": str(config.manifest_path) if config.is_manifest_mode() else None,
        "total_runs": len(run_paths),
        "thresholds": {
            "dvars_z_threshold": config.dvars_z_threshold,
            "fd_threshold": config.fd_threshold,
            "fd_median_threshold": config.fd_median_threshold,
            "outlier_threshold": config.outlier_threshold,
            "tsnr_drop_threshold": config.tsnr_drop_threshold,
            "slice_intensity_threshold": config.slice_intensity_threshold,
            "outlier_metric_threshold": config.outlier_metric_threshold,
        },
        "versions": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "nibabel": nib.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }


def _detect_outliers(
    results: List[RunResult],
    config: QAConfig,
    output_dir: Path,
    study: StudyResults,
) -> Dict[str, Any]:
    """Detect outliers and save report.

    Runs outlier detection using Mahalanobis distance and updates the study
    object with outlier information.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    config : QAConfig
        Configuration object with thresholds
    output_dir : Path
        Output directory for report
    study : StudyResults
        Study results object to update

    Returns
    -------
    Dict[str, Any]
        Outlier report dictionary
    """
    print("Detecting outliers...")
    outlier_report = generate_outlier_report(
        results,
        mahalanobis_threshold=config.outlier_metric_threshold,
        min_runs=config.outlier_min_runs
    )
    study.overall_outliers = outlier_report['multivariate_outliers']
    study.outlier_report = outlier_report  # Store full report for detailed explanations

    # Save outlier report
    with open(output_dir / "outlier_report.json", 'w') as f:
        json.dump(outlier_report, f, indent=2)

    return outlier_report


def _generate_exclusions(
    results: List[RunResult],
    config: QAConfig,
    outlier_report: Dict[str, Any],
    output_dir: Path,
    study: StudyResults,
) -> None:
    """Generate exclusion recommendations and save reports.

    Creates comprehensive exclusion recommendations based on QA metrics,
    exports BIDS-compatible exclusion lists, censor files, and methods text.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    config : QAConfig
        Configuration object with thresholds
    outlier_report : Dict[str, Any]
        Outlier report from detection
    output_dir : Path
        Output directory for reports
    study : StudyResults
        Study results object to update
    """
    print("Generating exclusion recommendations...")

    # Extract Mahalanobis distances from outlier report
    mahalanobis_distances = {}
    if "mahalanobis_distances" in outlier_report:
        mahalanobis_distances = outlier_report["mahalanobis_distances"]

    # Parse stringency from config
    stringency_map = {
        "liberal": ExclusionStringency.LIBERAL,
        "moderate": ExclusionStringency.MODERATE,
        "conservative": ExclusionStringency.CONSERVATIVE,
    }
    stringency = stringency_map.get(
        config.exclusion_stringency.lower(), ExclusionStringency.MODERATE
    )

    # Generate exclusion report
    exclusion_report = generate_exclusion_report(
        results,
        stringency=stringency,
        mahalanobis_distances=mahalanobis_distances,
        fd_threshold=config.fd_threshold,
        dvars_threshold=config.dvars_z_threshold,
    )
    study.exclusion_report = exclusion_report

    # Save exclusion report
    exclusions_dir = output_dir / "exclusions"
    exclusions_dir.mkdir(exist_ok=True)

    with open(exclusions_dir / "exclusion_report.json", 'w') as f:
        json.dump(exclusion_report.to_dict(), f, indent=2)

    # Export exclusion list in TSV format (BIDS-compatible)
    export_exclusion_list(
        exclusion_report,
        exclusions_dir / "excluded_runs.tsv",
        format="tsv"
    )

    # Export censor files for volume-level scrubbing
    censor_dir = exclusions_dir / "censor_files"
    export_censor_files(exclusion_report, censor_dir, format="fsl")

    # Save methods text
    methods_text = generate_methods_text(exclusion_report)
    (exclusions_dir / "methods_text.txt").write_text(methods_text)

    # Log exclusion summary
    summary = exclusion_report.summary
    print(f"  Exclusion recommendations: {summary['excluded_runs']}/{summary['total_runs']} runs "
          f"({summary['exclusion_rate_percent']:.1f}%)")
    print(f"  Volume scrubbing: {summary['flagged_volumes']}/{summary['total_volumes']} volumes "
          f"({summary['volume_data_loss_percent']:.1f}%)")


def _assign_aggregate_paths(
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
                        session.aggregate_map_paths = session_map_paths[session_key].copy()
                    break

    study.aggregate_figure_path = study_aggregate_path
    study.aggregate_map_paths = study_map_paths


def _generate_group_plots(
    study: StudyResults,
    output_dir: Path,
) -> Dict[str, Path]:
    """Generate group comparison plots.

    Creates violin plots comparing metrics across subjects for tSNR, FD,
    DVARS, and spatial smoothness.

    Parameters
    ----------
    study : StudyResults
        Study results object with subject data
    output_dir : Path
        Output directory

    Returns
    -------
    Dict[str, Path]
        Dictionary mapping plot names to file paths
    """
    print("Generating group comparison plots...")
    plots_dir = output_dir / "group_plots"
    plots_dir.mkdir(exist_ok=True)

    group_plots = {}

    # tSNR
    plot_path = create_subject_comparison_plot(
        study, "tsnr_median", plots_dir / "tsnr_comparison.png",
        "Temporal SNR Distribution by Subject", "tSNR (median)"
    )
    if plot_path:
        group_plots["tsnr"] = plot_path

    # FD
    plot_path = create_subject_comparison_plot(
        study, "fd_median", plots_dir / "fd_comparison.png",
        "Framewise Displacement Distribution by Subject", "FD (median, mm)"
    )
    if plot_path:
        group_plots["fd"] = plot_path

    # DVARS
    plot_path = create_subject_comparison_plot(
        study, "dvars_std_median", plots_dir / "dvars_comparison.png",
        "Standardized DVARS Distribution by Subject", "Standardized DVARS (median)"
    )
    if plot_path:
        group_plots["dvars"] = plot_path

    # Smoothness
    plot_path = create_subject_comparison_plot(
        study, "smoothness_fwhm", plots_dir / "smoothness_comparison.png",
        "Spatial Smoothness Distribution by Subject", "FWHM (mm)"
    )
    if plot_path:
        group_plots["smoothness"] = plot_path

    return group_plots


def run_qa(config: QAConfig) -> int:
    """Main QA execution function."""
    # If reusing a previous run, skip finding runs and go straight to loading
    if config.reuse_run_dir:
        output_dir = config.reuse_run_dir.resolve()
        if not output_dir.exists():
            raise SystemExit(f"Reuse directory {output_dir} does not exist")

        # Friendly messaging for reports-only mode
        if config.reports_only:
            print(f"Reports-only mode: regenerating reports in {output_dir}")
        else:
            print(f"Loading results from previous QA run: {output_dir}")
        
        # Load all results from previous run
        try:
            results = load_all_results_from_previous_run(output_dir, output_dir)
            print(f"Loaded {len(results)} results from previous QA run")
        except Exception as e:
            raise SystemExit(f"Failed to load results from previous run: {e}")
        
        if not results:
            raise SystemExit("No results found in previous QA run directory")
        
        # Skip processing and go straight to report generation
        cached_results_used = len(results)
        run_paths = [r.info.path for r in results]  # For summary purposes
    else:
        # Discover runs from manifest or glob pattern
        run_paths, manifest_contexts, base_output = _discover_runs(config)

        if config.dry_run:
            for path in run_paths:
                print(path)
            return 0

        # Setup output directory and cache
        output_dir, cache, runs_to_process, results_by_path, cached_results_used = _setup_output_and_cache(
            config, base_output, run_paths
        )

        # Process runs
        results = _process_runs(
            runs_to_process, manifest_contexts, config, output_dir, run_paths, results_by_path
        )

    if not results:
        print("ERROR: No runs were successfully processed")
        return 1

    # Update cache (only if not loading from previous run)
    if not config.reuse_run_dir:
        cache = QACache(output_dir, reuse_dir=None) if config.use_cache else None
        if cache:
            # Rebuild results_by_path for cache update
            results_by_path = {r.info.path: r for r in results}
            for path in run_paths:
                if path in results_by_path:
                    cache.set(path, results_by_path[path])
            cache.save()

    # Build analysis metadata for provenance
    analysis_metadata = _build_analysis_metadata(config, run_paths)

    # Organize results hierarchically
    study = organize_results(results, analysis_metadata=analysis_metadata)
    
    # Compute overall metrics
    study.overall_metrics = compute_overall_metrics(results)

    # Outlier detection
    outlier_report = _detect_outliers(results, config, output_dir, study)

    # Generate exclusion recommendations
    _generate_exclusions(results, config, outlier_report, output_dir, study)

    # Aggregate maps
    _assign_aggregate_paths(results, output_dir, study)

    # Generate group comparison plots
    study.group_plots = _generate_group_plots(study, output_dir)

    # Generate hierarchical reports
    if config.organize_hierarchical:
        generate_hierarchical_reports(study, output_dir, study.aggregate_figure_path)
    else:
        # Generate single flat report (legacy)
        generate_study_report(study, output_dir, study.aggregate_figure_path)
    
    # Processing summary
    study.processing_summary = {
        'total_runs_found': len(run_paths),
        'runs_processed': len(results),
        'runs_failed': len(run_paths) - len(results),
        'cached_results_used': cached_results_used,
        'outliers_detected': len(study.overall_outliers),
        'total_warnings': sum(len(r.warnings) for r in results),
    }
    
    # Save study summary
    with open(output_dir / "study_summary.json", 'w') as f:
        json.dump({
            'overall_metrics': study.overall_metrics,
            'processing_summary': study.processing_summary,
            'outliers': study.overall_outliers,
        }, f, indent=2)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"QA Complete!")
    print(f"{'='*60}")
    print(f"Report: {output_dir / 'index.html'}")
    print(f"Output directory: {output_dir}")
    print(f"\nSummary:")
    print(f"  - {len(results)} runs processed")
    print(f"  - {len(study.overall_outliers)} outliers detected ({len(study.overall_outliers)/len(results)*100:.1f}%)")
    print(f"  - Median tSNR: {study.overall_metrics['tsnr_median']:.2f}")
    print(f"  - Median FD: {study.overall_metrics['fd_median']:.3f} mm")
    
    if study.overall_outliers:
        print(f"\nOutlier runs:")
        for outlier in study.overall_outliers[:5]:
            print(f"  - {outlier}")
        if len(study.overall_outliers) > 5:
            print(f"  ... and {len(study.overall_outliers) - 5} more")
    
    return 0


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="fMRI Quality Assurance Pipeline")
    parser.add_argument("--derivatives-dir", type=Path, help="Derivatives directory")
    parser.add_argument("--bids-root", type=Path, help="BIDS root directory (optional)")
    parser.add_argument("--config", type=Path, help="Configuration YAML file")
    parser.add_argument("--manifest", type=Path, metavar="FILE",
                       help="Path to manifest file (YAML/JSON) for non-BIDS datasets")
    parser.add_argument("--data-source", type=str, default=None,
                       choices=["finalinterp", "tedana", "glmsingle", "manifest"],
                       help="Data source preset (default: auto-detect from config, or finalinterp if no config)")
    parser.add_argument("--glmsingle-input-source", type=str, default="finalinterp",
                       choices=["finalinterp", "tedana"],
                       help="For glmsingle: which preprocessing was used (default: finalinterp)")
    parser.add_argument("--glob-pattern", type=str, default="",
                       help="Custom glob pattern (overrides data-source preset)")
    parser.add_argument("--output-dir-name", type=str, default="QA")
    parser.add_argument("--target-echo", type=int, default=2)
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--dvars-z-threshold", type=float, default=StatisticalConstants.Z_SCORE_STRICT)
    parser.add_argument("--fd-threshold", type=float, default=QualityThresholds.FD_THRESHOLD_STRICT)
    parser.add_argument("--fd-median-threshold", type=float, default=0.2)
    parser.add_argument("--outlier-threshold", type=float, default=0.02)
    parser.add_argument("--tsnr-drop-threshold", type=float, default=0.25)
    parser.add_argument("--outlier-metric-threshold", type=float, default=3.0)
    parser.add_argument("--exclusion-stringency", type=str, default="moderate",
                       choices=["liberal", "moderate", "conservative"],
                       help="Stringency for exclusion recommendations")
    parser.add_argument("--no-hierarchical", action="store_true",
                       help="Disable hierarchical reports")
    parser.add_argument("--no-carpetplots", action="store_true",
                       help="Disable carpetplot generation")
    parser.add_argument("--no-cache", action="store_true",
                       help="Disable incremental caching")
    parser.add_argument("--force-reprocess", action="store_true",
                       help="Force reprocessing of all runs")
    parser.add_argument("--reuse-from", type=Path,
                        help="Reuse cached QA results from a previous output directory")
    parser.add_argument("--reports-only", type=Path, metavar="QA_DIR",
                        help="Regenerate reports from existing QA directory without recomputing metrics")
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    # Handle --reports-only as a shortcut for --reuse-from with same output dir
    if args.reports_only:
        args.reuse_from = args.reports_only

    # Handle manifest mode
    if args.manifest:
        args.data_source = "manifest"

    # Load or create config
    if args.config and Path(args.config).exists():
        config = QAConfig.from_yaml(Path(args.config))
        # Override with command-line args if provided
        if args.derivatives_dir:
            config.derivatives_dir = Path(args.derivatives_dir)
        if args.bids_root:
            config.bids_root = Path(args.bids_root)
        if args.manifest:
            config.manifest_path = Path(args.manifest)
            config.data_source = "manifest"
        elif args.data_source is not None:
            # User explicitly provided --data-source, override config
            config.data_source = args.data_source
        if args.n_jobs != 1:
            config.n_jobs = args.n_jobs
        if args.reuse_from:
            config.reuse_run_dir = Path(args.reuse_from)
        if args.reports_only:
            config.reports_only = Path(args.reports_only)
    else:
        # Create config from command-line args
        config = QAConfig(
            derivatives_dir=Path(args.derivatives_dir) if args.derivatives_dir else None,
            bids_root=Path(args.bids_root) if args.bids_root else None,
            manifest_path=Path(args.manifest) if args.manifest else None,
            data_source=args.data_source if args.data_source is not None else "finalinterp",
            glmsingle_input_source=args.glmsingle_input_source,
            glob_pattern=args.glob_pattern,
            output_dir_name=args.output_dir_name,
            target_echo=args.target_echo,
            n_jobs=args.n_jobs,
            dvars_z_threshold=args.dvars_z_threshold,
            fd_threshold=args.fd_threshold,
            fd_median_threshold=args.fd_median_threshold,
            outlier_threshold=args.outlier_threshold,
            tsnr_drop_threshold=args.tsnr_drop_threshold,
            outlier_metric_threshold=args.outlier_metric_threshold,
            exclusion_stringency=args.exclusion_stringency,
            organize_hierarchical=not args.no_hierarchical,
            generate_carpetplots=not args.no_carpetplots,
            use_cache=not args.no_cache,
            force_reprocess=args.force_reprocess,
            reuse_run_dir=Path(args.reuse_from) if args.reuse_from else None,
            reports_only=Path(args.reports_only) if args.reports_only else None,
            dry_run=args.dry_run,
        )
    
    return run_qa(config)


if __name__ == "__main__":
    raise SystemExit(main())