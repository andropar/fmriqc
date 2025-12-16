"""Run-level QA processing."""

import time
import numpy as np
import nibabel as nib
from pathlib import Path
from typing import Dict, Optional, Any, Tuple, TYPE_CHECKING, List

from .config import QAConfig
from .structures import RunInfo, RunResult
from .constants import (
    StatisticalConstants,
    MotionConstants,
    IOConstants,
    QualityThresholds,
)
from .io import (
    find_mask_path,
    locate_motion_params,
    find_events_file,
    find_fieldmap_data,
    ensure_mask_aligned,
    create_run_info,
    create_run_info_from_manifest,
    persist_run_assets,
)

if TYPE_CHECKING:
    from .core import ManifestRunContext
from .metrics import (compute_fd, compute_dvars_standardized, compute_slice_quality,
                      assess_brain_mask_quality, detect_physiological_noise,
                      validate_events_file, assess_sdc_quality, compute_smoothness,
                      compute_ar1, detrend_poly, robust_z, compute_gcor)
from .visualization import create_run_figure, create_carpetplot, create_run_thumbnail


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
) -> Optional[Tuple[nib.Nifti1Image, np.ndarray, np.ndarray, int, float]]:
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
    else:
        mask_path = find_mask_path(run_path, info)

    if mask_path is None:
        warnings_list.append("Mask file not found - using simple threshold")
        mean_img = data.mean(axis=-1)
        mask_data = mean_img > (np.percentile(mean_img[mean_img > 0], 5) if np.any(mean_img > 0) else 0)
    else:
        try:
            mask_img = nib.load(str(mask_path))
            mask_img = ensure_mask_aligned(data_img, mask_img)
            mask_data = mask_img.get_fdata().astype(bool)
        except Exception as e:
            warnings_list.append(f"Cannot load mask: {e}")
            mean_img = data.mean(axis=-1)
            mask_data = mean_img > np.percentile(mean_img[mean_img > 0], 5)

    voxel_count = int(mask_data.sum())
    if voxel_count == 0:
        print(f"ERROR: Empty mask for {run_path}")
        return None

    return data_img, data, mask_data, voxel_count, file_mtime


