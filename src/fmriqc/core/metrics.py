"""QA metric computations."""

import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

from .constants import StatisticalConstants
from .motion import compute_fd_from_fsl_par


def robust_z(x: np.ndarray) -> np.ndarray:
    """Compute robust z-scores using median and MAD."""
    med = np.median(x)
    mad = np.median(np.abs(x - med))
    scale = StatisticalConstants.MAD_TO_STD_FACTOR * mad + StatisticalConstants.EPSILON
    return (x - med) / scale


def detrend_poly(series: np.ndarray, degree: int = 2) -> np.ndarray:
    """Polynomial detrending."""
    t = np.arange(series.shape[0], dtype=np.float32)
    coefs = np.polyfit(t, series, degree)
    trend = np.polyval(coefs, t)
    return series - trend


def compute_fd(par_path: Path) -> np.ndarray:
    """
    Compute Framewise Displacement (FD) from motion parameters.

    FD quantifies head motion between consecutive volumes as the sum of
    absolute displacements across all 6 motion parameters (3 rotations,
    3 translations).

    Parameters
    ----------
    par_path : Path
        Path to motion parameter file. Expected format is FSL mcflirt .par:
        - 6 columns: rot_x, rot_y, rot_z (radians), trans_x, trans_y, trans_z (mm)
        - One row per volume

    Returns
    -------
    np.ndarray
        Framewise displacement in mm for each volume. First volume is always 0.

    Notes
    -----
    Rotational displacements are converted to mm using the arc length
    approximation: displacement = angle (rad) × radius. We use a head radius
    of 50mm, which is standard for adult human heads (Power et al., 2012).

    The formula is: FD_t = |Δrot_x|×r + |Δrot_y|×r + |Δrot_z|×r + |Δtx| + |Δty| + |Δtz|

    References
    ----------
    Power, J. D., et al. (2012). Spurious but systematic correlations in
    functional connectivity MRI networks arise from subject motion.
    NeuroImage, 59(3), 2142-2154.
    """
    return compute_fd_from_fsl_par(Path(par_path))


