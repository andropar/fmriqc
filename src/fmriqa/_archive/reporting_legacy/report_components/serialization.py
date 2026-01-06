"""Serialization utilities for interactive QA reports.

This module provides functions for serializing QA data structures to
JSON-compatible dictionaries for use in interactive HTML reports.
"""

from datetime import datetime
from typing import Dict, List, Any

import numpy as np

from .aggregation import _safe_float, _safe_int
from .constants import COMPARISON_METRICS


def serialize_subject_for_export(subject: Any, session_consistency: Dict[str, Dict]) -> Dict[str, Any]:
    """Serialize subject data for JSON export in HTML reports.

    Converts SubjectResults to a JSON-serializable dictionary suitable
    for embedding in HTML reports. Handles numpy type conversion and
    includes threshold-relevant metrics for interactive recalculation.

    Parameters
    ----------
    subject : SubjectResults
        Subject results object containing all sessions and runs
    session_consistency : dict
        Session consistency reports keyed by session identifier
        (e.g., "sub-01_ses-1")

    Returns
    -------
    dict
        Serializable dictionary with structure:
        {
            "subject": str,
            "export_timestamp": str (ISO format),
            "sessions": [
                {
                    "session": str,
                    "runs": [...],
                    "aggregate_metrics": dict,
                    "consistency_metrics": dict,
                    "outlier_runs": list,
                    "consistency_analysis": dict (if available)
                }
            ]
        }

    Notes
    -----
    - Numpy types are converted to native Python types
    - NaN values are converted to None
    - Includes threshold_metrics for each run to enable JavaScript
      recalculation of flags with different thresholds
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

    Extracts comparison metrics from all runs in the study and formats
    them for use in interactive scatter plots and visualizations.

    Parameters
    ----------
    study : StudyResults
        Study results object containing all subjects

    Returns
    -------
    dict
        Serializable dictionary with structure:
        {
            "runs": [
                {
                    "id": str (full run identifier),
                    "subject": str,
                    "session": str,
                    "run": str,
                    "task": str,
                    "flags": dict,
                    "metrics": dict (comparison metrics only)
                }
            ],
            "metrics": [
                {
                    "key": str,
                    "label": str,
                    "description": str
                }
            ],
            "subjects": list of str
        }

    Notes
    -----
    Only includes metrics defined in COMPARISON_METRICS constant.
    These are typically the most informative metrics for between-run
    comparisons (e.g., tSNR, FD, GCOR, DVARS).
    """
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
