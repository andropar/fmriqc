"""Orchestration of QA run discovery and processing.

This module handles the discovery of runs to process (from BIDS directories
or manifest files), setup of caching infrastructure, and coordination of
parallel or serial processing of runs.
"""

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import nibabel as nib
import numpy as np
import scipy
import yaml
from joblib import Parallel, delayed
from tqdm import tqdm

from fmriqc.core.motion import has_usable_motion
from fmriqc.core.processing import process_single_run
from fmriqc.io.io import QACache, load_default_derivatives
from fmriqc.io.manifest import QAManifest
from fmriqc.io.structures import InputRun, RunResult, SessionResults, StudyResults, SubjectResults

from .config import QAConfig


@dataclass
class ManifestRunContext:
    """Context for a run from a manifest (includes mask/motion paths).

    Attributes
    ----------
    bold_path : Path
        Path to BOLD NIfTI file
    subject_id : str
        Subject identifier
    session_id : str
        Session identifier
    run_label : str
        Run label
    mask_path : Path, optional
        Path to brain mask file
    motion_path : Path, optional
        Path to motion parameters file
    """

    bold_path: Path
    subject_id: str
    session_id: str
    run_label: str
    mask_path: Optional[Path] = None
    motion_path: Optional[Path] = None


def _get_session_key(run_path: Path) -> str:
    """Extract subject-session key from run path for grouping.

    Parameters
    ----------
    run_path : Path
        Path to run file

    Returns
    -------
    str
        Session key in format "subject_session"
    """
    path_str = str(run_path)
    sub_match = re.search(r'sub-([^/\\]+)', path_str)
    ses_match = re.search(r'ses-([^/\\]+)', path_str)
    subject = sub_match.group(1) if sub_match else "unknown"
    session = ses_match.group(1) if ses_match else "unknown"
    return f"{subject}_{session}"


def discover_runs_from_manifest(manifest: QAManifest) -> List[ManifestRunContext]:
    """Extract run contexts from a manifest.

    Parameters
    ----------
    manifest : QAManifest
        Manifest object containing run information

    Returns
    -------
    List[ManifestRunContext]
        List of run contexts with paths and metadata
    """
    runs = []
    for subject in manifest.subjects:
        for session in subject.sessions:
            for run in session.runs:
                if run.bold:
                    runs.append(
                        ManifestRunContext(
                            bold_path=run.bold,
                            subject_id=subject.id,
                            session_id=session.id,
                            run_label=run.label,
                            mask_path=run.mask,
                            motion_path=run.motion,
                        )
                    )
    return runs