def _load_motion_parameters(
    info: RunInfo,
    config: QAConfig,
    manifest_context: Optional["ManifestRunContext"],
    warnings_list: List[str],
    thresholds: Dict[str, float],
) -> Tuple[Optional[Path], Optional[np.ndarray], float, float]:
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
    # Motion parameters - use manifest path if available
    if manifest_context is not None and manifest_context.motion_path is not None:
        par_path = manifest_context.motion_path
    elif config.derivatives_dir is not None:
        par_path = locate_motion_params(config.derivatives_dir, info, config.target_echo)
    else:
        par_path = None

    if par_path is not None:
        try:
            fd = compute_fd(par_path)
            fd_percent = float(np.mean(fd > thresholds["fd"]) * 100.0)
            fd_median = float(np.median(fd))
        except Exception as e:
            warnings_list.append(f"Cannot compute FD: {e}")
            fd = None
            fd_percent = 0.0
            fd_median = 0.0
    else:
        warnings_list.append("Motion parameters not found")
        fd = None
        fd_percent = 0.0
        fd_median = 0.0

    return par_path, fd, fd_percent, fd_median


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
        - coverage: Brain coverage
        - dvars_std: Standardized DVARS timeseries
        - dvars_vstd: Variance-standardized DVARS timeseries
        - dvars_basic: Basic DVARS timeseries
        - dvars_percent: Percentage of volumes above DVARS threshold
        - outlier_fraction: Outlier fraction timeseries
        - outlier_high: Percentage of volumes with high outliers
        - maps: Dictionary of spatial maps (mean, std, tsnr, cov, dropout, ar1)
        - voxel_count: Number of voxels in mask
    """
    voxel_count = int(mask_data.sum())

    # Basic spatial maps
    mean_img = data.mean(axis=-1)
    std_img = data.std(axis=-1, ddof=1)
    tsnr_img = np.divide(mean_img, std_img + StatisticalConstants.EPSILON)
    cov_img = np.divide(std_img, mean_img + StatisticalConstants.EPSILON)

    # Coverage
    mean_brain = mean_img[mask_data]
    coverage = float(np.count_nonzero(mean_brain > 0) / voxel_count)

    # Dropout
    low_thresh = np.percentile(mean_brain, 10)
    dropout_map = (mean_img < low_thresh).astype(float) * mask_data

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
        "cov": cov_img,
        "dropout": dropout_map,
    }

    return {
        "tsnr_median": tsnr_median,
        "coverage": coverage,
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
        - physio_metrics: Physiological noise metrics
        - smoothness: Smoothness FWHM
        - gcor: Global correlation
        - ar1_median: Median AR(1) value
        - ar1_brain: AR(1) brain map
    """
    # Global signal analysis
    global_signal = masked.mean(axis=1)
    tr = float(data_img.header.get_zooms()[3]) if data_img.ndim == 4 else 1.0

    # Physiological noise
    physio_metrics = detect_physiological_noise(global_signal, tr)

    # Smoothness
    residuals_4d = data - mean_img[..., None]
    smoothness = compute_smoothness(residuals_4d, data_img.header.get_zooms()[:3])

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
        "physio_metrics": physio_metrics,
        "smoothness": smoothness,
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
) -> Tuple[Optional[Dict], Dict, Dict, bool, Dict, bool]:
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
        (slice_qc, mask_quality, sdc_metrics, sdc_assessed, events_validation, events_validated)
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

    # SDC assessment
    fmap_files = find_fieldmap_data(config.derivatives_dir, info)
    sdc_metrics = {}
    sdc_assessed = False
    if fmap_files is not None:
        try:
            sdc_metrics = assess_sdc_quality(fmap_files)
            sdc_assessed = True
        except Exception as e:
            warnings_list.append(f"SDC assessment failed: {e}")

    # Events validation
    events_validation = {'valid': False, 'n_events': 0, 'issues': []}
    events_validated = False
    events_path = find_events_file(config.derivatives_dir, info)
    if events_path is not None:
        try:
            tr = 1.0  # Will be overridden by actual TR if available
            events_validation = validate_events_file(events_path, data.shape[-1], tr)
            events_validated = True
            if not events_validation['valid']:
                warnings_list.append(f"Events issues: {events_validation['issues']}")
        except Exception as e:
            warnings_list.append(f"Events validation failed: {e}")

    return slice_qc, mask_quality, sdc_metrics, sdc_assessed, events_validation, events_validated


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
) -> Tuple[Path, Optional[Path], Optional[Path]]:
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
        (figure_path, carpetplot_path, thumbnail_path)
    """
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

    return figure_path, carpetplot_path, thumbnail_path


# ============================================================================
# HELPER FUNCTIONS - Results Compilation
# ============================================================================

def _compute_quality_flags(
    metrics: Dict[str, float],
    thresholds: Dict[str, float],
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

    # Quality flags - only flag serious issues
    # These thresholds are intentionally lenient to avoid over-flagging
    flags = {
        "tsnr_low": metrics["tsnr_median"] < 25,  # tSNR below 25 is genuinely poor (conservative threshold)
        "dvars_high": metrics["dvars_percent_above"] > 15.0,  # >15% high-DVARS volumes
        "outliers_high": metrics["outlier_percent_above"] > 10.0,  # >10% outlier volumes
        "motion_high": metrics["fd_percent_above"] > 20.0 or metrics["fd_median"] > QualityThresholds.FD_THRESHOLD_DEFAULT,  # serious motion issues
        "hyperintense_slices": n_hyperintense > 3,  # multiple hyperintense slices
        "slice_outliers": slice_outlier_max > 0.25,  # >25% outlier in worst slice
        "mask_fragmented": metrics.get('mask_components', 1) > 3,  # badly fragmented
        "physiological_noise_high": metrics['physiological_power_ratio'] > 0.5,  # >50% physio
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
    mean_img: np.ndarray,
    warnings_list: List[str],
    slice_qc: Optional[Dict],
    sdc_assessed: bool,
    events_validated: bool,
    file_mtime: float,
    processing_time: float,
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
    mean_img : np.ndarray
        Mean image
    warnings_list : list
        List of warnings
    slice_qc : dict, optional
        Slice quality metrics
    sdc_assessed : bool
        Whether SDC was assessed
    events_validated : bool
        Whether events were validated
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
        sdc_assessed=sdc_assessed,
        events_validated=events_validated,
        file_mtime=file_mtime,
        processing_time=processing_time,
    )

    return result


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_single_run(
    run_path: Path,
    config: QAConfig,
    output_dir: Path,
    reference_mask_path: Optional[Path] = None,
    manifest_context: Optional["ManifestRunContext"] = None,
) -> Optional[RunResult]:
    """Process a single fMRI run with comprehensive QA.

    Parameters
    ----------
    run_path : Path
        Path to the 4D BOLD NIfTI file
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
        # Create run info - use manifest context if available
        if manifest_context is not None:
            info = create_run_info_from_manifest(
                run_path,
                manifest_context.subject_id,
                manifest_context.session_id,
                manifest_context.run_label,
            )
        else:
            info = create_run_info(run_path)

        # Create run directory
        run_dir = _create_run_directories(output_dir, info)

        # Load data and mask
        load_result = _load_run_data(run_path, info, reference_mask_path, warnings_list)
        if load_result is None:
            return None
        data_img, data, mask_data, voxel_count, file_mtime = load_result

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
        par_path, fd, fd_percent, fd_median = _load_motion_parameters(
            info, config, manifest_context, warnings_list, thresholds
        )

        # Assess quality features
        slice_qc, mask_quality, sdc_metrics, sdc_assessed, events_validation, events_validated = \
            _assess_quality_features(data, mask_data, mean_img, info, config, warnings_list)

        # Prepare series data for visualization
        from scipy import signal
        detrended_gs = detrend_poly(temporal_results["global_signal"])
        tr = temporal_results["tr"]
        freq, psd = signal.welch(
            detrended_gs,
            fs=1.0/tr,
            nperseg=min(IOConstants.MAX_INLINE_ARRAY_SIZE, len(detrended_gs))
        )

        series = {
            "dvars": np.concatenate([[np.nan], spatial_results["dvars_basic"]]),
            "dvars_std": np.concatenate([[np.nan], spatial_results["dvars_std"]]),
            "dvars_vstd": np.concatenate([[np.nan], spatial_results["dvars_vstd"]]),
            "dvars_threshold": thresholds["dvars_z"],
            "outlier_fraction": spatial_results["outlier_fraction"],
            "global_signal": temporal_results["global_signal"],
            "freq": freq,
            "psd": psd,
        }

        # Create visualizations
        figure_path, carpetplot_path, thumbnail_path = _create_visualizations(
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
            "coverage": spatial_results["coverage"],
            "smoothness_fwhm": temporal_results["smoothness"],
            "gcor": temporal_results["gcor"],
            "ar1_median": temporal_results["ar1_median"],
            "global_mean": float(np.mean(temporal_results["global_signal"])),
            "n_hyperintense_slices": n_hyperintense,
            "slice_outlier_max": slice_outlier_max,
            **temporal_results["physio_metrics"],
            **mask_quality,
            **sdc_metrics,
        }

        # Compute quality flags
        flags = _compute_quality_flags(metrics, thresholds, slice_qc)

        # Create result
        processing_time = time.time() - start_time
        result = _create_run_result(
            info, metrics, flags, series, maps, mask_data, data_img,
            figure_path, carpetplot_path, thumbnail_path, mean_img,
            warnings_list, slice_qc, sdc_assessed, events_validated,
            file_mtime, processing_time
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
