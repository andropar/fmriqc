"""Tests for candidate review recommendations.

This test suite covers exclusion functionality including:
- Exclusion criterion checking
- Run-level exclusion evaluation
- Volume scrubbing recommendations
- Exclusion report generation
- Export to various formats
- Methods text generation
"""

import json
from pathlib import Path

import numpy as np
import pytest

from fmriqc.analysis.exclusions import (
    ExclusionCriteria,
    ExclusionCriterion,
    ExclusionEvaluator,
    ExclusionStringency,
    compute_volume_scrubbing,
    evaluate_run_exclusion,
    export_censor_files,
    export_exclusion_list,
    generate_exclusion_report,
    generate_methods_text,
)
from fmriqc.io.structures import RunInfo, RunResult

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def good_run_result():
    """Create a RunResult with good quality metrics."""
    info = RunInfo(
        path=Path("/data/sub-01_ses-01_run-01_bold.nii.gz"),
        subject="01",
        session="01",
        run="01",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )

    metrics = {
        'fd_median': 0.15,
        'fd_percent_above': 5.0,
        'tsnr_median': 50.0,
        'dvars_percent_above': 3.0,
        'outlier_percent_above': 2.0,
        'coverage_signal_fraction': 0.95,
    }

    fd_series = np.random.randn(100) * 0.05 + 0.15
    dvars_series = np.random.randn(100) * 0.3 + 1.0
    dvars_series[0] = np.nan

    result = RunResult(
        info=info,
        metrics=metrics,
        flags={},
        series={'fd': fd_series, 'dvars_std': dvars_series},
        maps={},
        mask=np.ones((10, 10, 10), dtype=bool),
        affine=np.eye(4),
        header=None,
        figure_path=Path("/tmp/fig.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(100),
    )

    return result


@pytest.fixture
def bad_run_result():
    """Create a RunResult with poor quality metrics."""
    info = RunInfo(
        path=Path("/data/sub-01_ses-01_run-bad_bold.nii.gz"),
        subject="01",
        session="01",
        run="bad",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )

    metrics = {
        'fd_median': 0.8,  # Very high motion
        'fd_percent_above': 45.0,  # Many high-motion volumes
        'tsnr_median': 15.0,  # Low tSNR
        'dvars_percent_above': 30.0,
        'outlier_percent_above': 25.0,
        'coverage_signal_fraction': 0.65,  # Poor coverage
    }

    fd_series = np.random.randn(100) * 0.2 + 0.8
    dvars_series = np.random.randn(100) * 1.0 + 3.0
    dvars_series[0] = np.nan

    result = RunResult(
        info=info,
        metrics=metrics,
        flags={},
        series={'fd': fd_series, 'dvars_std': dvars_series},
        maps={},
        mask=np.ones((10, 10, 10), dtype=bool),
        affine=np.eye(4),
        header=None,
        figure_path=Path("/tmp/fig_bad.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(100),
    )

    return result


# ============================================================================
# ExclusionCriterion Tests
# ============================================================================


class TestExclusionCriterion:
    """Test individual exclusion criterion checking."""

    def test_greater_than_criterion_violated(self):
        """Test criterion with 'gt' comparison when violated."""
        criterion = ExclusionCriterion(
            name='fd_median',
            metric_key='fd_median',
            threshold=0.5,
            comparison='gt',
            reason_template='FD ({value:.2f}) exceeds {threshold}'
        )

        metrics = {'fd_median': 0.8}
        reason = criterion.check(metrics)

        assert reason is not None
        assert 'FD (0.80)' in reason
        assert '0.5' in reason

    def test_greater_than_criterion_passed(self):
        """Test criterion with 'gt' comparison when passed."""
        criterion = ExclusionCriterion(
            name='fd_median',
            metric_key='fd_median',
            threshold=0.5,
            comparison='gt',
            reason_template='FD ({value:.2f}) exceeds {threshold}'
        )

        metrics = {'fd_median': 0.3}
        reason = criterion.check(metrics)

        assert reason is None

    def test_less_than_criterion_violated(self):
        """Test criterion with 'lt' comparison when violated."""
        criterion = ExclusionCriterion(
            name='tsnr_min',
            metric_key='tsnr_median',
            threshold=30.0,
            comparison='lt',
            reason_template='tSNR ({value:.1f}) below {threshold}'
        )

        metrics = {'tsnr_median': 20.0}
        reason = criterion.check(metrics)

        assert reason is not None
        assert 'tSNR (20.0)' in reason
        assert '30.0' in reason

    def test_less_than_criterion_passed(self):
        """Test criterion with 'lt' comparison when passed."""
        criterion = ExclusionCriterion(
            name='tsnr_min',
            metric_key='tsnr_median',
            threshold=30.0,
            comparison='lt',
            reason_template='tSNR ({value:.1f}) below {threshold}'
        )

        metrics = {'tsnr_median': 45.0}
        reason = criterion.check(metrics)

        assert reason is None

    def test_missing_metric_key(self):
        """Test criterion when metric key is missing."""
        criterion = ExclusionCriterion(
            name='test',
            metric_key='nonexistent',
            threshold=1.0,
            comparison='gt',
            reason_template='Test'
        )

        metrics = {'fd_median': 0.5}
        reason = criterion.check(metrics)

        assert reason is None


# ============================================================================
# ExclusionEvaluator Tests
# ============================================================================


class TestExclusionEvaluator:
    """Test exclusion evaluator."""

    def test_evaluator_builds_criteria_list(self):
        """Test that evaluator builds correct criteria list."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
            coverage_min=0.8,
        )

        evaluator = ExclusionEvaluator(criteria)

        assert len(evaluator.criteria_list) == 3
        assert any(c.name == 'fd_median' for c in evaluator.criteria_list)
        assert any(c.name == 'tsnr_min' for c in evaluator.criteria_list)
        assert any(c.name == 'coverage_signal_fraction' for c in evaluator.criteria_list)

    def test_evaluator_skips_none_criteria(self):
        """Test that None criteria are not included."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=None,  # Disabled
            coverage_min=None,  # Disabled
        )

        evaluator = ExclusionEvaluator(criteria)

        assert len(evaluator.criteria_list) == 1
        assert evaluator.criteria_list[0].name == 'fd_median'

    def test_evaluate_good_run_passes(self, good_run_result):
        """Test that good run passes evaluation."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
        )

        evaluator = ExclusionEvaluator(criteria)
        reasons, excluded = evaluator.evaluate(good_run_result)

        assert not excluded
        assert len(reasons) == 0

    def test_evaluate_bad_run_fails(self, bad_run_result):
        """Test that bad run fails evaluation."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
        )

        evaluator = ExclusionEvaluator(criteria)
        reasons, excluded = evaluator.evaluate(bad_run_result)

        assert excluded
        assert len(reasons) == 2  # Both fd_median and tsnr_min violated

    def test_evaluate_with_tsnr_percentile(self, bad_run_result):
        """Test evaluation with tSNR percentile criterion."""
        criteria = ExclusionCriteria(
            tsnr_percentile_min=25.0,
        )

        # Create tSNR values where bad run is in bottom percentile
        tsnr_values = [50.0, 55.0, 60.0, 65.0, 15.0]  # bad run is 15.0

        evaluator = ExclusionEvaluator(criteria)
        reasons, excluded = evaluator.evaluate(
            bad_run_result,
            tsnr_values=tsnr_values
        )

        assert excluded
        assert len(reasons) == 1
        assert reasons[0].criterion == 'tsnr_percentile'

    def test_evaluate_with_mahalanobis(self, bad_run_result):
        """Test evaluation with Mahalanobis distance criterion."""
        criteria = ExclusionCriteria(
            mahalanobis_max=5.0,
        )

        evaluator = ExclusionEvaluator(criteria)
        reasons, excluded = evaluator.evaluate(
            bad_run_result,
            mahalanobis_distance=7.5
        )

        assert excluded
        assert len(reasons) == 1
        assert reasons[0].criterion == 'mahalanobis'
        assert reasons[0].value == 7.5


