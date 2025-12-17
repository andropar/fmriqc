"""Modular components for QA report generation.

This package provides reusable components for generating QA reports:

Core modules:
- constants.py: Metric tooltips, standards, and flag descriptions
- numeric_constants.py: Numeric constants and thresholds (NEW in Phase 3)
- section_renderers.py: Functions for rendering report sections
- badge_helpers.py: Badge generation for run quality metrics
- thumbnail_helpers.py: Thumbnail management and card generation

Utility modules (NEW in Phase 3 - focused split):
- formatting.py: Run label and metric name/value formatting
- escaping.py: HTML/JS escaping and path utilities
- aggregation.py: Metric aggregation across runs/sessions
- serialization.py: JSON export for interactive reports
- metric_resolver.py: Metric tooltip and standard value lookup
- utils.py: Backward-compatibility re-export wrapper (DEPRECATED)

DEPRECATED:
- styles.py: CSS has been moved to static/css/styles.css
- scripts.py: JavaScript has been moved to static/js/*.js modules

Usage:
    # Use the modular components directly
    from fmriqa.report_components.constants import METRIC_TOOLTIPS
    from fmriqa.report_components.formatting import format_run_label
    from fmriqa.report_components.numeric_constants import FD_THRESHOLD_DEFAULT

    # Legacy imports still work via utils.py (backward compatibility):
    from fmriqa.report_components.utils import format_run_label

    # For full report generation, use the reporting module:
    from fmriqa.reporting import generate_subject_report, generate_study_report

Note: This subpackage provides standalone utilities.
The main report generation functions are in fmriqa.reporting.
"""

# Export constants for direct use
from .constants import (
    METRIC_TOOLTIPS,
    METRIC_STANDARDS,
    FLAG_DESCRIPTIONS,
    COMPARISON_METRICS,
)

# Export utility functions
from .utils import (
    format_run_label,
    format_metric_name,
    get_metric_tooltip,
    get_metric_standard,
    format_metric_value,
    escape_html,
    escape_js_string,
    relative_asset_path,
    compute_session_metrics,
    compute_subject_metrics,
    serialize_subject_for_export,
    serialize_study_for_interactive,
)

# Export section renderers
from .section_renderers import (
    render_metrics_table,
    render_metrics_summary,
)

# Export badge helpers
from .badge_helpers import (
    get_outlier_badge,
    get_fd_badge,
    get_coverage_badge,
    get_flag_badge,
)

# Export thumbnail helpers
from .thumbnail_helpers import (
    ensure_thumbnail,
    build_thumbnail_cards,
)

__all__ = [
    # Constants
    "METRIC_TOOLTIPS",
    "METRIC_STANDARDS",
    "FLAG_DESCRIPTIONS",
    "COMPARISON_METRICS",
    # Utils
    "format_run_label",
    "format_metric_name",
    "get_metric_tooltip",
    "get_metric_standard",
    "format_metric_value",
    "escape_html",
    "escape_js_string",
    "relative_asset_path",
    "compute_session_metrics",
    "compute_subject_metrics",
    "serialize_subject_for_export",
    "serialize_study_for_interactive",
    # Section renderers
    "render_metrics_table",
    "render_metrics_summary",
    # Badge helpers
    "get_outlier_badge",
    "get_fd_badge",
    "get_coverage_badge",
    "get_flag_badge",
    # Thumbnail helpers
    "ensure_thumbnail",
    "build_thumbnail_cards",
]
