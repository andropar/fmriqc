"""Metric name resolution and documentation utilities.

This module provides functions for resolving metric names to their
human-readable tooltips and expected standard values for QA reports.
"""

from .constants import METRIC_TOOLTIPS, METRIC_STANDARDS


def get_metric_tooltip(metric_name: str) -> str:
    """Get tooltip text for a metric.

    Provides human-readable descriptions for QA metrics, with support
    for aggregated metrics (e.g., tsnr_median_mean) and consistency
    metrics (e.g., tsnr_cv).

    Parameters
    ----------
    metric_name : str
        Name of the metric (e.g., "tsnr_median", "fd_percent_above")

    Returns
    -------
    str
        Human-readable description of the metric

    Examples
    --------
    >>> get_metric_tooltip("tsnr_median")
    'Median temporal signal-to-noise ratio'
    >>> get_metric_tooltip("tsnr_median_mean")
    'Median temporal signal-to-noise ratio (Mean across runs)'
    >>> get_metric_tooltip("tsnr_cv")
    'Coefficient of variation for median temporal signal-to-noise ratio. Lower is better.'

    Notes
    -----
    Handles several naming patterns:
    - Direct matches from METRIC_TOOLTIPS
    - Aggregated metrics: *_mean, *_median
    - Consistency metrics: *_cv, *_range, *_drift_slope, *_drift_pvalue
    - Special metrics: spatial_icc, overall_consistency
    """
    # Check direct match first
    if metric_name in METRIC_TOOLTIPS:
        return METRIC_TOOLTIPS[metric_name]

    # Handle aggregated metrics (e.g., tsnr_median_median, tsnr_median_mean)
    if metric_name.endswith("_mean"):
        base = metric_name[:-5]  # Remove "_mean"
        if base in METRIC_TOOLTIPS:
            return f"{METRIC_TOOLTIPS[base]} (Mean across runs)"
        # Try with _median suffix
        base_with_median = f"{base}_median"
        if base_with_median in METRIC_TOOLTIPS:
            return f"{METRIC_TOOLTIPS[base_with_median]} (Mean across runs)"

    if metric_name.endswith("_median"):
        base = metric_name[:-7]  # Remove "_median"
        if base in METRIC_TOOLTIPS:
            return f"{METRIC_TOOLTIPS[base]} (Median across runs)"
        # Try with _median suffix
        base_with_median = f"{base}_median"
        if base_with_median in METRIC_TOOLTIPS:
            return f"{METRIC_TOOLTIPS[base_with_median]} (Median across runs)"

    # Handle consistency metrics
    if metric_name.endswith("_cv"):
        base = metric_name[:-3]
        base_desc = METRIC_TOOLTIPS.get(base) or METRIC_TOOLTIPS.get(f"{base}_median")
        if base_desc:
            return f"Coefficient of variation for {base_desc.lower()}. Lower is better."

    if metric_name.endswith("_range"):
        base = metric_name[:-6]
        base_desc = METRIC_TOOLTIPS.get(base) or METRIC_TOOLTIPS.get(f"{base}_median")
        if base_desc:
            return f"Range (max - min) for {base_desc.lower()} across runs."

    if metric_name.endswith("_drift_slope"):
        base = metric_name[:-12]
        base_desc = METRIC_TOOLTIPS.get(base) or METRIC_TOOLTIPS.get(f"{base}_median")
        if base_desc:
            return f"Linear drift slope for {base_desc.lower()} across runs. Near zero is better."

    if metric_name.endswith("_drift_pvalue"):
        base = metric_name[:-13]
        base_desc = METRIC_TOOLTIPS.get(base) or METRIC_TOOLTIPS.get(f"{base}_median")
        if base_desc:
            return f"P-value for linear drift test for {base_desc.lower()}. Higher p-value indicates no significant drift."

    if metric_name.endswith("_split_half_reliability"):
        base = metric_name[:-23]
        base_desc = METRIC_TOOLTIPS.get(base) or METRIC_TOOLTIPS.get(f"{base}_median")
        if base_desc:
            return f"Split-half reliability for {base_desc.lower()}. Higher is better (0-1 scale)."

    if metric_name == "spatial_icc":
        return "ICC(2,1) for spatial patterns across runs (Shrout & Fleiss, 1979). Measures absolute agreement. Higher is better (0-1 scale)."

    if metric_name == "overall_consistency":
        return "Overall consistency score across runs. Higher values indicate more consistent data."

    return "No description available."


def get_metric_standard(metric_name: str) -> str:
    """Get good standard value for a metric.

    Returns expected or acceptable values for QA metrics, helping
    users interpret whether their data meets quality standards.

    Parameters
    ----------
    metric_name : str
        Name of the metric

    Returns
    -------
    str
        Standard or acceptable value (e.g., ">40", "0.5 mm", "—")

    Examples
    --------
    >>> get_metric_standard("tsnr_median")
    '>40'
    >>> get_metric_standard("fd_median")
    '<0.2 mm'
    >>> get_metric_standard("tsnr_cv")
    '—'

    Notes
    -----
    Returns "—" for metrics without established standards, such as:
    - Consistency metrics (CV, range, drift)
    - Study-specific metrics
    """
    # Check direct match first
    if metric_name in METRIC_STANDARDS:
        return METRIC_STANDARDS[metric_name]

    # Handle aggregated metrics - use base metric standard
    if metric_name.endswith("_mean"):
        base = metric_name[:-5]
        if base in METRIC_STANDARDS:
            return METRIC_STANDARDS[base]
        base_with_median = f"{base}_median"
        if base_with_median in METRIC_STANDARDS:
            return METRIC_STANDARDS[base_with_median]

    if metric_name.endswith("_median"):
        base = metric_name[:-7]
        if base in METRIC_STANDARDS:
            return METRIC_STANDARDS[base]
        base_with_median = f"{base}_median"
        if base_with_median in METRIC_STANDARDS:
            return METRIC_STANDARDS[base_with_median]

    # Handle consistency metrics - no standard values
    if metric_name.endswith(("_cv", "_range", "_drift_slope", "_drift_pvalue", "_split_half_reliability")):
        return "—"

    if metric_name in ("spatial_icc", "overall_consistency"):
        return ">0.7"

    return "—"
