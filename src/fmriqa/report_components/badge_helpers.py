"""Badge helper functions for QA reports.

This module contains functions that generate badge text and CSS classes
for displaying run quality metrics in a compact format.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..structures import RunResult


def get_outlier_badge(run: "RunResult") -> tuple[str, str]:
    """Return (label, class) for outlier badge based on outlier_percent_above if available."""
    pct = run.metrics.get("outlier_percent_above")
    if pct is None:
        return ("n/a", "badge-muted")
    if pct <= 5:
        return (f"{pct:.1f}% outliers", "badge-good")
    if pct <= 10:
        return (f"{pct:.1f}% outliers", "badge-warn")
    return (f"{pct:.1f}% outliers", "badge-bad")


def get_fd_badge(run: "RunResult") -> tuple[str, str]:
    """Return (label, class) for framewise displacement badge."""
    fd_med = run.metrics.get("fd_median")
    if fd_med is None:
        return ("FD n/a", "badge-muted")
    if fd_med <= 0.2:
        return (f"FD {fd_med:.2f}", "badge-good")
    if fd_med <= 0.5:
        return (f"FD {fd_med:.2f}", "badge-warn")
    return (f"FD {fd_med:.2f}", "badge-bad")


def get_coverage_badge(run: "RunResult") -> tuple[str, str]:
    """Return (label, class) for brain coverage badge."""
    cov = run.metrics.get("coverage")
    if cov is None:
        return ("Coverage n/a", "badge-muted")
    pct = cov * 100 if cov <= 1 else cov
    if pct >= 95:
        return (f"{pct:.0f}% cov", "badge-good")
    if pct >= 85:
        return (f"{pct:.0f}% cov", "badge-warn")
    return (f"{pct:.0f}% cov", "badge-bad")


def get_flag_badge(run: "RunResult") -> tuple[str, str]:
    """Return (label, class) for QA flags badge."""
    n_flags = sum(1 for v in run.flags.values() if v)
    if n_flags == 0:
        return ("0 flags", "badge-good")
    if n_flags <= 2:
        return (f"{n_flags} flag(s)", "badge-warn")
    return (f"{n_flags} flag(s)", "badge-bad")
