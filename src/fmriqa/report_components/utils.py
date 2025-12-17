"""Utility functions for QA report generation.

DEPRECATED: This module has been split into focused modules for better organization.
All functions are still available here for backward compatibility via re-exports.

New locations:
- formatting.py: format_run_label, format_metric_name, format_metric_value
- escaping.py: escape_html, escape_js_string, relative_asset_path
- aggregation.py: compute_session_metrics, compute_subject_metrics
- serialization.py: serialize_subject_for_export, serialize_study_for_interactive
- metric_resolver.py: get_metric_tooltip, get_metric_standard
- numeric_constants.py: MAD_TO_STD_FACTOR, EPSILON, Z_SCORE_THRESHOLD, etc.

Users should update imports to use the new module locations.
This re-export wrapper will be maintained indefinitely for compatibility.
"""

# Re-export from new modules for backward compatibility
from .formatting import (
    format_run_label,
    format_metric_name,
    format_metric_value,
)

from .escaping import (
    escape_html,
    escape_js_string,
    relative_asset_path,
)

from .aggregation import (
    compute_session_metrics,
    compute_subject_metrics,
    _safe_float,
    _safe_int,
)

from .serialization import (
    serialize_subject_for_export,
    serialize_study_for_interactive,
)

from .metric_resolver import (
    get_metric_tooltip,
    get_metric_standard,
)

# Make all imports available at module level
__all__ = [
    # Formatting
    'format_run_label',
    'format_metric_name',
    'format_metric_value',
    # Escaping
    'escape_html',
    'escape_js_string',
    'relative_asset_path',
    # Aggregation
    'compute_session_metrics',
    'compute_subject_metrics',
    '_safe_float',
    '_safe_int',
    # Serialization
    'serialize_subject_for_export',
    'serialize_study_for_interactive',
    # Metric resolution
    'get_metric_tooltip',
    'get_metric_standard',
]
