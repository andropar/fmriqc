"""Run-level QA processing."""

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import nibabel as nib
import numpy as np

from fmriqc.io.io import (
    create_run_info,
    create_run_info_from_manifest,
    ensure_mask_aligned,
    find_mask_path,
    locate_motion_params,
    persist_run_assets,
)
from fmriqc.io.structures import (
    InputRun,
    MaskInfo,
    MotionInfo,
    QAProvenance,
    RunInfo,
    RunResult,
    SnapshotInfo,
)
from fmriqc.orchestration.config import QAConfig

from .constants import (
    IOConstants,
    StatisticalConstants,
)
from .motion import choose_motion_path, load_fd_series
from .thresholds import ResolvedThresholds

if TYPE_CHECKING:
    from fmriqc.orchestration.orchestration import ManifestRunContext
from fmriqc.visualization.visualization import (
    create_carpetplot,
    create_mean_mask_overlay,
    create_run_figure,
    create_run_spatial_maps,
    create_run_thumbnail,
)

from .metrics import (
    assess_brain_mask_quality,
    compute_ar1,
    compute_dvars_standardized,
    compute_gcor,
    compute_slice_quality,
    compute_smoothness,
    detrend_poly,
)

# ============================================================================
# HELPER FUNCTIONS - Data Loading
# ============================================================================

def _create_run_directories(output_dir: Path, info: RunInfo) -> Path:
    """Create proper output directory for this run.

    Parameters
    ----------
    output_dir : Path
        Base output directory
    info : RunInfo
        Run information

    Returns
    -------
    Path
        Run directory path
    """
    subject_dir = output_dir / f"sub-{info.subject}" / f"ses-{info.session}"
    run_dir = subject_dir / info.get_identifier()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _load_run_data(
    run_path: Path,
    info: RunInfo,
    reference_mask_path: Optional[Path],
    warnings_list: List[str],
    explicit_mask_path: Optional[Path] = None,
) -> Optional[Tuple[nib.Nifti1Image, np.ndarray, np.ndarray, int, float, MaskInfo]]:
    """Load run data and mask.

    Parameters
    ----------
    run_path : Path
        Path to the 4D BOLD NIfTI file
    info : RunInfo
        Run information
    reference_mask_path : Path, optional
        Path to reference mask (overrides auto-discovery)
    warnings_list : list
        List to append warnings to

    Returns
    -------
    tuple or None
        (data_img, data, mask_data, voxel_count, file_mtime) or None if loading fails
    """
    # Get file modification time for caching
    file_mtime = run_path.stat().st_mtime

    # Load data
    try:
        data_img = nib.load(str(run_path))
        data = data_img.get_fdata(dtype=np.float32)
    except Exception as e:
        print(f"ERROR: Cannot load {run_path}: {e}")
        return None

    # Find and load mask
    # Use reference mask if provided (ensures consistent mask across runs in a session)
    if reference_mask_path is not None:
        mask_path = reference_mask_path
        mask_source = "reference"
    elif explicit_mask_path is not None:
        mask_path = explicit_mask_path
        mask_source = "manifest"
    else:
        mask_path = find_mask_path(run_path, info)
        mask_source = "bids_derivative" if mask_path else "missing"

    if mask_path is None:
        warnings_list.append("Mask file not found - using simple threshold")
        mean_img = data.mean(axis=-1)
        mask_data = mean_img > (np.percentile(mean_img[mean_img > 0], 5) if np.any(mean_img > 0) else 0)
        mask_info = MaskInfo(
            path=None,
            source="auto_threshold",
            resampled=False,
            same_shape=True,
            same_affine=True,
            warnings=["Mask file not found; generated simple signal threshold mask"],
        )
    else:
        try:
            mask_img = nib.load(str(mask_path))
            same_shape = data_img.shape[:3] == mask_img.shape[:3]
            same_affine = bool(np.allclose(data_img.affine, mask_img.affine, atol=1e-3))
            mask_img, resampled = ensure_mask_aligned(data_img, mask_img)
            if resampled:
                warnings_list.append("Mask grid/affine differed from BOLD image and was resampled")
            mask_data = mask_img.get_fdata().astype(bool)
            mask_info = MaskInfo(
                path=mask_path,
                source=mask_source,  # type: ignore[arg-type]
                resampled=resampled,
                same_shape=same_shape,
                same_affine=same_affine,
            )
        except Exception as e:
            warnings_list.append(f"Cannot load mask: {e}")
            mean_img = data.mean(axis=-1)
            mask_data = mean_img > np.percentile(mean_img[mean_img > 0], 5)
            mask_info = MaskInfo(
                path=mask_path,
                source="auto_threshold",
                warnings=[f"Cannot load requested mask: {e}"],
            )

    voxel_count = int(mask_data.sum())
    if voxel_count == 0:
        print(f"ERROR: Empty mask for {run_path}")
        return None
    mask_info.voxel_count = voxel_count

    return data_img, data, mask_data, voxel_count, file_mtime, mask_info


