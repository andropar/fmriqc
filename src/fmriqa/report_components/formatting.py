"""Formatting utilities for QA report display.

This module provides functions for formatting run labels, metric names,
and metric values for human-readable display in QA reports.
"""


def format_run_label(run_id: str) -> str:
    """Normalise run identifiers to the ``run-XX`` format.

    Parameters
    ----------
    run_id : str
        Run identifier (e.g., "run-1", "run-001", "1")

    Returns
    -------
    str
        Normalized run label (e.g., "run-01")

    Examples
    --------
    >>> format_run_label("run-1")
    'run-01'
    >>> format_run_label("sub-01_ses-1_run-3")
    'run-03'
    >>> format_run_label("5")
    'run-05'
    """
    core = run_id
    if "run-" in run_id:
        for part in run_id.split("_"):
            if part.startswith("run-"):
                core = part[4:]
                break
    elif run_id.startswith("run-"):
        core = run_id[4:]
    if core.isdigit():
        core = core.zfill(2)
    return f"run-{core}"


def format_metric_name(metric_name: str) -> str:
    """Format metric name for display.

    Converts snake_case metric names to Title Case with spaces.

    Parameters
    ----------
    metric_name : str
        Metric name in snake_case (e.g., "tsnr_median")

    Returns
    -------
    str
        Formatted metric name (e.g., "Tsnr Median")

    Examples
    --------
    >>> format_metric_name("tsnr_median")
    'Tsnr Median'
    >>> format_metric_name("fd_percent_above")
    'Fd Percent Above'
    """
    return metric_name.replace("_", " ").title()


def format_metric_value(value: float) -> str:
    """Format metric value for display.

    Automatically adjusts decimal precision based on value magnitude:
    - Very small values (<0.01): 6 decimal places
    - Small values (<1): 4 decimal places
    - Medium values (<100): 2 decimal places
    - Large values (>=100): 1 decimal place

    Parameters
    ----------
    value : float
        Metric value to format

    Returns
    -------
    str
        Formatted value string

    Examples
    --------
    >>> format_metric_value(0.00123)
    '0.001230'
    >>> format_metric_value(0.456)
    '0.4560'
    >>> format_metric_value(12.345)
    '12.35'
    >>> format_metric_value(123.45)
    '123.5'
    """
    if isinstance(value, float):
        if abs(value) < 0.01:
            return f"{value:.6f}"
        elif abs(value) < 1:
            return f"{value:.4f}"
        elif abs(value) < 100:
            return f"{value:.2f}"
        else:
            return f"{value:.1f}"
    return str(value)
