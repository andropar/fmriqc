"""Modular components for QA report generation.

This package provides reusable components for generating QA reports:

- constants.py: Metric tooltips, standards, and flag descriptions
- styles.py: CSS stylesheet
- scripts.py: JavaScript for interactivity
- utils.py: Helper functions for formatting and metrics
- section_renderers.py: Functions for rendering report sections
- badge_helpers.py: Badge generation for run quality metrics
- thumbnail_helpers.py: Thumbnail management and card generation

Usage:
    # Use the modular components directly
    from fmriqa.report_components.styles import CSS_STYLE
    from fmriqa.report_components.constants import METRIC_TOOLTIPS
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

# Export CSS
from .styles import CSS_STYLE

# Export script generators
from .scripts import get_subject_report_scripts, get_study_report_scripts

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
    render_alignment_section,
    render_multiecho_section,
    render_analysis_info_section,
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
    # Styles
    "CSS_STYLE",
    # Scripts
    "get_subject_report_scripts",
    "get_study_report_scripts",
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
    "render_alignment_section",
    "render_multiecho_section",
    "render_analysis_info_section",
    # Badge helpers
    "get_outlier_badge",
    "get_fd_badge",
    "get_coverage_badge",
    "get_flag_badge",
    # Thumbnail helpers
    "ensure_thumbnail",
    "build_thumbnail_cards",
]