def _load_motion_parameters(
    info: RunInfo,
    config: QAConfig,
    manifest_context: Optional["ManifestRunContext"],
    warnings_list: List[str],
    thresholds: Dict[str, float],
    input_run: Optional[InputRun] = None,
    motion_path_override: Optional[Path] = None,
) -> Tuple[Optional[Path], Optional[np.ndarray], float, float, MotionInfo]:
    """Load and compute motion parameters.

    Parameters
    ----------
    info : RunInfo
        Run information
    config : QAConfig
        QA configuration
    manifest_context : ManifestRunContext, optional
        Context from manifest with additional file paths
    warnings_list : list
        List to append warnings to
    thresholds : dict
        Quality thresholds

    Returns
    -------
    tuple
        (par_path, fd, fd_percent, fd_median)
    """
    generated = False
    diagnostic_only = False

    if input_run is not None:
        par_path = choose_motion_path(input_run)
        generated = bool(input_run.metadata.get("motion_generated"))
        diagnostic_only = bool(input_run.metadata.get("motion_diagnostic_only", False))
    elif motion_path_override is not None:
        par_path = motion_path_override
        generated = True
    elif manifest_context is not None and manifest_context.motion_path is not None:
        par_path = manifest_context.motion_path
    elif config.derivatives_dir is not None:
        par_path = locate_motion_params(config.derivatives_dir, info, config.target_echo)
    else:
        par_path = None

    if par_path is not None:
        try:
            fd, motion_info = load_fd_series(
                par_path,
                generated=generated,
                diagnostic_only=diagnostic_only,
            )
            warnings_list.extend(motion_info.warnings)
            if fd.size == 0:
                fd = None
                fd_percent = 0.0
                fd_median = 0.0
            else:
                fd_percent = float(np.mean(fd > thresholds["fd"]) * 100.0)
                fd_median = float(np.median(fd))
        except Exception as e:
            warnings_list.append(f"Cannot compute FD: {e}")
            fd = None
            fd_percent = 0.0
            fd_median = 0.0
            motion_info = MotionInfo(path=par_path, source="missing", warnings=[str(e)])
    else:
        warnings_list.append("Motion parameters not found")
        fd = None
        fd_percent = 0.0
        fd_median = 0.0
        motion_info = MotionInfo()

    return par_path, fd, fd_percent, fd_median, motion_info


# ============================================================================
# HELPER FUNCTIONS - Metrics Computation
# ============================================================================

