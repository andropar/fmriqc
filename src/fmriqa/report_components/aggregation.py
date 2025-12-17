"""Metric aggregation utilities for QA reports.

This module provides functions for computing aggregate metrics across
runs, sessions, and subjects, as well as safe type conversion functions.
"""

from typing import Dict, List, Any, Optional

import numpy as np


def _safe_float(value) -> Optional[float]:
    """Convert to float, handling numpy types and NaN.

    Parameters
    ----------
    value : any
        Value to convert to float

    Returns
    -------
    float or None
        Float value, or None if value is None or NaN

    Examples
    --------
    >>> _safe_float(42)
    42.0
    >>> _safe_float(np.float64(3.14))
    3.14
    >>> _safe_float(np.nan)
    None
    >>> _safe_float(None)
    None
    """
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        value = float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return float(value)


def _safe_int(value) -> Optional[int]:
    """Convert to int, handling numpy types.

    Parameters
    ----------
    value : any
        Value to convert to int

    Returns
    -------
    int or None
        Integer value, or None if value is None

    Examples
    --------
    >>> _safe_int(42)
    42
    >>> _safe_int(np.int64(100))
    100
    >>> _safe_int(3.7)
    3
    >>> _safe_int(None)
    None
    """
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        return int(value)
    return int(value)


def compute_session_metrics(runs: List[Any]) -> Dict[str, float]:
    """Compute aggregate metrics for a session.

    Aggregates metrics across all runs in a session, computing both mean
    and median values. For metrics already named with _median suffix,
    the median is used as the primary aggregation.

    Parameters
    ----------
    runs : list
        List of RunResult objects

    Returns
    -------
    dict
        Aggregated metrics with _mean and _median suffixes.
        For metrics ending in _median, also includes the base key
        with median aggregation.

    Examples
    --------
    >>> run1 = type('Run', (), {'metrics': {'tsnr_median': 45.0, 'gcor': 0.03}})()
    >>> run2 = type('Run', (), {'metrics': {'tsnr_median': 50.0, 'gcor': 0.04}})()
    >>> metrics = compute_session_metrics([run1, run2])
    >>> metrics['tsnr_median_mean']  # Mean of tSNR medians
    47.5
    >>> metrics['tsnr_median_median']  # Median of tSNR medians
    47.5
    >>> metrics['tsnr']  # Primary aggregation (median for median metrics)
    47.5
    """
    if not runs:
        return {}

    metrics = {}
    all_metrics: Dict[str, List[float]] = {}

    # Collect all metric values
    for run in runs:
        for key, value in run.metrics.items():
            if key not in all_metrics:
                all_metrics[key] = []
            if isinstance(value, (int, float)) and not np.isnan(value):
                all_metrics[key].append(value)

    # Compute aggregates - use original key names with _mean/_median suffix
    for key, values in all_metrics.items():
        if not values:
            continue
        # Store both mean and median for flexibility
        metrics[f"{key}_mean"] = float(np.mean(values))
        metrics[f"{key}_median"] = float(np.median(values))
        # Also store the median as the primary value for median metrics
        if key.endswith("_median"):
            base_key = key.replace("_median", "")
            metrics[base_key] = float(np.median(values))
        else:
            # For non-median metrics, use mean as primary
            metrics[key] = float(np.mean(values))

    return metrics


def compute_subject_metrics(sessions: List[Any]) -> Dict[str, float]:
    """Compute aggregate metrics for a subject.

    Aggregates metrics across all runs from all sessions for a subject.
    This is essentially a convenience wrapper that flattens sessions
    and calls compute_session_metrics().

    Parameters
    ----------
    sessions : list
        List of SessionResults objects

    Returns
    -------
    dict
        Aggregated metrics with _mean and _median suffixes

    Examples
    --------
    >>> run1 = type('Run', (), {'metrics': {'tsnr_median': 45.0}})()
    >>> session1 = type('Session', (), {'runs': [run1]})()
    >>> run2 = type('Run', (), {'metrics': {'tsnr_median': 50.0}})()
    >>> session2 = type('Session', (), {'runs': [run2]})()
    >>> metrics = compute_subject_metrics([session1, session2])
    >>> metrics['tsnr_median_mean']
    47.5
    """
    all_runs = [run for session in sessions for run in session.runs]
    return compute_session_metrics(all_runs)
