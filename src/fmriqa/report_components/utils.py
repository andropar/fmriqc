"""Utility functions for QA report generation.

This module contains helper functions for formatting, escaping,
and computing aggregate metrics.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np

from .constants import METRIC_TOOLTIPS, METRIC_STANDARDS


def _safe_float(value):
    """Convert to float, handling numpy types and NaN."""
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        value = float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return float(value)


def _safe_int(value):
    """Convert to int, handling numpy types."""
    if value is None:
        return None
    if isinstance(value, (np.floating, np.integer)):
        return int(value)
    return int(value)


def format_run_label(run_id: str) -> str:
    """Normalise run identifiers to the ``run-XX`` format."""
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
    """Format metric name for display."""
    return metric_name.replace("_", " ").title()


def get_metric_tooltip(metric_name: str) -> str:
    """Get tooltip text for a metric."""
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
    """Get good standard value for a metric."""
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


def format_metric_value(value: float) -> str:
    """Format metric value for display."""
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


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))


def escape_js_string(text: str) -> str:
    """Escape string for use in JavaScript string literals."""
    return (text.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", "\\r"))


def relative_asset_path(path: Optional[Path], base: Path) -> str:
    """Return a POSIX-style relative path for assets.

    Returns a string suitable for use in HTML src/href attributes.
    If the path cannot be made relative, returns a relative path using os.path.relpath.
    """
    import os

    if path is None:
        return ""
    path = path.resolve()
    base = base.resolve()
    try:
        rel = path.relative_to(base)
    except ValueError:
        rel = Path(os.path.relpath(path, base))
    return rel.as_posix()


def compute_session_metrics(runs: List[Any]) -> Dict[str, float]:
    """Compute aggregate metrics for a session.

    Parameters
    ----------
    runs : list
        List of RunResult objects

    Returns
    -------
    dict
        Aggregated metrics with _mean and _median suffixes
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

    Parameters
    ----------
    sessions : list
        List of SessionResults objects

    Returns
    -------
    dict
        Aggregated metrics with _mean and _median suffixes
    """
    all_runs = [run for session in sessions for run in session.runs]
    return compute_session_metrics(all_runs)


def serialize_subject_for_export(subject: Any, session_consistency: Dict[str, Dict]) -> Dict[str, Any]:
    """Serialize subject data for JSON export in HTML reports.

    Parameters
    ----------
    subject : SubjectResults
        Subject results object
    session_consistency : dict
        Session consistency reports keyed by session identifier

    Returns
    -------
    dict
        Serializable dictionary for JSON export
    """
    data = {
        "subject": subject.subject,
        "export_timestamp": datetime.now().isoformat(),
        "sessions": []
    }

    for session in subject.sessions:
        session_data = {
            "session": session.session,
            "runs": [],
            "aggregate_metrics": session.aggregate_metrics,
            "consistency_metrics": session.consistency_metrics,
            "outlier_runs": session.outlier_runs,
        }

        # Add session consistency if available
        session_key = f"sub-{subject.subject}_ses-{session.session}"
        if session_key in session_consistency:
            session_data["consistency_analysis"] = session_consistency[session_key]

        for run in session.runs:
            run_data = {
                "run": run.info.run,
                "task": run.info.task,
                "echo": run.info.echo,
                "metrics": {},
                "flags": run.flags,
                "warnings": run.warnings,
            }
            # Convert numpy types to native Python types
            for key, value in run.metrics.items():
                if isinstance(value, (np.floating, np.integer)):
                    run_data["metrics"][key] = float(value) if isinstance(value, np.floating) else int(value)
                elif isinstance(value, float) and np.isnan(value):
                    run_data["metrics"][key] = None
                else:
                    run_data["metrics"][key] = value

            # Add threshold-relevant metrics for JavaScript flag recalculation
            run_data["threshold_metrics"] = {
                "tsnr_median": _safe_float(run.metrics.get("tsnr_median")),
                "dvars_percent_above": _safe_float(run.metrics.get("dvars_percent_above")),
                "outlier_percent_above": _safe_float(run.metrics.get("outlier_percent_above")),
                "fd_percent_above": _safe_float(run.metrics.get("fd_percent_above")),
                "fd_median": _safe_float(run.metrics.get("fd_median")),
                "n_hyperintense_slices": _safe_int(run.metrics.get("n_hyperintense_slices", 0)),
                "slice_outlier_max": _safe_float(run.metrics.get("slice_outlier_max")),
                "mask_components": _safe_int(run.metrics.get("mask_components", 1)),
                "physiological_power_ratio": _safe_float(run.metrics.get("physiological_power_ratio")),
            }

            session_data["runs"].append(run_data)

        data["sessions"].append(session_data)

    return data


def serialize_study_for_interactive(study: Any) -> Dict[str, Any]:
    """Serialize all run data for interactive JavaScript charts.

    Parameters
    ----------
    study : StudyResults
        Study results object

    Returns
    -------
    dict
        Serializable dictionary for interactive charts
    """
    from .constants import COMPARISON_METRICS

    runs_data = []

    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                run_entry = {
                    "id": run.info.get_identifier(),
                    "subject": subject.subject,
                    "session": session.session,
                    "run": run.info.run,
                    "task": run.info.task or "",
                    "flags": run.flags,
                    "metrics": {},
                }
                # Extract comparison metrics
                for metric_key, _, _ in COMPARISON_METRICS:
                    val = run.metrics.get(metric_key)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        run_entry["metrics"][metric_key] = float(val)
                    else:
                        run_entry["metrics"][metric_key] = None

                runs_data.append(run_entry)

    return {
        "runs": runs_data,
        "metrics": [{"key": k, "label": l, "description": d} for k, l, d in COMPARISON_METRICS],
        "subjects": [s.subject for s in study.subjects],
    }