def _compute_spatial_metrics(
    data: np.ndarray,
    mask_data: np.ndarray,
    masked: np.ndarray,
    config: QAConfig,
) -> Dict[str, Any]:
    """Compute spatial metrics and generate spatial maps.

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data
    mask_data : np.ndarray
        Brain mask
    masked : np.ndarray
        Masked timeseries (timepoints x voxels)
    config : QAConfig
        QA configuration

    Returns
    -------
    dict
        Dictionary containing:
        - tsnr_median: Median tSNR value
        - coverage_signal_fraction: Fraction of mask voxels with positive mean signal
        - dvars_std: Standardized DVARS timeseries
        - dvars_vstd: Variance-standardized DVARS timeseries
        - dvars_basic: Basic DVARS timeseries
        - dvars_percent: Percentage of volumes above DVARS threshold
        - outlier_fraction: Outlier fraction timeseries
        - outlier_high: Percentage of volumes with high outliers
        - maps: Dictionary of spatial maps
        - voxel_count: Number of voxels in mask
    """
    voxel_count = int(mask_data.sum())

    # Basic spatial maps
    mean_img = data.mean(axis=-1)
    std_img = data.std(axis=-1, ddof=1)
    tsnr_img = np.divide(mean_img, std_img + StatisticalConstants.EPSILON)
    temporal_cov_img = np.divide(std_img, mean_img + StatisticalConstants.EPSILON)

    # Signal coverage
    mean_brain = mean_img[mask_data]
    coverage_signal_fraction = float(np.count_nonzero(mean_brain > 0) / voxel_count)

    # Low-signal percentile map, not a formal susceptibility-loss estimate.
    low_thresh = np.percentile(mean_brain, 10)
    low_signal_percentile_map = (mean_img < low_thresh).astype(float) * mask_data

    # tSNR
    tsnr_median = float(np.median(tsnr_img[mask_data]))

    # DVARS - standardized
    dvars_std, dvars_vstd = compute_dvars_standardized(data, mask_data)
    diff = np.diff(masked, axis=0)
    dvars_basic = np.sqrt(np.mean(diff**2, axis=1))

    thresholds = config.get_threshold_dict()
    dvars_percent = float(np.mean(dvars_std > thresholds["dvars_z"]) * 100.0)

    # Outlier detection
    voxel_median = np.median(masked, axis=0)
    voxel_mad = np.median(np.abs(masked - voxel_median), axis=0)
    voxel_scale = StatisticalConstants.MAD_TO_STD_FACTOR * voxel_mad + StatisticalConstants.EPSILON
    z = (masked - voxel_median) / voxel_scale
    outlier_fraction = np.mean(np.abs(z) > StatisticalConstants.Z_SCORE_THRESHOLD, axis=1)
    outlier_high = float(np.mean(outlier_fraction > thresholds["outlier"]) * 100.0)

    # Prepare maps (AR(1) will be added by temporal metrics)
    maps = {
        "mean": mean_img,
        "std": std_img,
        "tsnr": tsnr_img,
        "temporal_cov": temporal_cov_img,
        "low_signal": low_signal_percentile_map,
    }

    return {
        "tsnr_median": tsnr_median,
        "coverage_signal_fraction": coverage_signal_fraction,
        "dvars_std": dvars_std,
        "dvars_vstd": dvars_vstd,
        "dvars_basic": dvars_basic,
        "dvars_percent": dvars_percent,
        "outlier_fraction": outlier_fraction,
        "outlier_high": outlier_high,
        "maps": maps,
        "mean_img": mean_img,
        "voxel_count": voxel_count,
    }


def _compute_temporal_metrics(
    masked: np.ndarray,
    data_img: nib.Nifti1Image,
    mean_img: np.ndarray,
    data: np.ndarray,
    mask_data: np.ndarray,
) -> Dict[str, Any]:
    """Compute temporal metrics.

    Parameters
    ----------
    masked : np.ndarray
        Masked timeseries (timepoints x voxels)
    data_img : Nifti1Image
        NIfTI image with header information
    mean_img : np.ndarray
        Mean image
    data : np.ndarray
        4D fMRI data
    mask_data : np.ndarray
        Brain mask

    Returns
    -------
    dict
        Dictionary containing:
        - global_signal: Global signal timeseries
        - tr: Repetition time
        - apparent_smoothness_fwhm: Apparent smoothness FWHM
        - gcor: Global correlation
        - ar1_median: Median AR(1) value
        - ar1_brain: AR(1) brain map
    """
    # Global signal analysis
    global_signal = masked.mean(axis=1)
    tr = float(data_img.header.get_zooms()[3]) if data_img.ndim == 4 else 1.0

    # Smoothness
    residuals_4d = data - mean_img[..., None]
    apparent_smoothness_fwhm = compute_smoothness(residuals_4d, data_img.header.get_zooms()[:3])

    # GCOR - Global Correlation (Saad et al., 2013)
    gcor = compute_gcor(masked)

    # AR(1)
    detrended = masked - np.polyval(
        np.polyfit(np.arange(masked.shape[0]), masked, 2),
        np.arange(masked.shape[0])[:, None]
    )
    ar1_vals = compute_ar1(detrended)
    ar1_brain = np.zeros_like(mean_img)
    ar1_brain[mask_data] = ar1_vals
    ar1_median = float(np.median(ar1_vals))

    return {
        "global_signal": global_signal,
        "tr": tr,
        "apparent_smoothness_fwhm": apparent_smoothness_fwhm,
        "gcor": gcor,
        "ar1_median": ar1_median,
        "ar1_brain": ar1_brain,
    }