def discover_runs(
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
        run_context_list = discover_runs_from_manifest(manifest)
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
            raise SystemExit(
                f"No runs matched the glob pattern: {config.get_effective_glob_pattern()}"
            )

    print(f"Found {len(run_paths)} runs")

    return run_paths, manifest_contexts, base_output


def setup_output_and_cache(
    config: QAConfig,
    base_output: Path,
    input_runs: List[InputRun],
) -> Tuple[Path, Optional[QACache], List[InputRun], Dict[Path, RunResult], int]:
    """Setup output directory and cache system.

    Creates output directory structure, initializes output-local cache metadata,
    and identifies which runs need processing vs can use cached results.

    Parameters
    ----------
    config : QAConfig
        Configuration object
    base_output : Path
        Base directory for output
    input_runs : List[InputRun]
        Runs to process

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
    import json

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", config.snapshot.id).strip("-") or "snapshot"
    output_dir = base_output / config.output_dir_name / f"{timestamp}_snapshot-{snapshot_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    reuse_dir = None

    # Save config
    config.to_yaml(output_dir / "qa_config.yaml")
    (output_dir / "snapshot.json").write_text(
        json.dumps(config.get_snapshot_info().to_dict(), indent=2)
    )
    (output_dir / "qa_config_resolved.yaml").write_text(
        yaml.safe_dump({"thresholds": config.thresholds.resolve().to_dict()}, sort_keys=False)
    )

    # Initialize cache
    print(f"Initializing cache: {output_dir}")
    cache = (
        QACache(
            output_dir,
            reuse_dir=reuse_dir,
            config_hash=config.compute_hash(),
            input_runs=input_runs,
        )
        if config.use_cache
        else None
    )

    results_by_path: Dict[Path, RunResult] = {}
    runs_to_process: List[InputRun] = []
    cached_results_used = 0

    if cache and not config.force_reprocess:
        print("Checking cache for existing results...")
        for input_run in tqdm(input_runs, desc="Checking cache"):
            run_path = input_run.bold_path
            if cache.needs_reprocessing(run_path):
                runs_to_process.append(input_run)
                continue
            cached_result = cache.load_run_result(run_path, output_dir)
            if cached_result is not None:
                results_by_path[run_path] = cached_result
                cached_results_used += 1
            else:
                runs_to_process.append(input_run)
        if cached_results_used:
            print(f"Reused cached QA outputs for {cached_results_used} runs")
    else:
        runs_to_process = list(input_runs)

    return output_dir, cache, runs_to_process, results_by_path, cached_results_used


def process_runs(
    runs_to_process: List[InputRun],
    manifest_contexts: Dict[Path, ManifestRunContext],
    config: QAConfig,
    output_dir: Path,
    input_runs: List[InputRun],
    results_by_path: Dict[Path, RunResult],
) -> List[RunResult]:
    """Process runs in parallel or serial.

    Executes QA processing for all runs that need it, handling both
    manifest and glob-based modes with appropriate masking.

    Parameters
    ----------
    runs_to_process : List[InputRun]
        Runs that need processing (not cached)
    manifest_contexts : Dict[Path, ManifestRunContext]
        Manifest contexts for each run (empty for glob mode)
    config : QAConfig
        Configuration object
    output_dir : Path
        Output directory
    input_runs : List[InputRun]
        Original ordered list of all input runs
    results_by_path : Dict[Path, RunResult]
        Existing results (from cache), will be updated

    Returns
    -------
    List[RunResult]
        Complete list of results in original order
    """
    processed_results: List[Optional[RunResult]] = []

    if runs_to_process:
        # Generate motion parameters if requested
        if config.motion.strategy == "generate_if_missing":
            from fmriqc.motion_generation import (
                ContainerNotFoundError,
                MotionGenerationError,
                check_container_runtime,
                generate_motion_parameters,
                get_container_path,
            )

            try:
                # Check which container runtime is available
                runtime = check_container_runtime()

                # Only download FSL container for Singularity/Apptainer runtime
                # Docker will pull the image automatically
                container_path = None
                if runtime in {"singularity", "apptainer"}:
                    container_path = get_container_path(
                        config.fsl_container_path,
                        download_policy=config.motion.download_policy,
                    )

                # Identify runs needing motion parameters
                runs_needing_motion = []
                for input_run in runs_to_process:
                    path = input_run.bold_path
                    # Check if motion params already available
                    if not has_usable_motion(input_run):
                        # Need to generate motion for this run
                        run_id = input_run.get_identifier()
                        runs_needing_motion.append((run_id, path))

                # Generate motion parameters
                if runs_needing_motion:
                    par_files = generate_motion_parameters(
                        runs_needing_motion,
                        output_dir,
                        container_path,
                        n_jobs=config.n_jobs,
                    )

                    par_by_path = {path: par_files.get(run_id) for run_id, path in runs_needing_motion}
                    updated_runs = []
                    for input_run in runs_to_process:
                        generated_path = par_by_path.get(input_run.bold_path)
                        if generated_path is None:
                            updated_runs.append(input_run)
                            continue
                        diagnostic_only = (
                            input_run.snapshot.source_type == "preprocessed"
                            and config.motion.diagnostic_only_for_preprocessed
                        )
                        updated_runs.append(
                            replace(
                                input_run,
                                motion_path=generated_path,
                                metadata={
                                    **input_run.metadata,
                                    "motion_generated": True,
                                    "motion_diagnostic_only": diagnostic_only,
                                },
                            )
                        )
                    runs_to_process = updated_runs

            except ContainerNotFoundError as e:
                print(f"\nError: {e}")
                sys.exit(1)
            except MotionGenerationError as e:
                print(f"\nWarning: Motion generation failed: {e}")
                print("Continuing without generated motion parameters...")

        def worker(input_run: InputRun) -> Optional[RunResult]:
            return process_single_run(input_run, config, output_dir)

        print(f"Processing {len(runs_to_process)} runs...")
        if config.n_jobs == 1:
            processed_results = [
                worker(input_run) for input_run in tqdm(runs_to_process, desc="QA")
            ]
        else:
            processed_results = Parallel(n_jobs=config.n_jobs)(
                delayed(worker)(input_run) for input_run in tqdm(runs_to_process, desc="QA")
            )

        for input_run, result in zip(runs_to_process, processed_results):
            if result is not None:
                results_by_path[input_run.bold_path] = result

        successful = sum(1 for r in processed_results if r is not None)
        print(f"Successfully processed {successful} / {len(runs_to_process)} runs")

    results = [results_by_path[input_run.bold_path] for input_run in input_runs if input_run.bold_path in results_by_path]
    return results


def organize_results(
    results: List[RunResult], analysis_metadata: Optional[Dict] = None
) -> StudyResults:
    """Organize flat list of results into hierarchical structure.

    Takes a flat list of run results and organizes them into a hierarchical
    structure of subjects, sessions, and runs.

    Parameters
    ----------
    results : List[RunResult]
        Flat list of run results
    analysis_metadata : dict, optional
        Metadata about the analysis run

    Returns
    -------
    StudyResults
        Hierarchical structure of study results
    """
    # Group by subject and session
    grouped: Dict[str, Dict[str, List[RunResult]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for result in results:
        grouped[result.info.subject][result.info.session].append(result)

    # Create hierarchical structure
    subjects = []
    for subject_id in sorted(grouped.keys()):
        sessions = []
        for session_id in sorted(grouped[subject_id].keys()):
            session_runs = grouped[subject_id][session_id]
            sessions.append(
                SessionResults(
                    subject=subject_id, session=session_id, runs=session_runs
                )
            )
        subjects.append(SubjectResults(subject=subject_id, sessions=sessions))

    return StudyResults(subjects=subjects, analysis_metadata=analysis_metadata or {})


def compute_overall_metrics(results: List[RunResult]) -> Dict:
    """Compute overall study metrics.

    Calculates summary statistics across all runs for key QA metrics.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results

    Returns
    -------
    dict
        Dictionary of overall metrics including median/mean tSNR, FD, etc.
    """
    if not results:
        return {}

    return {
        "runs": len(results),
        "tsnr_median": float(np.median([r.metrics["tsnr_median"] for r in results])),
        "tsnr_mean": float(np.mean([r.metrics["tsnr_median"] for r in results])),
        "fd_median": float(
            np.median([r.metrics.get("fd_median", 0) for r in results])
        ),
        "fd_mean": float(np.mean([r.metrics.get("fd_median", 0) for r in results])),
        "dvars_percent_above_mean": float(
            np.mean([r.metrics["dvars_percent_above"] for r in results])
        ),
        "outlier_percent_above_mean": float(
            np.mean([r.metrics["outlier_percent_above"] for r in results])
        ),
        "smoothness_mean": float(
            np.mean([r.metrics["apparent_smoothness_fwhm"] for r in results])
        ),
        "gcor_mean": float(np.mean([r.metrics["gcor"] for r in results])),
        "ar1_median": float(np.median([r.metrics["ar1_median"] for r in results])),
    }


def build_analysis_metadata(config: QAConfig, run_paths: List[Path]) -> Dict[str, Any]:
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
        "glob_pattern": (
            config.get_effective_glob_pattern()
            if not config.is_manifest_mode()
            else "manifest"
        ),
        "manifest_path": (
            str(config.manifest_path) if config.is_manifest_mode() else None
        ),
        "snapshot": config.get_snapshot_info().to_dict(),
        "total_runs": len(run_paths),
        "thresholds": config.thresholds.resolve().to_dict(),
        "versions": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "nibabel": nib.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
