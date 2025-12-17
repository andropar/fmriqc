"""Outlier detection for QA results."""

import numpy as np
from typing import List, Dict, Tuple, Optional
from abc import ABC, abstractmethod
from scipy import stats
from scipy.spatial.distance import mahalanobis

from fmriqa.io.structures import RunResult, SessionResults
from fmriqa.core.constants import StatisticalConstants


# === COVARIANCE ESTIMATION STRATEGIES ===


class CovarianceEstimator(ABC):
    """Base class for covariance estimation strategies."""

    @abstractmethod
    def estimate(self, data: np.ndarray) -> Optional[np.ndarray]:
        """Estimate covariance matrix.

        Parameters
        ----------
        data : np.ndarray
            Data matrix (n_samples, n_features)

        Returns
        -------
        np.ndarray or None
            Covariance matrix, or None if estimation failed
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return estimator name for logging."""
        pass


class LedoitWolfEstimator(CovarianceEstimator):
    """Ledoit-Wolf shrinkage estimator.

    Uses optimal shrinkage to regularize the covariance matrix,
    improving estimation when sample size is small relative to
    dimensionality.

    Reference: Ledoit & Wolf (2004)
    """

    def name(self) -> str:
        return "Ledoit-Wolf"

    def estimate(self, data: np.ndarray) -> Optional[np.ndarray]:
        try:
            from sklearn.covariance import LedoitWolf
            return LedoitWolf().fit(data).covariance_
        except Exception:
            return None


class EmpiricalEstimator(CovarianceEstimator):
    """Standard empirical covariance.

    Computes the maximum likelihood covariance estimate.
    May fail or be poorly conditioned when sample size
    is small or features are highly correlated.
    """

    def name(self) -> str:
        return "Empirical"

    def estimate(self, data: np.ndarray) -> Optional[np.ndarray]:
        try:
            return np.cov(data, rowvar=False)
        except Exception:
            return None


class DiagonalEstimator(CovarianceEstimator):
    """Diagonal covariance (independent features).

    Assumes features are uncorrelated and estimates only
    the diagonal elements (variances). This is a strong
    simplification but always well-conditioned.
    """

    def name(self) -> str:
        return "Diagonal"

    def estimate(self, data: np.ndarray) -> Optional[np.ndarray]:
        try:
            variances = np.var(data, axis=0)
            if np.all(variances > StatisticalConstants.NUMERICAL_STABILITY):
                return np.diag(variances)
            return None
        except Exception:
            return None


class IdentityEstimator(CovarianceEstimator):
    """Identity covariance (last resort fallback).

    Returns identity matrix, effectively computing Euclidean
    distance instead of Mahalanobis distance. Always succeeds
    and is used as the final fallback.
    """

    def name(self) -> str:
        return "Identity"

    def estimate(self, data: np.ndarray) -> Optional[np.ndarray]:
        return np.eye(data.shape[1])


class CovarianceEstimatorChain:
    """Try estimators in sequence until one succeeds.

    Implements a chain-of-responsibility pattern for covariance
    estimation with progressively simpler fallback strategies:
    1. Ledoit-Wolf (robust shrinkage)
    2. Empirical (standard maximum likelihood)
    3. Diagonal (independent features)
    4. Identity (Euclidean distance)
    """

    def __init__(self):
        self.estimators = [
            LedoitWolfEstimator(),
            EmpiricalEstimator(),
            DiagonalEstimator(),
            IdentityEstimator(),
        ]

    def estimate(self, data: np.ndarray) -> tuple[np.ndarray, str]:
        """Estimate covariance with fallback chain.

        Parameters
        ----------
        data : np.ndarray
            Data matrix (n_samples, n_features)

        Returns
        -------
        tuple[np.ndarray, str]
            Covariance matrix and name of successful estimator
        """
        for estimator in self.estimators:
            cov = estimator.estimate(data)
            if cov is not None:
                return cov, estimator.name()
        # Should never reach here since Identity always succeeds
        return np.eye(data.shape[1]), "Identity (fallback)"


# === HELPER FUNCTIONS ===


def _prepare_metric_matrix(
    results: List[RunResult],
    min_runs: int
) -> Tuple[Optional[np.ndarray], List[str], List[str]]:
    """Prepare and validate metric matrix for outlier detection.

    Parameters
    ----------
    results : list
        List of RunResult objects
    min_runs : int
        Minimum number of runs needed

    Returns
    -------
    metric_matrix : np.ndarray or None
        Normalized metric matrix (n_samples, n_features), or None if invalid
    identifiers : list
        Run identifiers corresponding to matrix rows
    metric_keys : list
        Metric keys used (for reference)
    """
    if len(results) < min_runs:
        return None, [], []

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
        return None, [], metric_keys

    metric_matrix = np.array(metric_matrix)

    # Check for zero variance metrics
    variances = np.var(metric_matrix, axis=0)
    valid_metrics = variances > StatisticalConstants.NUMERICAL_STABILITY
    if not np.all(valid_metrics):
        metric_matrix = metric_matrix[:, valid_metrics]
        if metric_matrix.shape[1] == 0:
            print("Warning: All metrics have zero variance, cannot detect outliers")
            return None, [], metric_keys

    # Normalize metrics to same scale (z-score)
    # This helps with numerical stability
    mean = np.mean(metric_matrix, axis=0)
    std = np.std(metric_matrix, axis=0) + StatisticalConstants.NUMERICAL_STABILITY
    metric_matrix_normalized = (metric_matrix - mean) / std

    return metric_matrix_normalized, identifiers, metric_keys


def _compute_mahalanobis_distances(
    data: np.ndarray,
    cov_matrix: np.ndarray,
    center: Optional[np.ndarray] = None
) -> np.ndarray:
    """Compute Mahalanobis distances for each data point.

    Parameters
    ----------
    data : np.ndarray
        Data matrix (n_samples, n_features)
    cov_matrix : np.ndarray
        Covariance matrix (n_features, n_features)
    center : np.ndarray, optional
        Center point. If None, uses median of data.

    Returns
    -------
    np.ndarray
        Mahalanobis distances for each sample
    """
    if center is None:
        center = np.median(data, axis=0)

    try:
        cov_inv = np.linalg.inv(cov_matrix)
    except np.linalg.LinAlgError:
        # Use pseudoinverse as fallback
        cov_inv = np.linalg.pinv(cov_matrix)

    distances = np.zeros(len(data))
    for i in range(len(data)):
        diff = data[i] - center
        try:
            # abs for numerical stability (avoid negative values from numerical errors)
            distances[i] = np.sqrt(np.abs(diff @ cov_inv @ diff))
        except Exception:
            # Final fallback: Euclidean distance
            distances[i] = np.linalg.norm(diff)

    return distances


# === MAIN OUTLIER DETECTION FUNCTIONS ===


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
    # Prepare and validate metric matrix
    metric_matrix, identifiers, metric_keys = _prepare_metric_matrix(results, min_runs)

    if metric_matrix is None:
        return [], {}

    # Compute robust center
    center = np.median(metric_matrix, axis=0)

    # Estimate covariance matrix using chain of strategies
    estimator_chain = CovarianceEstimatorChain()
    cov_matrix, method_used = estimator_chain.estimate(metric_matrix)

    # Compute Mahalanobis distances
    distances_array = _compute_mahalanobis_distances(metric_matrix, cov_matrix, center)

    # Build results
    distances = {}
    outliers = []

    for i, identifier in enumerate(identifiers):
        dist = float(distances_array[i])
        distances[identifier] = dist

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
