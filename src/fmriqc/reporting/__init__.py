"""Reporting v2 - New HTML report generation system."""

from .reporting import (
    generate_study_report,
    generate_subject_report,
    compute_metric_distributions,
)

__all__ = [
    "generate_study_report",
    "generate_subject_report",
    "compute_metric_distributions",
]
