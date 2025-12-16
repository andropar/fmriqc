"""Outlier detection for QA results."""

import numpy as np
from typing import List, Dict, Tuple
from scipy import stats
from scipy.spatial.distance import mahalanobis

from .structures import RunResult, SessionResults
from .constants import StatisticalConstants


def detect_outliers_mahalanobis(
    results: List[RunResult],
    threshold: float = StatisticalConstants.MAHALANOBIS_THRESHOLD,
    min_runs: int = 5
) -> Tuple[List[str], Dict[str, float]]:
    """
    Detect outlier runs using Mahalanobis distance in metric space.

    Parameters
    ----------
    results : list
        List of RunResult objects
    threshold : float
        Threshold for Mahalanobis distance (default: StatisticalConstants.MAHALANOBIS_THRESHOLD)
    min_runs : int
        Minimum number of runs needed for outlier detection
    
    Returns
    -------
    outlier_identifiers : list
        List of run identifiers flagged as outliers
    distances : dict
        Dictionary mapping run identifiers to Mahalanobis distances
    """
    if len(results) < min_runs:
        return [], {}
    
    # Select key metrics for outlier detection
    # Use fewer metrics if we have few runs to avoid rank deficiency
    all_metric_keys = [
        'tsnr_median',
        'fd_median',
        'dvars_percent_above',
        'outlier_percent_above',
        'gcor',
        'smoothness_fwhm',
        'coverage',
    ]
    
    # Adaptive metric selection: use at most n_runs - 2 metrics
    max_metrics = max(3, len(results) - 2)
    metric_keys = all_metric_keys[:min(len(all_metric_keys), max_metrics)]
    
    # Build metric matrix
    metric_matrix = []
    identifiers = []
    
    for res in results:
        # Check if all metrics are present
        if all(key in res.metrics for key in metric_keys):
            metric_vector = [res.metrics[key] for key in metric_keys]
            metric_matrix.append(metric_vector)
            identifiers.append(res.info.get_identifier())
    
    if len(metric_matrix) < min_runs:
        return [], {}
    
    metric_matrix = np.array(metric_matrix)
    
    # Check for zero variance metrics
    variances = np.var(metric_matrix, axis=0)
    valid_metrics = variances > StatisticalConstants.NUMERICAL_STABILITY
    if not np.all(valid_metrics):
        metric_matrix = metric_matrix[:, valid_metrics]
        if metric_matrix.shape[1] == 0:
            print("Warning: All metrics have zero variance, cannot detect outliers")
            return [], {}

    # Normalize metrics to same scale (z-score)
    # This helps with numerical stability
    mean = np.mean(metric_matrix, axis=0)
    std = np.std(metric_matrix, axis=0) + StatisticalConstants.NUMERICAL_STABILITY
    metric_matrix_normalized = (metric_matrix - mean) / std
    
    # Compute robust center
    center = np.median(metric_matrix_normalized, axis=0)
    
    # Try robust covariance estimation
    cov_inv = None
    method_used = 'none'
    
    # Method 1: Try MinCovDet (most robust)
    try:
        from sklearn.covariance import MinCovDet
        mcd = MinCovDet(support_fraction=0.8, random_state=0).fit(metric_matrix_normalized)
        cov = mcd.covariance_
        center = mcd.location_
        
        # Check condition number
        cond = np.linalg.cond(cov)
        if cond < 1e10:  # Not too ill-conditioned
            cov_inv = np.linalg.inv(cov)
            method_used = 'mincovdet'
    except Exception as e:
        pass
    
    # Method 2: Regularized covariance
    if cov_inv is None:
        try:
            cov = np.cov(metric_matrix_normalized.T)
            
            # Add regularization proportional to trace
            regularization = 0.1 * np.trace(cov) / cov.shape[0]
            cov_reg = cov + regularization * np.eye(cov.shape[0])
            
            # Check rank
            rank = np.linalg.matrix_rank(cov_reg)
            if rank == cov_reg.shape[0]:
                cov_inv = np.linalg.inv(cov_reg)
                method_used = 'regularized'
        except Exception as e:
            pass
    
    # Method 3: Pseudoinverse
    if cov_inv is None:
        try:
            cov = np.cov(metric_matrix_normalized.T)
            cov_inv = np.linalg.pinv(cov)
            method_used = 'pseudoinverse'
        except Exception as e:
            pass
    
    # Method 4: Fallback to Euclidean distance
    if cov_inv is None:
        print("Warning: Could not compute covariance inverse, using Euclidean distance")
        method_used = 'euclidean'
    
    # Compute distances
    distances = {}
    outliers = []
    
    for i, identifier in enumerate(identifiers):
        diff = metric_matrix_normalized[i] - center
        
        try:
            if cov_inv is not None:
                # Mahalanobis distance
                dist = np.sqrt(np.abs(diff @ cov_inv @ diff))  # abs for numerical stability
            else:
                # Euclidean distance as fallback
                dist = np.linalg.norm(diff)
        except Exception as e:
            # Final fallback
            dist = np.linalg.norm(diff)
        
        distances[identifier] = float(dist)
        
        if dist > threshold:
            outliers.append(identifier)
    
    return outliers, distances


