"""Helper functions for adding context to metrics (Phase 5).

This module provides functions for:
- Computing percentile rankings for metrics within a study
- Classifying metric values into quality bands (excellent, good, acceptable, poor)
- Formatting metrics with contextual information
"""

from typing import Dict, Optional, Tuple
from .constants import METRIC_THRESHOLDS


def compute_run_percentiles(run_metrics: Dict, metric_distributions: Dict) -> Dict[str, float]:
    """Compute percentile rankings for each metric in a run.

    Args:
        run_metrics: Dictionary of metric values for a single run
        metric_distributions: Study-wide distribution data (from compute_metric_distributions)

    Returns:
        Dictionary mapping metric names to their percentile ranks (0-100)
    """
    percentiles = {}

    for metric_name, value in run_metrics.items():
        if metric_name not in metric_distributions:
            continue

        distribution = metric_distributions[metric_name]
        all_values = distribution.get('all_values', [])

        if not all_values or value is None:
            continue

        # Count how many values are less than or equal to this value
        count_below = sum(1 for v in all_values if v <= value)
        percentile = (count_below / len(all_values)) * 100
        percentiles[metric_name] = percentile

    return percentiles


def classify_metric_value(metric_name: str, value: float) -> Optional[str]:
    """Classify a metric value into quality bands.

    Args:
        metric_name: Name of the metric
        value: The metric value

    Returns:
        Quality classification: 'excellent', 'good', 'acceptable', 'poor', or None if no threshold defined
    """
    if metric_name not in METRIC_THRESHOLDS:
        return None

    thresholds = METRIC_THRESHOLDS[metric_name]
    direction = thresholds['direction']

    if direction == 'higher':
        # Higher values are better
        if value >= thresholds['excellent']:
            return 'excellent'
        elif value >= thresholds['good']:
            return 'good'
        elif value >= thresholds['acceptable']:
            return 'acceptable'
        else:
            return 'poor'
    else:
        # Lower values are better (direction == 'lower')
        if value <= thresholds['excellent']:
            return 'excellent'
        elif value <= thresholds['good']:
            return 'good'
        elif value <= thresholds['acceptable']:
            return 'acceptable'
        else:
            return 'poor'


def get_quality_label(classification: Optional[str]) -> str:
    """Get human-readable label for quality classification.

    Args:
        classification: Quality band ('excellent', 'good', 'acceptable', 'poor')

    Returns:
        Human-readable label
    """
    labels = {
        'excellent': 'Excellent',
        'good': 'Good',
        'acceptable': 'Acceptable',
        'poor': 'Poor',
    }
    return labels.get(classification, 'Unknown')


def get_quality_css_class(classification: Optional[str]) -> str:
    """Get CSS class for quality classification.

    Args:
        classification: Quality band ('excellent', 'good', 'acceptable', 'poor')

    Returns:
        CSS class name
    """
    classes = {
        'excellent': 'quality-excellent',
        'good': 'quality-good',
        'acceptable': 'quality-acceptable',
        'poor': 'quality-poor',
    }
    return classes.get(classification, 'quality-unknown')


def compute_metric_position(metric_name: str, value: float) -> Optional[float]:
    """Compute the position of a value on the threshold scale (0-100).

    This is used to position the indicator on a visual bar showing thresholds.

    Args:
        metric_name: Name of the metric
        value: The metric value

    Returns:
        Position percentage (0-100) or None if no threshold defined
    """
    if metric_name not in METRIC_THRESHOLDS:
        return None

    thresholds = METRIC_THRESHOLDS[metric_name]
    direction = thresholds['direction']

    poor_val = thresholds['poor']
    excellent_val = thresholds['excellent']

    # Clamp value to range
    if direction == 'higher':
        # Scale: poor (0%) to excellent (100%)
        range_size = excellent_val - poor_val
        if range_size <= 0:
            return 50.0
        position = ((value - poor_val) / range_size) * 100
    else:
        # Scale: excellent (0%) to poor (100%) - inverted because lower is better
        range_size = poor_val - excellent_val
        if range_size <= 0:
            return 50.0
        position = ((excellent_val - value) / range_size) * 100

    # Clamp to 0-100
    return max(0.0, min(100.0, position))


def format_metric_with_context(
    metric_name: str,
    value: float,
    percentile: Optional[float] = None,
    classification: Optional[str] = None
) -> Dict[str, any]:
    """Format a metric value with full context information.

    Args:
        metric_name: Name of the metric
        value: The metric value
        percentile: Optional percentile rank (0-100)
        classification: Optional quality classification

    Returns:
        Dictionary with formatted context information
    """
    if classification is None:
        classification = classify_metric_value(metric_name, value)

    position = compute_metric_position(metric_name, value)

    return {
        'value': value,
        'percentile': percentile,
        'classification': classification,
        'quality_label': get_quality_label(classification),
        'quality_class': get_quality_css_class(classification),
        'position': position,
    }