# ============================================================================
# HELPER FUNCTIONS - Quality Assessment
# ============================================================================

def _assess_quality_features(
    data: np.ndarray,
    mask_data: np.ndarray,
    mean_img: np.ndarray,
    info: RunInfo,
    config: QAConfig,
    warnings_list: List[str],
) -> Tuple[Optional[Dict], Dict]:
    """Assess various quality features.

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data
    mask_data : np.ndarray
        Brain mask
    mean_img : np.ndarray
        Mean image
    info : RunInfo
        Run information
    config : QAConfig
        QA configuration
    warnings_list : list
        List to append warnings to

    Returns
    -------
    tuple
        (slice_qc, mask_quality)
    """
    voxel_count = int(mask_data.sum())

    # Slice-wise QC
    try:
        slice_qc = compute_slice_quality(data, mask_data)
    except Exception as e:
        warnings_list.append(f"Slice QC failed: {e}")
        slice_qc = None

    # Brain mask quality
    try:
        mask_quality = assess_brain_mask_quality(mask_data, mean_img)
    except Exception as e:
        warnings_list.append(f"Mask quality assessment failed: {e}")
        mask_quality = {
            'mask_voxel_count': voxel_count,
            'mask_volume_fraction': 0.0,
            'mask_components': 1,
            'mask_largest_component_fraction': 1.0,
            'signal_outside_mask_ratio': 0.0,
        }

    return slice_qc, mask_quality


# ============================================================================
# HELPER FUNCTIONS - Visualization
# ============================================================================

def _create_visualizations(
    data: np.ndarray,
    mask_data: np.ndarray,
    mean_img: np.ndarray,
    info: RunInfo,
    run_dir: Path,
    maps: Dict[str, np.ndarray],
    series: Dict[str, np.ndarray],
    fd: Optional[np.ndarray],
    thresholds: Dict[str, float],
    slice_qc: Optional[Dict],
    config: QAConfig,
    warnings_list: List[str],
) -> Tuple[Path, Optional[Path], Optional[Path], Dict[str, Path]]:
    """Create visualization outputs.

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data
    mask_data : np.ndarray
        Brain mask
    mean_img : np.ndarray
        Mean image
    info : RunInfo
        Run information
    run_dir : Path
        Run output directory
    maps : dict
        Spatial maps
    series : dict
        Time series data
    fd : np.ndarray, optional
        Framewise displacement
    thresholds : dict
        Quality thresholds
    slice_qc : dict, optional
        Slice quality metrics
    config : QAConfig
        QA configuration
    warnings_list : list
        List to append warnings to

    Returns
    -------
    tuple
        (figure_path, carpetplot_path, thumbnail_path, spatial_map_paths)
    """
    spatial_map_paths = {}

    # Compact thumbnail for quick visual QA
    thumbnail_path = None
    try:
        thumb_file = run_dir / f"{info.path.stem}_thumbnail.png"
        create_run_thumbnail(mean_img, mask_data, thumb_file)
        thumbnail_path = thumb_file
    except Exception as exc:
        warnings_list.append(f"Thumbnail creation failed: {exc}")

    # Create figures directly in run directory
    figure_filename = run_dir / f"{info.path.stem}_qa_figure.png"
    figure_path = create_run_figure(
        info, maps, series, fd, thresholds, figure_filename, mask_data, slice_qc
    )

    # Create carpetplot
    carpetplot_path = None
    if config.generate_carpetplots:
        try:
            carpetplot_filename = run_dir / f"{info.path.stem}_carpetplot.png"
            # Pass DVARS (use standardized dvars_std for display)
            dvars_for_carpet = series.get("dvars_std")
            carpetplot_path = create_carpetplot(
                data, mask_data, fd, carpetplot_filename, info, dvars=dvars_for_carpet
            )
        except Exception as e:
            warnings_list.append(f"Carpetplot failed: {e}")

    # Create spatial map images for flipbook viewer
    try:
        run_prefix = info.path.stem
        spatial_map_paths = create_run_spatial_maps(
            maps=maps,
            output_dir=run_dir,
            run_prefix=run_prefix,
            mask=mask_data,
            n_slices=5,
        )

        # Create mean+mask overlay for flipbook
        mean_mask_path = run_dir / f"{run_prefix}_map_mean_mask.png"
        create_mean_mask_overlay(mean_img, mask_data, mean_mask_path, n_slices=5)
        spatial_map_paths['mean_mask'] = mean_mask_path
    except Exception as e:
        warnings_list.append(f"Spatial map generation failed: {e}")

    return figure_path, carpetplot_path, thumbnail_path, spatial_map_paths


