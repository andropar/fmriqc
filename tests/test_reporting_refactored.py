"""Integration tests for refactored reporting module."""

import re
import tempfile
from pathlib import Path

from fmriqc.io.structures import (
    MaskInfo,
    MotionInfo,
    QAProvenance,
    RunInfo,
    RunKey,
    RunResult,
    SessionResults,
    SnapshotInfo,
    StudyResults,
    SubjectResults,
)
from fmriqc.reporting.reporting import (
    compute_metric_distributions,
    generate_study_report,
    generate_subject_report,
    prepare_study_data,
)


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
            "coverage_signal_fraction": 0.95,
            "gcor": 0.03,
            "dvars_median": 12.5,
            "dvars_percent_above": 2.0,
        },
        flags={
            "high_motion": False,
            "low_tsnr": False,
            "signal_coverage_low": False,
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
        assert "timeline-viz" in html_content
        assert "detail-modal" in html_content

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
        "versions": {"fmriqc": "0.1.0"},
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
        assert "Study Quality Report" in html_content
        assert "sub-01" in html_content
        assert "Median tSNR" in html_content
        assert "Median FD" in html_content

        # Check that template components work
        assert "summary-strip" in html_content

        # Check for JavaScript
        assert "<script>" in html_content

        print(f"✓ Study report generated successfully: {report_path}")


def test_missing_fd_stays_missing_in_study_report(tmp_path):
    """Missing motion should not be summarized as zero FD."""
    run = create_minimal_run_result("run-1")
    run.metrics["fd_median"] = None
    run.metrics["fd_percent_above"] = None
    run.metrics["motion_available"] = False
    run.motion_info = MotionInfo(source="missing")

    session = SessionResults(subject="01", session="1", runs=[run])
    subject = SubjectResults(subject="01", sessions=[session])
    study = StudyResults(subjects=[subject], overall_metrics={}, overall_outliers=[], group_plots={})

    distributions = compute_metric_distributions(study)
    study_data = prepare_study_data(study, tmp_path)

    assert "fd_median" not in distributions
    assert study_data["runs"][0]["metrics"]["fd_median"] is None

    report_path = generate_study_report(study=study, output_dir=tmp_path)
    html_content = report_path.read_text()

    assert re.search(
        r'<span class="value">\s*-\s*</span>\s*<span class="label">Median FD',
        html_content,
    )
    assert re.search(
        r"<td>\s*-\s*</td>\s*<td>2\.0</td>\s*<td>95\.0%</td>\s*<td>missing</td>",
        html_content,
    )


def test_prepare_outlier_data():
    """Test prepare_outlier_data helper function."""
    from fmriqc.reporting.reporting import prepare_outlier_data

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
    from fmriqc.analysis.exclusions import ExclusionReport, RunExclusion, VolumeScrubbing
    from fmriqc.reporting.reporting import prepare_exclusion_data

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
    from fmriqc.reporting.reporting import prepare_outlier_data

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
    from fmriqc.reporting.reporting import prepare_exclusion_data

    study = StudyResults(
        subjects=[],
        overall_metrics={},
        overall_outliers=[],
        group_plots={},
    )

    exclusion_data = prepare_exclusion_data(study)
    assert exclusion_data is None

    print("✓ prepare_exclusion_data correctly returns None for no report")


def test_study_report_contains_snapshot_id():
    run = create_minimal_run_result("run-1")
    study = StudyResults(
        subjects=[
            SubjectResults(
                subject="01",
                sessions=[
                    SessionResults(subject="01", session="1", runs=[run]),
                ],
            )
        ],
    )
    study.analysis_metadata = {
        "snapshot": {"id": "preproc", "label": "Preprocessed", "source_type": "preprocessed"},
        "thresholds": {"profile": "default"},
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        html = generate_study_report(study=study, output_dir=Path(tmpdir)).read_text()

    assert "Snapshot preproc" in html
    assert "Preprocessed" in html
    assert "Threshold profile: default" in html


def test_subject_report_contains_motion_and_mask_provenance():
    run = create_minimal_run_result("run-1")
    snapshot = SnapshotInfo(id="preproc")
    run_key = RunKey(subject="01", session="1", task="rest", run="run-1")
    mask_info = MaskInfo(path=Path("/data/mask.nii.gz"), source="manifest", resampled=True)
    motion_info = MotionInfo(path=Path("/data/confounds.tsv"), source="provided_confounds")
    run.snapshot = snapshot
    run.run_key = run_key
    run.mask_info = mask_info
    run.motion_info = motion_info
    run.provenance = QAProvenance(
        snapshot=snapshot,
        run_key=run_key,
        bold_path=run.info.path,
        mask_info=mask_info,
        motion_info=motion_info,
        config_hash="hash",
        software_version="test",
    )
    subject = SubjectResults(
        subject="01",
        sessions=[SessionResults(subject="01", session="1", runs=[run])],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        html = generate_subject_report(subject=subject, output_dir=Path(tmpdir)).read_text()

    assert "provided_confounds" in html
    assert "manifest" in html
    assert "confounds.tsv" in html


def test_subject_report_serializes_run_visual_assets():
    run = create_minimal_run_result("run-1")
    run.asset_paths = {
        "figure": Path("sub-01/ses-1/run-1/figure.png"),
        "carpetplot": Path("sub-01/ses-1/run-1/carpetplot.png"),
        "thumbnail": Path("sub-01/ses-1/run-1/thumb.png"),
        "spatial_map_tsnr": Path("sub-01/ses-1/run-1/map_tsnr.png"),
    }
    subject = SubjectResults(
        subject="01",
        sessions=[SessionResults(subject="01", session="1", runs=[run])],
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_root = Path(tmpdir)
        subject_dir = output_root / "sub-01"
        asset_dir = output_root / "sub-01" / "ses-1" / "run-1"
        asset_dir.mkdir(parents=True)
        for name in ["figure.png", "carpetplot.png", "thumb.png", "map_tsnr.png"]:
            (asset_dir / name).write_bytes(b"asset")

        html = generate_subject_report(subject=subject, output_dir=subject_dir).read_text()

    assert "run-visual-grid" in html
    assert "run-figure-image" in html
    assert "carpet-image" in html
    assert "flipbook-image" in html
    assert "ses-1/run-1/figure.png" in html
    assert "ses-1/run-1/carpetplot.png" in html
    assert "ses-1/run-1/map_tsnr.png" in html


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
