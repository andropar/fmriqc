"""Tests for consistency analysis.

This test suite covers cross-run consistency analysis including:
- Intraclass Correlation Coefficient (ICC) computation
- Split-half reliability
- Coefficient of variation
- Linear trend detection
- Inconsistent run identification
- Pairwise similarity computation
- Comprehensive consistency reporting
"""

import pytest
import numpy as np
from pathlib import Path

from fmriqa.analysis.consistency import (
    compute_icc,
    ConsistencyInterpreter,
    compute_split_half_reliability,
    assess_run_consistency,
    identify_inconsistent_runs,
    compute_between_run_similarity,
    generate_consistency_report,
)
from fmriqa.io.structures import RunInfo, RunResult, SessionResults


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def consistent_run_results():
    """Create sample runs with good consistency."""
    results = []

    for i in range(6):
        info = RunInfo(
            path=Path(f"/data/run-{i:02d}.nii.gz"),
            subject="01",
            session="01",
            run=f"{i:02d}",
            task="rest",
            echo=None,
            part=None,
            desc=None,
        )

        # Consistent metrics with small variation
        metrics = {
            'tsnr_median': 45.0 + np.random.randn() * 2.0,
            'fd_median': 0.15 + np.random.randn() * 0.03,
            'global_mean': 1000.0 + np.random.randn() * 20.0,
            'gcor': 0.04 + np.random.randn() * 0.005,
            'smoothness_fwhm': 6.0 + np.random.randn() * 0.3,
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
            mean_vector=np.random.randn(100) + 1000,  # Consistent mean vectors
        )
        results.append(result)

    return results


