"""Integration tests for refactored reporting module."""

import json
from pathlib import Path
import tempfile
import pytest
from fmriqa.io.structures import StudyResults, SubjectResults, SessionResults, RunResult, RunInfo
from fmriqa.reporting.reporting import generate_subject_report, generate_study_report


def create_minimal_run_result(run_id: str) -> RunResult:
    """Create a minimal RunResult for testing."""
    import numpy as np
    return RunResult(
        info=RunInfo(
            path=Path(f"/fake/path/{run_id}.nii.gz"),
            subject="01",
            session="1",
            run=run_id,
            task="rest",
            echo=None,
            part=None,
            desc=None,
        ),
        metrics={
            "tsnr_median": 45.2,
            "fd_median": 0.15,
            "coverage": 0.95,
            "gcor": 0.03,
            "dvars_median": 12.5,
        },
        flags={
            "high_motion": False,
            "low_tsnr": False,
            "tsnr_drop": False,
            "slice_intensity": False,
        },
        series={},
        maps={},
        mask=np.array([]),
        affine=np.eye(4),
        header=None,
        figure_path=Path("/fake/figure.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.array([]),
    )


def test_generate_subject_report():
    """Test subject report generation with refactored templates."""
    # Create test data
    run1 = create_minimal_run_result("run-1")
    run2 = create_minimal_run_result("run-2")

    session = SessionResults(
        subject="01",
        session="1",
        runs=[run1, run2],
        aggregate_figure_path=None,
    )

    subject = SubjectResults(
        subject="01",
        sessions=[session],
        aggregate_figure_path=None,
    )

    # Generate report in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        session_consistency = {}

        report_path = generate_subject_report(
            subject=subject,
            output_dir=output_dir,
            session_consistency=session_consistency,
            alignment_report=None,
        )

        # Verify report was created
        assert report_path.exists()
        assert report_path.name == "subject_report.html"

        # Read and verify HTML content
        html_content = report_path.read_text()

        # Check for key elements from templates
        assert "sub-01" in html_content
        assert "ses-1" in html_content
        assert "run-1" in html_content
        assert "run-2" in html_content
        assert "tSNR" in html_content
        assert "FD" in html_content

        # Check that template components were included
        assert "thumbnail-view" in html_content or "detail-view" in html_content

        # Check for JavaScript
        assert "<script>" in html_content

        print(f"✓ Subject report generated successfully: {report_path}")


def test_generate_study_report():
    """Test study report generation with refactored templates."""
    # Create test data
    run1 = create_minimal_run_result("run-1")
    run2 = create_minimal_run_result("run-2")

    session = SessionResults(
        subject="01",
        session="1",
        runs=[run1, run2],
        aggregate_figure_path=None,
    )

    subject = SubjectResults(
        subject="01",
        sessions=[session],
        aggregate_figure_path=None,
    )

    study = StudyResults(
        subjects=[subject],
        overall_metrics={"tsnr_median": 45.0, "fd_median": 0.15},
        overall_outliers=[],
        group_plots={},
    )

    # Add analysis metadata
    study.analysis_metadata = {
        "timestamp": "2025-12-16 16:00:00",
        "data_source": "test",
        "total_runs": 2,
        "versions": {"fmriqa": "0.1.0"},
        "thresholds": {
            "fd_threshold": 0.5,
            "dvars_z_threshold": 3.0,
        },
    }

    # Generate report in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        report_path = generate_study_report(
            study=study,
            output_dir=output_dir,
            study_aggregate_path=None,
        )

        # Verify report was created
        assert report_path.exists()
        assert report_path.name == "index.html"

        # Read and verify HTML content
        html_content = report_path.read_text()

        # Check for key elements
        assert "fMRI Quality Assurance Report" in html_content
        assert "sub-01" in html_content
        assert "Median tSNR" in html_content
        assert "Median FD" in html_content

        # Check that template components work
        assert "summary-cards" in html_content

        # Check for JavaScript
        assert "<script>" in html_content

        print(f"✓ Study report generated successfully: {report_path}")