# ============================================================================
# HELPER FUNCTIONS - Results Compilation
# ============================================================================

def _compute_quality_flags(
    metrics: Dict[str, float],
    thresholds: ResolvedThresholds,
    slice_qc: Optional[Dict],
) -> Dict[str, bool]:
    """Compute quality flags based on metrics and thresholds.

    Parameters
    ----------
    metrics : dict
        Computed metrics
    thresholds : dict
        Quality thresholds
    slice_qc : dict, optional
        Slice quality metrics

    Returns
    -------
    dict
        Quality flags
    """
    n_hyperintense = int(np.sum(slice_qc['hyperintense_slices'])) if slice_qc is not None else 0
    slice_outlier_max = float(np.max(slice_qc['slice_outliers'])) if slice_qc is not None else 0.0

    flags = {
        "tsnr_low": metrics["tsnr_median"] < thresholds.tsnr_median_min,
        "dvars_high": metrics["dvars_percent_above"] > thresholds.dvars_percent,
        "outliers_high": metrics["outlier_percent_above"] > thresholds.outlier_percent,
        "motion_high": (
            metrics["fd_percent_above"] > thresholds.fd_percent
            or metrics["fd_median"] > thresholds.fd_median
        ),
        "hyperintense_slices": n_hyperintense > thresholds.hyperintense_slice_max,
        "slice_outliers": slice_outlier_max > thresholds.slice_outlier_max,
        "mask_fragmented": metrics.get('mask_components', 1) > thresholds.mask_max_components,
    }

    return flags