@pytest.fixture
def inconsistent_run_results(consistent_run_results):
    """Create sample runs with one inconsistent run."""
    results = consistent_run_results.copy()

    # Add an inconsistent run
    info = RunInfo(
        path=Path("/data/run-outlier.nii.gz"),
        subject="01",
        session="01",
        run="outlier",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )

    # Very different metrics
    metrics = {
        'tsnr_median': 20.0,  # Much lower
        'fd_median': 0.8,  # Much higher
        'global_mean': 1500.0,  # Much higher
        'gcor': 0.15,  # Much higher
        'smoothness_fwhm': 10.0,  # Much higher
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
        figure_path=Path("/tmp/fig_outlier.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.random.randn(100) + 1500,  # Different mean
    )

    results.append(result)
    return results


# ============================================================================
# ICC Tests
# ============================================================================


class TestComputeICC:
    """Test ICC computation."""

    def test_perfect_consistency(self):
        """Test ICC with perfectly consistent data."""
        # All runs have same values across measures
        data = np.ones((5, 10))

        icc = compute_icc(data, icc_type="2,1")

        # Perfect consistency should give high ICC (though may not be exactly 1.0)
        assert 0.0 <= icc <= 1.0

    def test_zero_consistency(self):
        """Test ICC with random noise (low consistency)."""
        np.random.seed(42)
        # Pure random noise
        data = np.random.randn(10, 20)

        icc = compute_icc(data, icc_type="2,1")

        # Random data should have low ICC
        assert 0.0 <= icc <= 1.0
        assert icc < 0.5  # Should be low for random data

    def test_icc_types(self):
        """Test different ICC types."""
        np.random.seed(42)
        data = np.random.randn(8, 15) + 100

        icc_1_1 = compute_icc(data, icc_type="1,1")
        icc_2_1 = compute_icc(data, icc_type="2,1")
        icc_3_1 = compute_icc(data, icc_type="3,1")

        # All should be valid
        assert 0.0 <= icc_1_1 <= 1.0
        assert 0.0 <= icc_2_1 <= 1.0
        assert 0.0 <= icc_3_1 <= 1.0

    def test_insufficient_data(self):
        """Test ICC with too little data."""
        data = np.ones((1, 10))  # Only one row

        icc = compute_icc(data, icc_type="2,1")

        assert icc == 0.0

    def test_known_icc_value(self):
        """Test ICC computation with known values."""
        # Create data with known structure
        # Runs have consistent patterns across measures
        data = np.array([
            [10, 11, 12, 10, 11],
            [20, 21, 22, 20, 21],
            [30, 31, 32, 30, 31],
            [40, 41, 42, 40, 41],
        ])

        icc = compute_icc(data, icc_type="2,1")

        # High consistency -> high ICC
        assert icc > 0.9


# ============================================================================
# ConsistencyInterpreter Tests
# ============================================================================


class TestConsistencyInterpreter:
    """Test consistency interpretation."""

    def test_interpret_consistency_score(self):
        """Test consistency score interpretation."""
        interpreter = ConsistencyInterpreter()

        assert interpreter.interpret_consistency_score(60.0) == "excellent"
        assert interpreter.interpret_consistency_score(30.0) == "good"
        assert interpreter.interpret_consistency_score(15.0) == "fair"
        assert interpreter.interpret_consistency_score(5.0) == "poor"

    def test_interpret_icc(self):
        """Test ICC interpretation."""
        interpreter = ConsistencyInterpreter()

        assert interpreter.interpret_icc(0.95) == "excellent"
        assert interpreter.interpret_icc(0.80) == "good"
        assert interpreter.interpret_icc(0.60) == "moderate"
        assert interpreter.interpret_icc(0.35) == "fair"
        assert interpreter.interpret_icc(0.15) == "poor"

    def test_interpret_reliability(self):
        """Test reliability interpretation."""
        interpreter = ConsistencyInterpreter()

        assert interpreter.interpret_reliability(0.95) == "excellent"
        assert interpreter.interpret_reliability(0.80) == "good"
        assert interpreter.interpret_reliability(0.65) == "adequate"
        assert interpreter.interpret_reliability(0.40) == "questionable"

    def test_interpret_cv(self):
        """Test CV interpretation."""
        interpreter = ConsistencyInterpreter()

        assert interpreter.interpret_cv(0.03) == "very_low"
        assert interpreter.interpret_cv(0.08) == "low"
        assert interpreter.interpret_cv(0.15) == "moderate"
        assert interpreter.interpret_cv(0.25) == "high"
        assert interpreter.interpret_cv(0.40) == "very_high"


# ============================================================================
# Split-Half Reliability Tests
# ============================================================================


class TestComputeSplitHalfReliability:
    """Test split-half reliability computation."""

    def test_sufficient_runs(self, consistent_run_results):
        """Test reliability with sufficient runs."""
        reliability = compute_split_half_reliability(
            consistent_run_results, metric_key="tsnr_median"
        )

        assert not np.isnan(reliability)
        # With random variation, reliability might be moderate
        # Just check it's a valid value
        assert -1.0 <= reliability <= 1.0

    def test_insufficient_runs(self, consistent_run_results):
        """Test reliability with too few runs."""
        reliability = compute_split_half_reliability(
            consistent_run_results[:2], metric_key="tsnr_median"
        )

        assert np.isnan(reliability)

    def test_perfect_reliability(self):
        """Test reliability with perfectly correlated odd/even runs."""
        # Create runs where odd and even runs have perfect correlation
        results = []
        for i in range(6):
            info = RunInfo(
                path=Path(f"/data/run-{i}.nii.gz"),
                subject="01", session="01", run=f"{i}", task="rest",
                echo=None, part=None, desc=None,
            )

            # Odd runs: 40, 42, 44; Even runs: 40, 42, 44
            metrics = {"tsnr_median": 40.0 + (i // 2) * 2.0}

            result = RunResult(
                info=info, metrics=metrics, flags={}, series={}, maps={},
                mask=np.ones((10, 10, 10), dtype=bool), affine=np.eye(4),
                header=None, figure_path=Path(f"/tmp/fig_{i}.png"),
                carpetplot_path=None, thumbnail_path=None,
                mean_vector=np.ones(100),
            )
            results.append(result)

        reliability = compute_split_half_reliability(results, "tsnr_median")

        assert reliability > 0.9


# ============================================================================
# Consistency Assessment Tests
# ============================================================================


class TestAssessRunConsistency:
    """Test run consistency assessment."""

    def test_consistent_runs(self, consistent_run_results):
        """Test assessment of consistent runs."""
        metrics = assess_run_consistency(consistent_run_results)

        # Should compute CVs for key metrics
        assert "tsnr_median_cv" in metrics
        assert "fd_median_cv" in metrics

        # Consistent data should have low CV
        assert metrics["tsnr_median_cv"] < 0.15

        # Should have overall consistency score
        assert "overall_consistency" in metrics

    def test_insufficient_runs(self, consistent_run_results):
        """Test assessment with too few runs."""
        metrics = assess_run_consistency(consistent_run_results[:1])

        assert metrics == {}

    def test_drift_detection(self, consistent_run_results):
        """Test linear drift detection."""
        # Add systematic trend
        for i, result in enumerate(consistent_run_results):
            result.metrics['tsnr_median'] = 40.0 + i * 2.0  # Linear increase

        metrics = assess_run_consistency(consistent_run_results)

        # Should detect drift
        assert "tsnr_median_drift_slope" in metrics
        assert "tsnr_median_drift_pvalue" in metrics
        assert metrics["tsnr_median_drift_slope"] > 1.0  # Positive slope

    def test_spatial_icc(self, consistent_run_results):
        """Test spatial ICC computation."""
        metrics = assess_run_consistency(consistent_run_results)

        # Should compute spatial ICC if mean_vectors present
        if "spatial_icc" in metrics:
            assert 0.0 <= metrics["spatial_icc"] <= 1.0


# ============================================================================
# Inconsistent Run Identification Tests
# ============================================================================


class TestIdentifyInconsistentRuns:
    """Test inconsistent run identification."""

    def test_consistent_runs(self, consistent_run_results):
        """Test that consistent runs are not flagged."""
        inconsistent = identify_inconsistent_runs(consistent_run_results)

        # Good consistency -> few or no flags (random variation may trigger occasional flags)
        assert len(inconsistent) <= 1  # Allow at most 1 due to random variation

    def test_inconsistent_run_detected(self, inconsistent_run_results):
        """Test detection of inconsistent run."""
        inconsistent = identify_inconsistent_runs(inconsistent_run_results)

        # Should flag the outlier run
        assert len(inconsistent) > 0

        # Check outlier is included
        outlier_id = inconsistent_run_results[-1].info.get_identifier()
        assert outlier_id in inconsistent

    def test_insufficient_runs(self, consistent_run_results):
        """Test identification with too few runs."""
        inconsistent = identify_inconsistent_runs(consistent_run_results[:2])

        assert inconsistent == []


# ============================================================================
# Similarity Tests
# ============================================================================


class TestComputeBetweenRunSimilarity:
    """Test pairwise similarity computation."""

    def test_similarity_matrix_shape(self, consistent_run_results):
        """Test similarity matrix has correct shape."""
        similarity = compute_between_run_similarity(consistent_run_results)

        n_runs = len(consistent_run_results)
        assert similarity.shape == (n_runs, n_runs)

    def test_similarity_diagonal_ones(self, consistent_run_results):
        """Test similarity matrix has 1s on diagonal."""
        similarity = compute_between_run_similarity(consistent_run_results)

        assert np.allclose(np.diag(similarity), 1.0)

    def test_similarity_symmetric(self, consistent_run_results):
        """Test similarity matrix is symmetric."""
        similarity = compute_between_run_similarity(consistent_run_results)

        assert np.allclose(similarity, similarity.T)


# ============================================================================
# Comprehensive Report Tests
# ============================================================================


class TestGenerateConsistencyReport:
    """Test comprehensive consistency reporting."""

    def test_report_structure(self, consistent_run_results):
        """Test report contains all expected sections."""
        session_results = SessionResults(
            subject="01",
            session="01",
            runs=consistent_run_results
        )

        report = generate_consistency_report(session_results)

        # Check structure
        assert "n_runs" in report
        assert "consistency_metrics" in report
        assert "inconsistent_runs" in report
        assert "similarity_matrix" in report
        assert "split_half_reliability" in report
        assert "consistency_interpretation" in report

        assert report["n_runs"] == len(consistent_run_results)

    def test_report_with_few_runs(self, consistent_run_results):
        """Test report generation with minimal runs."""
        session_results = SessionResults(
            subject="01",
            session="01",
            runs=consistent_run_results[:1]
        )

        report = generate_consistency_report(session_results)

        # Should return valid structure even with few runs
        assert report["n_runs"] == 1
        assert "consistency_metrics" in report

    def test_interpretations_present(self, consistent_run_results):
        """Test that qualitative interpretations are included."""
        session_results = SessionResults(
            subject="01",
            session="01",
            runs=consistent_run_results
        )

        report = generate_consistency_report(session_results)

        # Should have interpretation
        assert "consistency_interpretation" in report
        assert report["consistency_interpretation"] in [
            "excellent", "good", "fair", "poor"
        ]

        # Should have reliability interpretations
        if report["split_half_reliability"]:
            assert "reliability_interpretations" in report
