"""Reporting v2 - New HTML report generation system."""

from .reporting import (
    compute_metric_distributions,
    generate_study_report,
    generate_subject_report,
)

__all__ = [
    "generate_study_report",
    "generate_subject_report",
    "compute_metric_distributions",
]