def _create_run_result(
    info: RunInfo,
    metrics: Dict[str, float],
    flags: Dict[str, bool],
    series: Dict[str, np.ndarray],
    maps: Dict[str, np.ndarray],
    mask_data: np.ndarray,
    data_img: nib.Nifti1Image,
    figure_path: Path,
    carpetplot_path: Optional[Path],
    thumbnail_path: Optional[Path],
    spatial_map_paths: Dict[str, Path],
    mean_img: np.ndarray,
    warnings_list: List[str],
    slice_qc: Optional[Dict],
    file_mtime: float,
    processing_time: float,
    snapshot: SnapshotInfo,
    mask_info: MaskInfo,
    motion_info: MotionInfo,
    config_hash: str,
) -> RunResult:
    """Create RunResult object.

    Parameters
    ----------
    info : RunInfo
        Run information
    metrics : dict
        Computed metrics
    flags : dict
        Quality flags
    series : dict
        Time series data
    maps : dict
        Spatial maps
    mask_data : np.ndarray
        Brain mask
    data_img : Nifti1Image
        NIfTI image with header and affine
    figure_path : Path
        Path to QA figure
    carpetplot_path : Path, optional
        Path to carpetplot
    thumbnail_path : Path, optional
        Path to thumbnail
    spatial_map_paths : dict
        Paths to individual spatial map images for flipbook viewer
    mean_img : np.ndarray
        Mean image
    warnings_list : list
        List of warnings
    slice_qc : dict, optional
        Slice quality metrics
    file_mtime : float
        File modification time
    processing_time : float
        Processing time in seconds

    Returns
    -------
    RunResult
        Complete run result object
    """
    mean_vector = mean_img[mask_data].astype(np.float32)

    # Build asset_paths dict with all visualization paths
    asset_paths = {
        'figure': figure_path,
        'carpetplot': carpetplot_path,
        'thumbnail': thumbnail_path,
    }
    # Add spatial map paths (prefix with 'spatial_map_' for clarity)
    for map_key, map_path in spatial_map_paths.items():
        asset_paths[f'spatial_map_{map_key}'] = map_path

    result = RunResult(
        info=info,
        metrics=metrics,
        flags=flags,
        series=series,
        maps=maps,
        mask=mask_data,
        affine=data_img.affine,
        header=data_img.header,
        figure_path=figure_path,
        carpetplot_path=carpetplot_path,
        thumbnail_path=thumbnail_path,
        mean_vector=mean_vector,
        warnings=warnings_list,
        slice_qc=slice_qc,
        file_mtime=file_mtime,
        processing_time=processing_time,
        asset_paths=asset_paths,
        snapshot=snapshot,
        run_key=info.run_key,
        mask_info=mask_info,
        motion_info=motion_info,
    )
    try:
        import fmriqc

        version = getattr(fmriqc, "__version__", "unknown")
    except Exception:
        version = "unknown"
    result.provenance = QAProvenance(
        snapshot=snapshot,
        run_key=info.run_key,
        bold_path=info.path,
        mask_info=mask_info,
        motion_info=motion_info,
        config_hash=config_hash,
        software_version=version,
        warnings=list(warnings_list),
    )

    return result


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_single_run(
    run_or_input: Union[Path, InputRun],
    config: QAConfig,
    output_dir: Path,
    reference_mask_path: Optional[Path] = None,
    manifest_context: Optional["ManifestRunContext"] = None,
    motion_path_override: Optional[Path] = None,
) -> Optional[RunResult]:
    """Process a single fMRI run with comprehensive QA.

    Parameters
    ----------
    run_or_input : Path or InputRun
        Resolved InputRun or legacy path to a 4D BOLD NIfTI file
    config : QAConfig
        QA configuration
    output_dir : Path
        Output directory for QA results
    reference_mask_path : Path, optional
        Path to reference mask (overrides auto-discovery)
    manifest_context : ManifestRunContext, optional
        Context from manifest with additional file paths
    """
    start_time = time.time()
    warnings_list = []

    try:
        input_run = run_or_input if isinstance(run_or_input, InputRun) else None
        run_path = input_run.bold_path if input_run is not None else Path(run_or_input)
        snapshot = input_run.snapshot if input_run is not None else config.get_snapshot_info()

        # Create run info - use InputRun/manifest context if available
        if input_run is not None:
            key = input_run.run_key.normalized()
            info = RunInfo(
                path=run_path,
                subject=key.subject,
                session=key.session or "01",
                run=key.run or "01",
                task=key.task,
                echo=key.echo,
                part=key.part,
                desc=None,
                acquisition=key.acquisition,
                snapshot_id=snapshot.id,
            )
        elif manifest_context is not None:
            info = create_run_info_from_manifest(
                run_path,
                manifest_context.subject_id,
                manifest_context.session_id,
                manifest_context.run_label,
            )
        else:
            info = create_run_info(run_path)
            info.snapshot_id = snapshot.id

        # Create run directory
        run_dir = _create_run_directories(output_dir, info)

        # Load data and mask
        explicit_mask_path = input_run.mask_path if input_run is not None else None
        load_result = _load_run_data(
            run_path,
            info,
            reference_mask_path,
            warnings_list,
            explicit_mask_path=explicit_mask_path,
        )
        if load_result is None:
            return None
        data_img, data, mask_data, voxel_count, file_mtime, mask_info = load_result

        # Extract masked timeseries
        masked = data[mask_data].reshape(-1, data.shape[-1]).T

        # Compute spatial metrics
        spatial_results = _compute_spatial_metrics(data, mask_data, masked, config)
        mean_img = spatial_results["mean_img"]
        maps = spatial_results["maps"]

        # Compute temporal metrics
        temporal_results = _compute_temporal_metrics(masked, data_img, mean_img, data, mask_data)
        maps["ar1"] = temporal_results["ar1_brain"]  # Add AR(1) map

        # Load motion parameters
        thresholds = config.get_threshold_dict()
        par_path, fd, fd_percent, fd_median, motion_info = _load_motion_parameters(
            info,
            config,
            manifest_context,
            warnings_list,
            thresholds,
            input_run=input_run,
            motion_path_override=motion_path_override,
        )
        n_volumes = int(data.shape[-1])
        if fd is not None and len(fd) != n_volumes:
            warnings_list.append(
                f"FD length ({len(fd)}) does not match number of volumes ({n_volumes})"
            )

        # Assess quality features
        slice_qc, mask_quality = _assess_quality_features(
            data, mask_data, mean_img, info, config, warnings_list
        )

        # Prepare series data for visualization
        from scipy import signal
        detrended_gs = detrend_poly(temporal_results["global_signal"])
        tr = temporal_results["tr"]
        freq, psd = signal.welch(
            detrended_gs,
            fs=1.0/tr,
            nperseg=min(IOConstants.MAX_INLINE_ARRAY_SIZE, len(detrended_gs))
        )

        fd_series = fd if fd is not None else np.full(n_volumes, np.nan, dtype=float)

        series = {
            "fd": fd_series,
            "dvars": np.concatenate([[np.nan], spatial_results["dvars_basic"]]),
            "dvars_std": np.concatenate([[np.nan], spatial_results["dvars_std"]]),
            "dvars_vstd": np.concatenate([[np.nan], spatial_results["dvars_vstd"]]),
            "dvars_threshold": thresholds["dvars_z"],
            "fd_threshold": thresholds["fd"],
            "outlier_fraction": spatial_results["outlier_fraction"],
            "global_signal": temporal_results["global_signal"],
            "freq": freq,
            "psd": psd,
        }

        # Create visualizations
        figure_path, carpetplot_path, thumbnail_path, spatial_map_paths = _create_visualizations(
            data, mask_data, mean_img, info, run_dir, maps, series, fd,
            thresholds, slice_qc, config, warnings_list
        )

        # Compile metrics
        n_hyperintense = int(np.sum(slice_qc['hyperintense_slices'])) if slice_qc is not None else 0
        slice_outlier_max = float(np.max(slice_qc['slice_outliers'])) if slice_qc is not None else 0.0

        metrics = {
            "tsnr_median": spatial_results["tsnr_median"],
            "dvars_percent_above": spatial_results["dvars_percent"],
            "dvars_std_median": float(np.median(spatial_results["dvars_std"])),
            "dvars_vstd_median": float(np.median(spatial_results["dvars_vstd"])),
            "outlier_percent_above": spatial_results["outlier_high"],
            "fd_percent_above": fd_percent,
            "fd_median": fd_median,
            "coverage_signal_fraction": spatial_results["coverage_signal_fraction"],
            "apparent_smoothness_fwhm": temporal_results["apparent_smoothness_fwhm"],
            "gcor": temporal_results["gcor"],
            "ar1_median": temporal_results["ar1_median"],
            "global_mean": float(np.mean(temporal_results["global_signal"])),
            "n_hyperintense_slices": n_hyperintense,
            "slice_outlier_max": slice_outlier_max,
            "n_volumes": n_volumes,
            "tr": float(temporal_results["tr"]),
            "motion_available": fd is not None,
            **mask_quality,
        }
        # Transitional aliases for older downstream code; reports/docs use the new names.
        metrics["coverage"] = metrics["coverage_signal_fraction"]
        metrics["smoothness_fwhm"] = metrics["apparent_smoothness_fwhm"]

        # Compute quality flags
        flags = _compute_quality_flags(metrics, config.thresholds.resolve(), slice_qc)

        # Create result
        processing_time = time.time() - start_time
        result = _create_run_result(
            info, metrics, flags, series, maps, mask_data, data_img,
            figure_path, carpetplot_path, thumbnail_path, spatial_map_paths, mean_img,
            warnings_list, slice_qc, file_mtime, processing_time,
            snapshot, mask_info, motion_info, config.compute_hash()
        )

        try:
            persist_run_assets(result, output_dir)
        except Exception as exc:
            print(f"Warning: Failed to persist run assets for {run_path}: {exc}")

        return result

    except Exception as e:
        print(f"ERROR processing {run_path}: {e}")
        import traceback
        traceback.print_exc()
        return None
