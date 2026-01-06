"""Test that module split maintains backward compatibility."""

import pytest


def test_backward_compatible_imports():
    """Test that old imports from utils.py still work."""
    # These should all work via re-exports in utils.py
    from fmriqc.reporting.report_components.utils import (
        format_run_label,
        format_metric_name,
        format_metric_value,
        escape_html,
        escape_js_string,
        relative_asset_path,
        compute_session_metrics,
        compute_subject_metrics,
        serialize_subject_for_export,
        serialize_study_for_interactive,
        get_metric_tooltip,
        get_metric_standard,
        _safe_float,
        _safe_int,
    )

    # Quick functional tests
    assert format_run_label("1") == "run-01"
    assert format_metric_name("tsnr_median") == "Tsnr Median"
    assert escape_html("<script>") == "&lt;script&gt;"
    assert _safe_float(3.14) == 3.14
    assert _safe_int(42) == 42

    print("✓ All backward-compatible imports work")


def test_new_module_imports():
    """Test that new focused module imports work."""
    # Test formatting module
    from fmriqc.reporting.report_components.formatting import (
        format_run_label,
        format_metric_name,
        format_metric_value,
    )
    assert format_run_label("1") == "run-01"

    # Test escaping module
    from fmriqc.reporting.report_components.escaping import (
        escape_html,
        escape_js_string,
        relative_asset_path,
    )
    assert escape_html("<script>") == "&lt;script&gt;"

    # Test aggregation module
    from fmriqc.reporting.report_components.aggregation import (
        compute_session_metrics,
        compute_subject_metrics,
        _safe_float,
        _safe_int,
    )
    assert _safe_float(3.14) == 3.14

    # Test serialization module
    from fmriqc.reporting.report_components.serialization import (
        serialize_subject_for_export,
        serialize_study_for_interactive,
    )
    assert callable(serialize_subject_for_export)

    # Test metric_resolver module
    from fmriqc.reporting.report_components.metric_resolver import (
        get_metric_tooltip,
        get_metric_standard,
    )
    assert callable(get_metric_tooltip)

    # Test numeric_constants module
    from fmriqc.reporting.report_components.numeric_constants import (
        MAD_TO_STD_FACTOR,
        EPSILON,
        Z_SCORE_THRESHOLD,
        MAHALANOBIS_THRESHOLD,
        MC_ROT_RADIUS_MM,
        TSNR_MINIMUM_ACCEPTABLE,
        FD_THRESHOLD_DEFAULT,
        COVERAGE_MINIMUM,
    )
    assert MAD_TO_STD_FACTOR == 1.4826
    assert EPSILON == 1e-6
    assert Z_SCORE_THRESHOLD == 3.0
    assert MC_ROT_RADIUS_MM == 50.0

    print("✓ All new module imports work")


def test_package_level_imports():
    """Test that package-level imports still work."""
    from fmriqc.reporting.report_components import (
        format_run_label,
        format_metric_name,
        escape_html,
        compute_session_metrics,
    )

    assert format_run_label("1") == "run-01"
    assert format_metric_name("tsnr_median") == "Tsnr Median"
    assert escape_html("<script>") == "&lt;script&gt;"

    print("✓ Package-level imports work")


def test_imports_are_identical():
    """Test that imports from old and new locations are identical."""
    from fmriqc.reporting.report_components.utils import format_run_label as old_format
    from fmriqc.reporting.report_components.formatting import format_run_label as new_format

    # Should be the exact same function object
    assert old_format is new_format

    print("✓ Old and new imports are identical (not copies)")


def test_numeric_constants_values():
    """Test that numeric constants have expected values."""
    from fmriqc.reporting.report_components.numeric_constants import (
        MAD_TO_STD_FACTOR,
        EPSILON,
        Z_SCORE_THRESHOLD,
        MC_ROT_RADIUS_MM,
        FD_THRESHOLD_DEFAULT,
    )

    # Test values match expected constants
    assert MAD_TO_STD_FACTOR == pytest.approx(1.4826)
    assert EPSILON == 1e-6
    assert Z_SCORE_THRESHOLD == 3.0
    assert MC_ROT_RADIUS_MM == 50.0
    assert FD_THRESHOLD_DEFAULT == 0.5

    print("✓ Numeric constants have correct values")


if __name__ == "__main__":
    test_backward_compatible_imports()
    test_new_module_imports()
    test_package_level_imports()
    test_imports_are_identical()
    test_numeric_constants_values()
    print("\n✅ All module split tests passed!")