# ============================================================================
# evaluate_run_exclusion Tests
# ============================================================================


class TestEvaluateRunExclusion:
    """Test run exclusion evaluation."""

    def test_evaluate_good_run(self, good_run_result):
        """Test evaluating good run."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
        )

        exclusion = evaluate_run_exclusion(good_run_result, criteria)

        assert not exclusion.excluded
        assert len(exclusion.reasons) == 0
        assert exclusion.subject == "01"
        assert exclusion.session == "01"
        assert exclusion.run == "01"

    def test_evaluate_bad_run(self, bad_run_result):
        """Test evaluating bad run."""
        criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
        )

        exclusion = evaluate_run_exclusion(bad_run_result, criteria)

        assert exclusion.excluded
        assert len(exclusion.reasons) > 0
        assert exclusion.run == "bad"

    def test_exclusion_to_dict(self, bad_run_result):
        """Test converting exclusion to dictionary."""
        criteria = ExclusionCriteria(fd_median_max=0.5)

        exclusion = evaluate_run_exclusion(bad_run_result, criteria)
        data = exclusion.to_dict()

        assert 'run_id' in data
        assert 'excluded' in data
        assert 'reasons' in data
        assert isinstance(data['reasons'], list)


# ============================================================================
# Volume Scrubbing Tests
# ============================================================================


class TestComputeVolumeScrubbing:
    """Test volume-level scrubbing computation."""

    def test_scrubbing_with_high_fd_volumes(self, good_run_result):
        """Test scrubbing flags high FD volumes."""
        # Add some high FD volumes
        good_run_result.series['fd'][10] = 1.0
        good_run_result.series['fd'][20] = 0.8

        scrubbing = compute_volume_scrubbing(
            good_run_result,
            fd_threshold=0.5,
            dvars_threshold=2.5
        )

        assert scrubbing.n_volumes == 100
        # Should flag volumes 10, 11 (after 10), 20, 21 (after 20)
        assert 10 in scrubbing.flagged_volumes
        assert 11 in scrubbing.flagged_volumes  # Spin history
        assert 20 in scrubbing.flagged_volumes
        assert 21 in scrubbing.flagged_volumes
        assert 10 in scrubbing.fd_flagged
        assert 20 in scrubbing.fd_flagged

    def test_scrubbing_with_high_dvars_volumes(self, good_run_result):
        """Test scrubbing flags high DVARS volumes."""
        # Add some high DVARS volumes
        good_run_result.series['dvars_std'][15] = 4.0
        good_run_result.series['dvars_std'][25] = 3.5

        scrubbing = compute_volume_scrubbing(
            good_run_result,
            fd_threshold=0.5,
            dvars_threshold=2.5
        )

        assert 15 in scrubbing.flagged_volumes
        assert 25 in scrubbing.flagged_volumes
        assert 15 in scrubbing.dvars_flagged
        assert 25 in scrubbing.dvars_flagged

    def test_scrubbing_calculates_data_loss(self, good_run_result):
        """Test data loss calculation."""
        # Flag 10 volumes out of 100
        good_run_result.series['fd'][5:15] = 1.0

        scrubbing = compute_volume_scrubbing(
            good_run_result,
            fd_threshold=0.5
        )

        # Should be ~10-20% (10 flagged + some spin history volumes)
        assert 10.0 <= scrubbing.data_loss_percent <= 25.0

    def test_scrubbing_no_series_data(self):
        """Test scrubbing when no series data available."""
        info = RunInfo(
            path=Path("/data/test.nii.gz"),
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        result = RunResult(
            info=info,
            metrics={'n_volumes': 100},
            flags={},
            series={},  # No FD/DVARS series
            maps={},
            mask=np.ones((10, 10, 10), dtype=bool),
            affine=np.eye(4),
            header=None,
            figure_path=Path("/tmp/fig.png"),
            carpetplot_path=None,
            thumbnail_path=None,
            mean_vector=np.ones(100),
        )

        scrubbing = compute_volume_scrubbing(result)

        assert scrubbing.n_volumes == 100
        assert len(scrubbing.flagged_volumes) == 0
        assert scrubbing.data_loss_percent == 0.0

    def test_scrubbing_to_dict(self, good_run_result):
        """Test converting scrubbing to dictionary."""
        scrubbing = compute_volume_scrubbing(good_run_result)
        data = scrubbing.to_dict()

        assert 'run_id' in data
        assert 'n_volumes' in data
        assert 'flagged_volumes' in data
        assert 'fd_flagged' in data
        assert 'dvars_flagged' in data
        assert 'data_loss_percent' in data


# ============================================================================
# Exclusion Report Tests
# ============================================================================


class TestGenerateExclusionReport:
    """Test exclusion report generation."""

    def test_report_structure(self, good_run_result, bad_run_result):
        """Test report has correct structure."""
        results = [good_run_result, bad_run_result]

        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        assert report.stringency == "moderate"
        assert 'criteria' in report.to_dict()
        assert len(report.run_exclusions) == 2
        assert len(report.volume_scrubbing) == 2
        assert 'summary' in report.to_dict()

    def test_report_with_liberal_stringency(self, good_run_result, bad_run_result):
        """Test report with liberal stringency."""
        results = [good_run_result, bad_run_result]

        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.LIBERAL,
        )

        assert report.stringency == "liberal"
        # Liberal should exclude fewer runs
        excluded_count = sum(1 for e in report.run_exclusions if e.excluded)
        assert excluded_count <= len(results)

    def test_report_with_conservative_stringency(self, good_run_result, bad_run_result):
        """Test report with conservative stringency."""
        results = [good_run_result, bad_run_result]

        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.CONSERVATIVE,
        )

        assert report.stringency == "conservative"
        # Conservative should exclude more runs
        excluded_count = sum(1 for e in report.run_exclusions if e.excluded)
        assert excluded_count >= 0

    def test_report_with_custom_criteria(self, good_run_result):
        """Test report with custom criteria."""
        results = [good_run_result]

        custom_criteria = ExclusionCriteria(
            fd_median_max=0.1,  # Very strict
            tsnr_min=100.0,  # Very high
        )

        report = generate_exclusion_report(
            results,
            custom_criteria=custom_criteria,
        )

        # Good run should fail strict criteria
        assert report.run_exclusions[0].excluded

    def test_report_summary(self, good_run_result, bad_run_result):
        """Test report summary statistics."""
        results = [good_run_result, bad_run_result]

        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        summary = report.summary

        assert summary['total_runs'] == 2
        assert 'excluded_runs' in summary
        assert 'retained_runs' in summary
        assert 'exclusion_rate_percent' in summary
        assert summary['total_runs'] == summary['excluded_runs'] + summary['retained_runs']

    def test_report_with_mahalanobis_distances(self, good_run_result, bad_run_result):
        """Test report with Mahalanobis distances."""
        results = [good_run_result, bad_run_result]

        mahalanobis_distances = {
            good_run_result.info.get_identifier(): 2.5,
            bad_run_result.info.get_identifier(): 8.0,
        }

        custom_criteria = ExclusionCriteria(
            mahalanobis_max=5.0,
        )

        report = generate_exclusion_report(
            results,
            custom_criteria=custom_criteria,
            mahalanobis_distances=mahalanobis_distances,
        )

        # Bad run should be excluded due to high Mahalanobis distance
        bad_exclusion = [e for e in report.run_exclusions if e.run == 'bad'][0]
        assert bad_exclusion.excluded


# ============================================================================
# Export Tests
# ============================================================================


class TestExportExclusionList:
    """Test exclusion list export."""

    def test_export_tsv(self, tmp_path, bad_run_result):
        """Test exporting exclusion list as TSV."""
        results = [bad_run_result]
        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        output_path = tmp_path / "exclusions.tsv"
        export_exclusion_list(report, output_path, format="tsv")

        assert output_path.exists()
        content = output_path.read_text()
        assert 'subject' in content
        assert 'session' in content
        assert 'run' in content

    def test_export_json(self, tmp_path, bad_run_result):
        """Test exporting exclusion list as JSON."""
        results = [bad_run_result]
        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        output_path = tmp_path / "exclusions.json"
        export_exclusion_list(report, output_path, format="json")

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert 'excluded_runs' in data
        assert 'summary' in data

    def test_export_txt(self, tmp_path, bad_run_result):
        """Test exporting exclusion list as TXT."""
        results = [bad_run_result]
        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        output_path = tmp_path / "exclusions.txt"
        export_exclusion_list(report, output_path, format="txt")

        assert output_path.exists()
        content = output_path.read_text()
        # Should contain run IDs
        assert len(content) > 0


class TestExportCensorFiles:
    """Test censor file export."""

    def test_export_fsl_format(self, tmp_path, good_run_result):
        """Test exporting censor files in FSL format."""
        # Add some flagged volumes
        good_run_result.series['fd'][10] = 1.0
        good_run_result.series['fd'][20] = 0.8

        results = [good_run_result]
        report = generate_exclusion_report(results)

        paths = export_censor_files(report, tmp_path, format="fsl")

        run_id = good_run_result.info.get_identifier()
        assert run_id in paths
        assert paths[run_id].exists()

        # Load censor file
        censor = np.loadtxt(paths[run_id], dtype=int)
        assert len(censor) == 100
        assert censor[10] == 0  # Flagged volume
        assert censor[0] == 1  # Good volume

    def test_export_afni_format(self, tmp_path, good_run_result):
        """Test exporting censor files in AFNI format."""
        good_run_result.series['fd'][10] = 1.0

        results = [good_run_result]
        report = generate_exclusion_report(results)

        paths = export_censor_files(report, tmp_path, format="afni")

        run_id = good_run_result.info.get_identifier()
        assert run_id in paths

        # Load censor file
        censor = np.loadtxt(paths[run_id], dtype=int)
        # AFNI: 0 = keep, 1 = censor
        assert censor[10] == 1  # Flagged volume
        assert censor[0] == 0  # Good volume


# ============================================================================
# Methods Text Tests
# ============================================================================


class TestGenerateMethodsText:
    """Test methods text generation."""

    def test_methods_text_structure(self, good_run_result, bad_run_result):
        """Test methods text has correct structure."""
        results = [good_run_result, bad_run_result]
        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        text = generate_methods_text(report)

        assert 'moderate' in text
        assert 'criteria' in text.lower()
        assert 'manual review' in text.lower()

    def test_methods_text_includes_criteria(self, good_run_result):
        """Test methods text includes criteria descriptions."""
        custom_criteria = ExclusionCriteria(
            fd_median_max=0.5,
            tsnr_min=30.0,
        )

        results = [good_run_result]
        report = generate_exclusion_report(
            results,
            custom_criteria=custom_criteria,
        )

        text = generate_methods_text(report)

        assert '0.5' in text  # FD threshold
        assert '30' in text  # tSNR threshold

    def test_methods_text_includes_summary(self, good_run_result, bad_run_result):
        """Test methods text includes summary statistics."""
        results = [good_run_result, bad_run_result]
        report = generate_exclusion_report(
            results,
            stringency=ExclusionStringency.MODERATE,
        )

        text = generate_methods_text(report)

        assert str(len(results)) in text  # Total runs
        assert 'volumes' in text.lower()