def test_prepare_outlier_data():
    """Test prepare_outlier_data helper function."""
    from fmriqa.reporting.reporting import prepare_outlier_data

    # Create study with outlier report
    study = StudyResults(
        subjects=[],
        overall_metrics={},
        overall_outliers=["sub-01_ses-1_run-1"],
        group_plots={},
    )

    study.outlier_report = {
        "multivariate_outliers": ["sub-01_ses-1_run-1"],
        "extreme_motion": ["sub-01_ses-1_run-2"],
        "low_tsnr": [],
        "tsnr_threshold": 30.0,
        "mahalanobis_distances": {"sub-01_ses-1_run-1": 4.5},
        "summary": {"multivariate_outliers": 1, "extreme_motion": 1},
        "warnings": [],
    }

    outlier_data = prepare_outlier_data(study)

    # Verify data structure
    assert outlier_data is not None
    assert "tsnr_threshold" in outlier_data
    assert outlier_data["tsnr_threshold"] == 30.0
    assert "outlier_explanations" in outlier_data
    assert "sub-01_ses-1_run-1" in outlier_data["outlier_explanations"]
    assert "sub-01_ses-1_run-2" in outlier_data["outlier_explanations"]

    print("✓ prepare_outlier_data works correctly")


def test_prepare_exclusion_data():
    """Test prepare_exclusion_data helper function."""
    from fmriqa.reporting.reporting import prepare_exclusion_data
    from fmriqa.analysis.exclusions import ExclusionReport, RunExclusion, VolumeScrubbing

    # Create study with exclusion report
    study = StudyResults(
        subjects=[],
        overall_metrics={},
        overall_outliers=[],
        group_plots={},
    )

    study.exclusion_report = ExclusionReport(
        summary={"excluded_runs": 1, "total_runs": 2},
        stringency="moderate",
        criteria={"fd_median": 0.5, "tsnr_min": 30.0},
        run_exclusions=[
            RunExclusion(
                run_id="sub-01_ses-1_run-1",
                subject="01",
                session="1",
                run="1",
                excluded=True,
                reasons=[],
            ),
        ],
        volume_scrubbing=[
            VolumeScrubbing(
                run_id="sub-01_ses-1_run-2",
                n_volumes=100,
                flagged_volumes=list(range(15)),
                fd_flagged=list(range(10)),
                dvars_flagged=list(range(5, 15)),
                data_loss_percent=15.0,
            ),
        ],
    )

    exclusion_data = prepare_exclusion_data(study)

    # Verify data structure
    assert exclusion_data is not None
    assert "summary" in exclusion_data
    assert "stringency" in exclusion_data
    assert exclusion_data["stringency"] == "moderate"
    assert "excluded_runs" in exclusion_data
    assert len(exclusion_data["excluded_runs"]) == 1
    assert "high_scrub_runs" in exclusion_data
    assert len(exclusion_data["high_scrub_runs"]) == 1
    assert exclusion_data["high_scrub_runs"][0].data_loss_percent == 15.0

    print("✓ prepare_exclusion_data works correctly")


def test_no_outliers_returns_none():
    """Test that prepare_outlier_data returns None when no outliers."""
    from fmriqa.reporting.reporting import prepare_outlier_data

    study = StudyResults(
        subjects=[],
        overall_metrics={},
        overall_outliers=[],
        group_plots={},
    )

    study.outlier_report = {
        "multivariate_outliers": [],
        "extreme_motion": [],
        "low_tsnr": [],
    }

    outlier_data = prepare_outlier_data(study)
    assert outlier_data is None

    print("✓ prepare_outlier_data correctly returns None for no outliers")


def test_no_exclusions_returns_none():
    """Test that prepare_exclusion_data returns None when no report."""
    from fmriqa.reporting.reporting import prepare_exclusion_data

    study = StudyResults(
        subjects=[],
        overall_metrics={},
        overall_outliers=[],
        group_plots={},
    )

    exclusion_data = prepare_exclusion_data(study)
    assert exclusion_data is None

    print("✓ prepare_exclusion_data correctly returns None for no report")


if __name__ == "__main__":
    # Run tests
    print("\n=== Testing Refactored Reporting Module ===\n")

    test_generate_subject_report()
    test_generate_study_report()
    test_prepare_outlier_data()
    test_prepare_exclusion_data()
    test_no_outliers_returns_none()
    test_no_exclusions_returns_none()

    print("\n=== All tests passed! ===\n")
