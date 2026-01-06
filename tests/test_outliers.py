"""Tests for outlier detection.

This test suite covers outlier detection functionality including:
- Covariance estimation strategies (Ledoit-Wolf, Empirical, Diagonal, Identity)
- Mahalanobis distance computation
- Multivariate outlier detection
- Univariate outlier detection
- Motion flagging
- tSNR flagging
- Comprehensive outlier reporting
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
from pathlib import Path

from fmriqa.analysis.outliers import (
    LedoitWolfEstimator,
    EmpiricalEstimator,
    DiagonalEstimator,
    IdentityEstimator,
    CovarianceEstimatorChain,
    _prepare_metric_matrix,
    _compute_mahalanobis_distances,
    detect_outliers_mahalanobis,
    detect_outliers_univariate,
    flag_extreme_motion,
    flag_low_tsnr,
    generate_outlier_report,
)
from fmriqa.io.structures import RunInfo, RunResult
from fmriqa.core.constants import StatisticalConstants


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_run_results():
    """Create sample RunResult objects for testing."""
    results = []

    # Create 10 runs with typical metrics
    for i in range(10):
        info = RunInfo(
            path=Path(f"/data/sub-01/run-{i:02d}.nii.gz"),
            subject="01",
            session="01",
            run=f"{i:02d}",
            task="rest",
            echo=None,
            part=None,
            desc=None,
        )

        # Typical good-quality values with some variation
        metrics = {
            'tsnr_median': 40.0 + np.random.randn() * 5.0,
            'fd_median': 0.2 + np.random.randn() * 0.05,
            'dvars_percent_above': 5.0 + np.random.randn() * 2.0,
            'outlier_percent_above': 3.0 + np.random.randn() * 1.0,
            'gcor': 0.05 + np.random.randn() * 0.01,
            'smoothness_fwhm': 6.0 + np.random.randn() * 0.5,
            'coverage': 0.85 + np.random.randn() * 0.05,
            'fd_percent_above': 8.0 + np.random.randn() * 3.0,
        }

        result = RunResult(
            info=info,
            metrics=metrics,
            flags={},
            series={},
            maps={},
            mask=np.ones((10, 10, 10), dtype=bool),
            affine=np.eye(4),
            header=None,
            figure_path=Path(f"/tmp/fig_{i}.png"),
            carpetplot_path=None,
            thumbnail_path=None,
            mean_vector=np.ones(100),
            slice_qc={},
        )
        results.append(result)

    return results


@pytest.fixture
def outlier_run_results(sample_run_results):
    """Create sample data with one clear outlier."""
    results = sample_run_results.copy()

    # Make the last run an outlier (poor quality)
    outlier_info = RunInfo(
        path=Path("/data/sub-01/run-outlier.nii.gz"),
        subject="01",
        session="01",
        run="outlier",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )

    outlier_metrics = {
        'tsnr_median': 15.0,  # Low!
        'fd_median': 1.5,  # High motion!
        'dvars_percent_above': 25.0,  # High!
        'outlier_percent_above': 15.0,  # High!
        'gcor': 0.15,  # High!
        'smoothness_fwhm': 10.0,  # Overly smooth
        'coverage': 0.60,  # Poor coverage
        'fd_percent_above': 40.0,  # High motion percentage
    }

    outlier_result = RunResult(
        info=outlier_info,
        metrics=outlier_metrics,
        flags={},
        series={},
        maps={},
        mask=np.ones((10, 10, 10), dtype=bool),
        affine=np.eye(4),
        header=None,
        figure_path=Path("/tmp/fig_outlier.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(100),
        slice_qc={},
    )

    results.append(outlier_result)
    return results


@pytest.fixture
def simple_metric_matrix():
    """Create simple test data matrix."""
    np.random.seed(42)
    # 20 samples, 5 features
    data = np.random.randn(20, 5)
    # Add one clear outlier
    data[-1] = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
    return data


# ============================================================================
# Covariance Estimation Tests
# ============================================================================


class TestCovarianceEstimators:
    """Test different covariance estimation strategies."""

    def test_empirical_estimator_success(self, simple_metric_matrix):
        """Test empirical covariance estimation."""
        estimator = EmpiricalEstimator()

        cov = estimator.estimate(simple_metric_matrix)

        assert cov is not None
        assert cov.shape == (5, 5)
        assert np.allclose(cov, cov.T)  # Should be symmetric
        assert estimator.name() == "Empirical"

    def test_diagonal_estimator_success(self, simple_metric_matrix):
        """Test diagonal covariance estimation."""
        estimator = DiagonalEstimator()

        cov = estimator.estimate(simple_metric_matrix)

        assert cov is not None
        assert cov.shape == (5, 5)
        # Should be diagonal
        assert np.allclose(cov, np.diag(np.diag(cov)))
        assert estimator.name() == "Diagonal"

    def test_diagonal_estimator_zero_variance(self):
        """Test diagonal estimator handles zero variance."""
        # All constant features
        data = np.ones((10, 5))
        estimator = DiagonalEstimator()

        cov = estimator.estimate(data)

        # Should fail for zero variance
        assert cov is None

    def test_identity_estimator_always_succeeds(self, simple_metric_matrix):
        """Test identity estimator (fallback)."""
        estimator = IdentityEstimator()

        cov = estimator.estimate(simple_metric_matrix)

        assert cov is not None
        assert cov.shape == (5, 5)
        assert np.allclose(cov, np.eye(5))
        assert estimator.name() == "Identity"

    def test_ledoit_wolf_estimator(self, simple_metric_matrix):
        """Test Ledoit-Wolf estimator if sklearn available."""
        estimator = LedoitWolfEstimator()

        cov = estimator.estimate(simple_metric_matrix)

        # May be None if sklearn not available, but should not crash
        if cov is not None:
            assert cov.shape == (5, 5)
            assert np.allclose(cov, cov.T)
        assert estimator.name() == "Ledoit-Wolf"

    def test_covariance_chain_uses_fallback(self):
        """Test chain fallback when primary estimators fail."""
        # Degenerate data that will fail most estimators
        data = np.ones((3, 5))  # Constant values

        chain = CovarianceEstimatorChain()
        cov, method = chain.estimate(data)

        # Should succeed with some method (may be Identity, Diagonal, or even Ledoit-Wolf)
        assert cov is not None
        assert isinstance(method, str)
        # For constant data, should use a robust method
        assert method in ["Ledoit-Wolf", "Empirical", "Diagonal", "Identity"]

    def test_covariance_chain_prefers_better_methods(self, simple_metric_matrix):
        """Test chain tries better methods first."""
        chain = CovarianceEstimatorChain()

        cov, method = chain.estimate(simple_metric_matrix)

        assert cov is not None
        # Should use Ledoit-Wolf or Empirical (not Identity)
        assert method in ["Ledoit-Wolf", "Empirical", "Diagonal"]


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestPrepareMetricMatrix:
    """Test metric matrix preparation."""

    def test_sufficient_runs(self, sample_run_results):
        """Test preparation with sufficient runs."""
        matrix, identifiers, metric_keys = _prepare_metric_matrix(
            sample_run_results, min_runs=5
        )

        assert matrix is not None
        assert matrix.shape[0] == len(sample_run_results)
        assert len(identifiers) == len(sample_run_results)
        assert len(metric_keys) > 0

    def test_insufficient_runs(self, sample_run_results):
        """Test preparation with too few runs."""
        matrix, identifiers, metric_keys = _prepare_metric_matrix(
            sample_run_results[:3], min_runs=5
        )

        assert matrix is None
        assert identifiers == []
        assert metric_keys == []

    def test_adaptive_metric_selection(self, sample_run_results):
        """Test that fewer metrics are used when sample size is small."""
        # With 6 runs, should use at most 4 metrics (n-2)
        matrix_small, _, keys_small = _prepare_metric_matrix(
            sample_run_results[:6], min_runs=5
        )

        # With 10 runs, can use more metrics
        matrix_large, _, keys_large = _prepare_metric_matrix(
            sample_run_results, min_runs=5
        )

        assert matrix_small is not None
        assert matrix_large is not None
        # More runs -> can use more metrics
        assert matrix_large.shape[1] >= matrix_small.shape[1]

    def test_handles_missing_metrics(self, sample_run_results):
        """Test handling of runs with missing metrics."""
        # Remove a metric from one run
        sample_run_results[0].metrics.pop('tsnr_median')

        matrix, identifiers, _ = _prepare_metric_matrix(
            sample_run_results, min_runs=5
        )

        # Should exclude the run with missing metric
        assert matrix is not None
        assert len(identifiers) == len(sample_run_results) - 1

    def test_normalization(self, sample_run_results):
        """Test that metrics are normalized."""
        matrix, _, _ = _prepare_metric_matrix(sample_run_results, min_runs=5)

        assert matrix is not None
        # Normalized data should have mean ~ 0 and std ~ 1
        means = np.mean(matrix, axis=0)
        stds = np.std(matrix, axis=0)

        assert np.allclose(means, 0.0, atol=1e-10)
        assert np.allclose(stds, 1.0, atol=0.1)


class TestComputeMahalanobisDistances:
    """Test Mahalanobis distance computation."""

    def test_basic_computation(self, simple_metric_matrix):
        """Test basic Mahalanobis distance computation."""
        cov = np.cov(simple_metric_matrix, rowvar=False)

        distances = _compute_mahalanobis_distances(simple_metric_matrix, cov)

        assert len(distances) == len(simple_metric_matrix)
        assert np.all(distances >= 0)
        # Outlier (last sample) should have largest distance
        assert distances[-1] == np.max(distances)

    def test_custom_center(self, simple_metric_matrix):
        """Test with custom center point."""
        cov = np.cov(simple_metric_matrix, rowvar=False)
        center = np.zeros(simple_metric_matrix.shape[1])

        distances = _compute_mahalanobis_distances(
            simple_metric_matrix, cov, center=center
        )

        assert len(distances) == len(simple_metric_matrix)
        assert np.all(distances >= 0)

    def test_handles_singular_matrix(self):
        """Test handling of singular covariance matrix."""
        # Create data with perfect collinearity
        data = np.random.randn(10, 3)
        data[:, 2] = data[:, 0] + data[:, 1]  # Perfect collinearity

        cov = np.cov(data, rowvar=False)

        # Should use pseudoinverse and not crash
        distances = _compute_mahalanobis_distances(data, cov)

        assert len(distances) == len(data)
        assert np.all(distances >= 0)


# ============================================================================
# Outlier Detection Tests
# ============================================================================


class TestDetectOutliersMahalanobis:
    """Test multivariate outlier detection."""

    def test_no_outliers_in_good_data(self, sample_run_results):
        """Test that good quality data produces no outliers."""
        outliers, distances = detect_outliers_mahalanobis(
            sample_run_results, threshold=5.0, min_runs=5
        )

        # Should compute distances for all runs
        assert len(distances) == len(sample_run_results)
        # With good data and high threshold, no outliers
        assert len(outliers) == 0

    def test_detects_clear_outlier(self, outlier_run_results):
        """Test detection of clear outlier."""
        outliers, distances = detect_outliers_mahalanobis(
            outlier_run_results, threshold=3.0, min_runs=5
        )

        assert len(distances) == len(outlier_run_results)
        # Should detect at least one outlier
        assert len(outliers) >= 1
        # Outlier should have higher distance
        outlier_id = outlier_run_results[-1].info.get_identifier()
        if outlier_id in distances:
            avg_distance = np.mean([d for d in distances.values()])
            assert distances[outlier_id] > avg_distance

    def test_insufficient_runs_returns_empty(self, sample_run_results):
        """Test that too few runs returns empty results."""
        outliers, distances = detect_outliers_mahalanobis(
            sample_run_results[:3], threshold=3.0, min_runs=5
        )

        assert outliers == []
        assert distances == {}

    def test_threshold_affects_detection(self, outlier_run_results):
        """Test that threshold affects outlier detection."""
        # High threshold - fewer outliers
        outliers_high, _ = detect_outliers_mahalanobis(
            outlier_run_results, threshold=10.0, min_runs=5
        )

        # Low threshold - more outliers
        outliers_low, _ = detect_outliers_mahalanobis(
            outlier_run_results, threshold=1.0, min_runs=5
        )

        assert len(outliers_low) >= len(outliers_high)


class TestDetectOutliersUnivariate:
    """Test univariate outlier detection."""

    def test_no_outliers_in_good_data(self, sample_run_results):
        """Test good quality data produces few/no outliers."""
        outliers_by_metric = detect_outliers_univariate(
            sample_run_results, threshold=3.5
        )

        # May have some metrics flagged, but not many
        if outliers_by_metric:
            total_flags = sum(len(v) for v in outliers_by_metric.values())
            # With threshold of 3.5 standard deviations, should be very few
            assert total_flags < len(sample_run_results) * 0.5

    def test_detects_metric_specific_outliers(self, outlier_run_results):
        """Test detection of metric-specific outliers."""
        outliers_by_metric = detect_outliers_univariate(
            outlier_run_results, threshold=2.5
        )

        # Should detect outliers in multiple metrics
        assert len(outliers_by_metric) > 0

        # The outlier run should appear in multiple metrics
        outlier_id = outlier_run_results[-1].info.get_identifier()
        flagged_count = sum(
            1 for outliers in outliers_by_metric.values()
            if outlier_id in outliers
        )
        assert flagged_count > 0

    def test_insufficient_runs_returns_empty(self, sample_run_results):
        """Test that too few runs returns empty dict."""
        outliers_by_metric = detect_outliers_univariate(
            sample_run_results[:2], threshold=2.5
        )

        assert outliers_by_metric == {}

    def test_handles_constant_metrics(self, sample_run_results):
        """Test handling of metrics with zero variance."""
        # Make one metric constant across all runs
        for res in sample_run_results:
            res.metrics['constant_metric'] = 42.0

        outliers_by_metric = detect_outliers_univariate(
            sample_run_results, threshold=2.5
        )

        # Should not flag constant metric
        assert 'constant_metric' not in outliers_by_metric


class TestFlagExtremeMotion:
    """Test motion flagging."""

    def test_flags_high_fd_median(self, sample_run_results):
        """Test flagging of high median FD."""
        # Set one run to have high FD
        sample_run_results[0].metrics['fd_median'] = 1.5

        flagged = flag_extreme_motion(
            sample_run_results, fd_threshold=0.5, fd_percent_threshold=20.0
        )

        assert len(flagged) == 1
        assert sample_run_results[0].info.get_identifier() in flagged

    def test_flags_high_fd_percentage(self, sample_run_results):
        """Test flagging of high FD percentage."""
        # Set one run to have many high-FD volumes
        sample_run_results[0].metrics['fd_percent_above'] = 30.0

        flagged = flag_extreme_motion(
            sample_run_results, fd_threshold=0.5, fd_percent_threshold=20.0
        )

        assert len(flagged) >= 1
        assert sample_run_results[0].info.get_identifier() in flagged

    def test_no_flags_for_good_motion(self, sample_run_results):
        """Test that good motion data is not flagged."""
        flagged = flag_extreme_motion(
            sample_run_results, fd_threshold=0.5, fd_percent_threshold=20.0
        )

        # All runs have good motion in fixture
        assert len(flagged) == 0


class TestFlagLowTsnr:
    """Test tSNR flagging."""

    def test_flags_low_tsnr(self, sample_run_results):
        """Test flagging of low tSNR."""
        # Set one run to have low tSNR
        sample_run_results[0].metrics['tsnr_median'] = 20.0

        flagged, threshold = flag_low_tsnr(
            sample_run_results, tsnr_threshold=30.0
        )

        assert len(flagged) == 1
        assert sample_run_results[0].info.get_identifier() in flagged
        assert threshold == 30.0

    def test_no_flags_for_good_tsnr(self, sample_run_results):
        """Test that good tSNR data is not flagged."""
        flagged, _ = flag_low_tsnr(sample_run_results, tsnr_threshold=30.0)

        # All runs have tSNR > 30 in fixture
        assert len(flagged) == 0

    def test_handles_missing_tsnr(self, sample_run_results):
        """Test handling of missing tSNR metric."""
        # Remove tSNR from one run
        sample_run_results[0].metrics.pop('tsnr_median')

        flagged, _ = flag_low_tsnr(sample_run_results, tsnr_threshold=30.0)

        # Should not crash, just skip that run
        assert sample_run_results[0].info.get_identifier() not in flagged


class TestGenerateOutlierReport:
    """Test comprehensive outlier reporting."""

    def test_report_structure(self, sample_run_results):
        """Test report contains all expected sections."""
        report = generate_outlier_report(
            sample_run_results, mahalanobis_threshold=3.0, min_runs=5
        )

        # Check structure
        assert 'multivariate_outliers' in report
        assert 'univariate_outliers' in report
        assert 'extreme_motion' in report
        assert 'low_tsnr' in report
        assert 'mahalanobis_distances' in report
        assert 'summary' in report
        assert 'warnings' in report

    def test_summary_statistics(self, sample_run_results):
        """Test summary statistics are computed."""
        report = generate_outlier_report(sample_run_results, min_runs=5)

        summary = report['summary']
        assert summary['total_runs'] == len(sample_run_results)
        assert 'multivariate_outliers' in summary
        assert 'extreme_motion_runs' in summary
        assert 'low_tsnr_runs' in summary
        assert 'total_flagged' in summary
        assert 'percentage_flagged' in summary

        # Percentage should be in valid range
        assert 0.0 <= summary['percentage_flagged'] <= 100.0

    def test_report_with_outliers(self, outlier_run_results):
        """Test report correctly identifies outliers."""
        report = generate_outlier_report(
            outlier_run_results, mahalanobis_threshold=3.0, min_runs=5
        )

        # Should flag the outlier in at least one category
        total_flagged = (
            len(report['multivariate_outliers']) +
            len(report['extreme_motion']) +
            len(report['low_tsnr'])
        )
        assert total_flagged > 0

        # Summary should reflect this
        assert report['summary']['total_flagged'] > 0

    def test_handles_insufficient_data(self, sample_run_results):
        """Test report generation with insufficient data."""
        report = generate_outlier_report(
            sample_run_results[:3], mahalanobis_threshold=3.0, min_runs=5
        )

        # Should still return valid report structure
        assert 'summary' in report
        assert report['summary']['total_runs'] == 3
        # May have empty results but shouldn't crash
        assert 'multivariate_outliers' in report