def compute_dvars_standardized(
    data: np.ndarray, mask: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute standardized DVARS (D-temporal Variance of timecourses) metrics.

    DVARS measures the rate of change of BOLD signal across the brain,
    detecting sudden intensity changes that may indicate motion artifacts.

    Parameters
    ----------
    data : np.ndarray
        4D BOLD data (x, y, z, time)
    mask : np.ndarray
        3D binary brain mask

    Returns
    -------
    dvars_std : np.ndarray
        Standardized DVARS normalized by expected standard deviation.
        Values around 1.0 are expected for typical fMRI data.
        Length is n_volumes - 1.
    dvars_vstd : np.ndarray
        Voxelwise standardized DVARS (each voxel normalized by its own std).
        More robust to regional differences in signal variance.
        Length is n_volumes - 1.

    Notes
    -----
    **Basic DVARS:**
    DVARS_t = sqrt(mean((S_t - S_{t-1})^2))

    **Standardized DVARS:**
    The expected standard deviation of frame-to-frame differences for
    stationary data is sqrt(2) * sigma, since Var(X-Y) = 2*Var(X) for
    independent identically distributed X, Y.

    dvars_std = DVARS / (sqrt(2) * mean(voxel_std))

    **Voxelwise standardized DVARS:**
    Each voxel difference is normalized by that voxel's temporal std:
    dvars_vstd = sqrt(mean(((S_t - S_{t-1}) / sigma_voxel)^2))

    References
    ----------
    Power, J. D., et al. (2012). Spurious but systematic correlations in
    functional connectivity MRI networks arise from subject motion.
    NeuroImage, 59(3), 2142-2154.

    Nichols, T. (2017). Notes on DVARS.
    https://www2.warwick.ac.uk/fac/sci/statistics/staff/academic-research/nichols/scripts/fsl/dvars.pdf
    """
    masked = data[mask].T  # time x voxels

    # Compute frame-to-frame differences
    diff = np.diff(masked, axis=0)

    # Basic DVARS: RMS of differences across voxels
    dvars = np.sqrt(np.mean(diff**2, axis=1))

    # Standardized DVARS: normalize by expected std of differences
    # For stationary data, Var(X_t - X_{t-1}) = 2 * Var(X), so std = sqrt(2) * sigma
    signal_std = np.std(masked, axis=0, ddof=1)
    expected_std = np.sqrt(2) * np.mean(signal_std)
    dvars_std = dvars / (expected_std + StatisticalConstants.EPSILON)

    # Voxelwise standardized DVARS: normalize each voxel by its own std
    voxel_std = np.std(masked, axis=0, ddof=1)
    diff_normalized = diff / (voxel_std[None, :] + 1e-6)
    dvars_vstd = np.sqrt(np.mean(diff_normalized**2, axis=1))

    return dvars_std, dvars_vstd


def compute_slice_quality(data: np.ndarray, mask: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Compute slice-wise quality metrics.

    Parameters
    ----------
    data : np.ndarray
        4D BOLD data (x, y, z, time)
    mask : np.ndarray
        3D binary brain mask

    Returns
    -------
    dict
        Dictionary containing:
        - slice_mean: (n_slices, n_timepoints) mean intensity per slice
        - slice_std: (n_slices,) temporal std per slice
        - slice_outliers: (n_slices,) outlier fraction per slice
        - hyperintense_slices: (n_slices,) boolean array
    """
    n_slices = data.shape[2]
    n_timepoints = data.shape[3]

    slice_metrics = {
        "slice_mean": np.zeros((n_slices, n_timepoints)),
        "slice_std": np.zeros(n_slices),
        "slice_outliers": np.zeros(n_slices),
        "hyperintense_slices": np.zeros(n_slices, dtype=bool),
    }

    # Global stats for comparison
    brain_mean = np.mean(data[mask])
    brain_std = np.std(data[mask])

    for z in range(n_slices):
        slice_mask = mask[:, :, z]
        if not np.any(slice_mask):
            continue

        slice_data = data[:, :, z, :]
        slice_masked = slice_data[slice_mask]

        # Mean intensity over time
        slice_metrics["slice_mean"][z] = np.mean(slice_masked, axis=0)

        # Temporal variability
        slice_metrics["slice_std"][z] = np.std(slice_metrics["slice_mean"][z])

        # Check for hyperintensity
        slice_global_mean = np.mean(slice_metrics["slice_mean"][z])
        if slice_global_mean > brain_mean + 3 * brain_std:
            slice_metrics["hyperintense_slices"][z] = True

        # Outlier detection
        z_scores = robust_z(slice_metrics["slice_mean"][z])
        slice_metrics["slice_outliers"][z] = np.mean(np.abs(z_scores) > 3.0)

    return slice_metrics


def assess_brain_mask_quality(
    mask: np.ndarray, data_mean: np.ndarray
) -> Dict[str, float]:
    """
    Assess quality of brain extraction mask.

    Parameters
    ----------
    mask : np.ndarray
        3D binary brain mask
    data_mean : np.ndarray
        3D mean signal intensity image

    Returns
    -------
    dict
        Metrics about mask coverage and quality
    """
    from scipy.ndimage import label

    metrics = {}

    # Basic coverage
    metrics["mask_voxel_count"] = int(np.sum(mask))
    metrics["mask_volume_fraction"] = float(np.sum(mask) / mask.size)

    # Check for disconnected components
    labeled, n_components = label(mask)
    metrics["mask_components"] = int(n_components)

    # Largest component fraction
    if n_components > 0:
        component_sizes = [np.sum(labeled == i) for i in range(1, n_components + 1)]
        metrics["mask_largest_component_fraction"] = float(
            max(component_sizes) / np.sum(mask)
        )
    else:
        metrics["mask_largest_component_fraction"] = 0.0

    # Signal outside mask
    outside_mask = ~mask
    signal_outside = data_mean[outside_mask]
    signal_inside = data_mean[mask]

    if len(signal_outside) > 0 and len(signal_inside) > 0:
        metrics["signal_outside_mask_ratio"] = float(
            np.mean(signal_outside) / (np.mean(signal_inside) + 1e-6)
        )
    else:
        metrics["signal_outside_mask_ratio"] = 0.0

    return metrics


def compute_smoothness(
    residuals: np.ndarray, voxel_sizes: Tuple[float, float, float]
) -> float:
    """
    Estimate spatial smoothness as Full Width at Half Maximum (FWHM).

    Uses a gradient-based estimator similar to FSL's smoothest, based on
    Gaussian Random Field theory.

    Parameters
    ----------
    residuals : np.ndarray
        4D residual image (x, y, z, time). Should be detrended/demeaned.
    voxel_sizes : tuple
        Voxel dimensions in mm (x, y, z)

    Returns
    -------
    float
        Estimated FWHM in mm (average across x, y, z directions)

    Notes
    -----
    For a Gaussian random field with autocorrelation function:
    ρ(h) = exp(-h²/(2σ²))

    The FWHM relates to σ by: FWHM = σ × sqrt(8 × ln(2)) ≈ 2.355 × σ

    The variance ratio (signal variance / gradient variance) estimates σ²,
    since for a smooth Gaussian field:
    Var(dX/dx) ≈ Var(X) / σ²

    References
    ----------
    Forman, S. D., et al. (1995). Improved assessment of significant
    activation in functional magnetic resonance imaging (fMRI).
    Magnetic Resonance in Medicine, 33(5), 636-647.

    Kiebel, S. J., et al. (1999). Robust smoothness estimation in
    statistical parametric maps using standardized residuals from the
    general linear model. NeuroImage, 10(6), 756-766.
    """
    var = float(np.var(residuals)) + 1e-6
    grads = []

    for axis, voxel_size in enumerate(voxel_sizes):
        # Compute spatial gradient in each direction
        diff = np.diff(residuals, axis=axis)
        diff /= voxel_size  # Scale to mm
        grads.append(np.var(diff) + 1e-6)

    # Average the variance ratio across dimensions
    # Higher ratio = more smoothness
    inv = sum(var / g for g in grads) / len(grads)

    # Convert to FWHM: FWHM = sqrt(8 * ln(2)) * sigma
    fwhm = math.sqrt(8.0 * math.log(2.0) * inv)

    return float(fwhm)


def compute_gcor(masked_data: np.ndarray) -> float:
    """
    Compute Global Correlation (GCOR) following Saad et al. (2013).

    GCOR is the average of the entire brain correlation matrix. This
    implementation uses the efficient computation from AFNI, which is
    mathematically equivalent to computing all M*(M-1)/2 pairwise
    correlations but much faster.

    Parameters
    ----------
    masked_data : np.ndarray
        2D array of shape (time, voxels) containing voxel time series

    Returns
    -------
    float
        GCOR value. Range is [0, 1] where:
        - 0 indicates no global correlation
        - 1 indicates perfect global correlation (all voxels identical)
        Typical fMRI values range from 0.0 to 0.5.

    Notes
    -----
    The efficient AFNI formula (Saad et al., 2013):
    1. De-mean each voxel's time series
    2. Scale each to unit Euclidean norm: ||x|| = 1
    3. Average the unit-normed series across voxels: g_u = mean(U, axis=1)
    4. GCOR = ||g_u||² = g_u^T @ g_u

    This equals the mean of the full correlation matrix because for
    unit-normed centered vectors, r_ij = x_i^T @ x_j, and:
    mean(R) = (1/M²) sum_ij(r_ij) = ||mean(X)||²

    References
    ----------
    Saad, Z. S., et al. (2013). Correcting brain-wide correlation
    differences in resting-state FMRI. Brain Connectivity, 3(4), 339-352.
    """
    n_time, n_voxels = masked_data.shape

    if n_voxels < 2 or n_time < 2:
        return 0.0

    # Step 1: De-mean each voxel's time series
    centered = masked_data - masked_data.mean(axis=0)

    # Step 2: Scale each voxel to unit Euclidean norm
    # ||x|| = sqrt(sum(x^2))
    norms = np.sqrt(np.sum(centered**2, axis=0))
    norms[norms < 1e-6] = 1e-6  # Avoid division by zero
    U = centered / norms

    # Step 3: Average across voxels
    g_u = U.mean(axis=1)

    # Step 4: GCOR = L2 norm squared = g_u^T @ g_u
    gcor = float(np.dot(g_u, g_u))

    return gcor


def compute_ar1(series: np.ndarray) -> np.ndarray:
    """
    Compute lag-1 autocorrelation coefficient.

    This computes the AR(1) coefficient using the standard regression formula,
    which for zero-mean data is equivalent to the Pearson correlation between
    the time series and its lagged version.

    Parameters
    ----------
    series : np.ndarray
        Time series (time x voxels), should be detrended

    Returns
    -------
    np.ndarray
        AR(1) coefficient per voxel

    Notes
    -----
    Formula: AR(1) = sum(x_t * x_{t-1}) / sum(x_{t-1}^2)

    For detrended (zero-mean) data, this equals the lag-1 autocorrelation.
    Typical fMRI values range from 0.1 to 0.6.
    """
    x = series[1:]
    y = series[:-1]
    numerator = np.sum(x * y, axis=0)
    denominator = np.sum(y * y, axis=0) + 1e-6
    return numerator / denominator