def detect_outliers_univariate(
    results: List[RunResult],
    threshold: float = StatisticalConstants.Z_SCORE_THRESHOLD
) -> Dict[str, List[str]]:
    """
    Detect outliers for each metric individually using robust z-scores.

    Parameters
    ----------
    results : list
        List of RunResult objects
    threshold : float
        Threshold for robust z-score (default: StatisticalConstants.Z_SCORE_THRESHOLD)
    
    Returns
    -------
    dict
        Dictionary mapping metric names to lists of outlier identifiers
    """
    if len(results) < 3:
        return {}
    
    # Collect all unique metric keys
    metric_keys = set()
    for res in results:
        metric_keys.update(res.metrics.keys())
    
    outliers_by_metric = {}
    
    for metric in metric_keys:
        # Collect values for this metric
        values = []
        identifiers = []
        
        for res in results:
            if metric in res.metrics:
                values.append(res.metrics[metric])
                identifiers.append(res.info.get_identifier())
        
        if len(values) < 3:
            continue
        
        values = np.array(values)

        # Compute robust z-scores
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad < StatisticalConstants.NUMERICAL_STABILITY:  # Essentially constant
            continue

        robust_z = (values - median) / (StatisticalConstants.MAD_TO_STD_FACTOR * mad)
        
        # Find outliers
        outlier_mask = np.abs(robust_z) > threshold
        if np.any(outlier_mask):
            outliers_by_metric[metric] = [
                identifiers[i] for i in np.where(outlier_mask)[0]
            ]
    
    return outliers_by_metric


def flag_extreme_motion(
    results: List[RunResult],
    fd_threshold: float = 0.5,
    fd_percent_threshold: float = 20.0
) -> List[str]:
    """
    Flag runs with extreme motion.
    
    Parameters
    ----------
    results : list
        List of RunResult objects
    fd_threshold : float
        FD threshold in mm (default: 0.5)
    fd_percent_threshold : float
        Percentage of volumes above threshold (default: 20%)
    
    Returns
    -------
    list
        List of run identifiers with extreme motion
    """
    extreme_motion = []
    
    for res in results:
        fd_median = res.metrics.get('fd_median', 0)
        fd_percent = res.metrics.get('fd_percent_above', 0)
        
        # Flag if median FD is very high OR many volumes exceed threshold
        if fd_median > fd_threshold or fd_percent > fd_percent_threshold:
            extreme_motion.append(res.info.get_identifier())
    
    return extreme_motion


def flag_low_tsnr(
    results: List[RunResult],
    tsnr_threshold: float = 30.0
) -> Tuple[List[str], float]:
    """
    Flag runs with tSNR below absolute threshold.

    Parameters
    ----------
    results : list
        List of RunResult objects
    tsnr_threshold : float
        Absolute tSNR threshold (default: 30.0). Runs below this are flagged.
        For reference: tSNR < 20 is poor, 20-40 is marginal, > 40 is good.

    Returns
    -------
    low_tsnr : list
        List of run identifiers with low tSNR
    threshold_used : float
        The threshold that was applied
    """
    low_tsnr = []

    for res in results:
        if 'tsnr_median' in res.metrics:
            if res.metrics['tsnr_median'] < tsnr_threshold:
                low_tsnr.append(res.info.get_identifier())

    return low_tsnr, tsnr_threshold


def generate_outlier_report(
    results: List[RunResult],
    mahalanobis_threshold: float = StatisticalConstants.MAHALANOBIS_THRESHOLD,
    min_runs: int = 5
) -> Dict[str, any]:
    """
    Generate comprehensive outlier report.

    Parameters
    ----------
    results : list
        List of RunResult objects
    mahalanobis_threshold : float
        Threshold for multivariate outlier detection (default: StatisticalConstants.MAHALANOBIS_THRESHOLD)
    min_runs : int
        Minimum runs for outlier detection
    
    Returns
    -------
    dict
        Comprehensive outlier report
    """
    report = {
        'multivariate_outliers': [],
        'univariate_outliers': {},
        'extreme_motion': [],
        'low_tsnr': [],
        'mahalanobis_distances': {},
        'summary': {},
        'warnings': [],
    }
    
    # Multivariate outlier detection
    try:
        outliers, distances = detect_outliers_mahalanobis(
            results, 
            threshold=mahalanobis_threshold,
            min_runs=min_runs
        )
        report['multivariate_outliers'] = outliers
        report['mahalanobis_distances'] = distances
    except Exception as e:
        report['warnings'].append(f"Multivariate outlier detection failed: {str(e)}")
        print(f"Warning: Multivariate outlier detection failed: {e}")
    
    # Univariate outlier detection
    try:
        report['univariate_outliers'] = detect_outliers_univariate(results)
    except Exception as e:
        report['warnings'].append(f"Univariate outlier detection failed: {str(e)}")
        print(f"Warning: Univariate outlier detection failed: {e}")
    
    # Specific checks
    try:
        report['extreme_motion'] = flag_extreme_motion(results)
    except Exception as e:
        report['warnings'].append(f"Extreme motion detection failed: {str(e)}")
        print(f"Warning: Extreme motion detection failed: {e}")
    
    try:
        low_tsnr_runs, tsnr_threshold = flag_low_tsnr(results)
        report['low_tsnr'] = low_tsnr_runs
        report['tsnr_threshold'] = tsnr_threshold
    except Exception as e:
        report['warnings'].append(f"Low tSNR detection failed: {str(e)}")
        print(f"Warning: Low tSNR detection failed: {e}")
    
    # Summary
    all_outliers = set(report['multivariate_outliers'])
    all_outliers.update(report['extreme_motion'])
    all_outliers.update(report['low_tsnr'])
    
    report['summary'] = {
        'total_runs': len(results),
        'multivariate_outliers': len(report['multivariate_outliers']),
        'extreme_motion_runs': len(report['extreme_motion']),
        'low_tsnr_runs': len(report['low_tsnr']),
        'total_flagged': len(all_outliers),
        'percentage_flagged': 100.0 * len(all_outliers) / len(results) if results else 0.0,
    }
    
    return report