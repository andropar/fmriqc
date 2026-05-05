"""Group-level analysis and cross-subject visualizations.

This module handles outlier detection, candidate review flag generation,
and creation of group comparison plots across subjects.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from fmriqc.analysis.exclusions import (
    ExclusionStringency,
    export_censor_files,
    export_exclusion_list,
    generate_exclusion_report,
    generate_methods_text,
)
from fmriqc.analysis.outliers import generate_outlier_report
from fmriqc.io.structures import RunResult, StudyResults
from fmriqc.visualization.visualization import create_subject_comparison_plot

from .config import QAConfig


def detect_outliers_for_study(
    results: List[RunResult],
    config: QAConfig,
    output_dir: Path,
    study: StudyResults,
) -> Dict[str, Any]:
    """Detect outliers and save report.

    Runs outlier detection using Mahalanobis distance and updates the study
    object with outlier information.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    config : QAConfig
        Configuration object with thresholds
    output_dir : Path
        Output directory for report
    study : StudyResults
        Study results object to update

    Returns
    -------
    Dict[str, Any]
        Outlier report dictionary
    """
    print("Detecting outliers...")
    outlier_report = generate_outlier_report(
        results,
        mahalanobis_threshold=config.outlier_metric_threshold,
        min_runs=config.outlier_min_runs,
    )
    study.overall_outliers = outlier_report["multivariate_outliers"]
    study.outlier_report = outlier_report  # Store full report for detailed explanations

    # Save outlier report
    with open(output_dir / "outlier_report.json", "w") as f:
        json.dump(outlier_report, f, indent=2)

    return outlier_report


def generate_exclusions_for_study(
    results: List[RunResult],
    config: QAConfig,
    outlier_report: Dict[str, Any],
    output_dir: Path,
    study: StudyResults,
) -> None:
    """Generate candidate review recommendations and save reports.

    Creates review-support outputs based on QA metrics, exports candidate run
    flags, candidate censor vectors, and methods text.

    Parameters
    ----------
    results : List[RunResult]
        List of all run results
    config : QAConfig
        Configuration object with thresholds
    outlier_report : Dict[str, Any]
        Outlier report from detection
    output_dir : Path
        Output directory for reports
    study : StudyResults
        Study results object to update
    """
    print("Generating candidate review recommendations...")

    # Extract Mahalanobis distances from outlier report
    mahalanobis_distances = {}
    if "mahalanobis_distances" in outlier_report:
        mahalanobis_distances = outlier_report["mahalanobis_distances"]

    # Parse stringency from config
    stringency_map = {
        "liberal": ExclusionStringency.LIBERAL,
        "moderate": ExclusionStringency.MODERATE,
        "conservative": ExclusionStringency.CONSERVATIVE,
    }
    stringency = stringency_map.get(
        config.exclusion_stringency.lower(), ExclusionStringency.MODERATE
    )

    # Generate candidate review report
    exclusion_report = generate_exclusion_report(
        results,
        stringency=stringency,
        mahalanobis_distances=mahalanobis_distances,
        fd_threshold=config.fd_threshold,
        dvars_threshold=config.dvars_z_threshold,
    )
    study.exclusion_report = exclusion_report

    review_dir = output_dir / "reviews"
    review_dir.mkdir(exist_ok=True)

    with open(review_dir / "candidate_run_flags.json", "w") as f:
        json.dump(exclusion_report.to_dict(), f, indent=2)

    # Export candidate run flag list in TSV format
    export_exclusion_list(
        exclusion_report, review_dir / "candidate_run_flags.tsv", format="tsv"
    )

    # Export candidate censor vectors for volume-level review
    censor_dir = output_dir / "censor" / "candidate_censor_vectors"
    export_censor_files(exclusion_report, censor_dir, format="fsl")

    # Save methods text
    methods_text = generate_methods_text(exclusion_report)
    (review_dir / "methods_text.txt").write_text(methods_text)

    # Log candidate review summary
    summary = exclusion_report.summary
    print(
        f"  Candidate run flags: {summary['excluded_runs']}/{summary['total_runs']} runs "
        f"({summary['exclusion_rate_percent']:.1f}%)"
    )
    print(
        f"  Volume scrubbing: {summary['flagged_volumes']}/{summary['total_volumes']} volumes "
        f"({summary['volume_data_loss_percent']:.1f}%)"
    )


def generate_group_plots(
    study: StudyResults,
    output_dir: Path,
) -> Dict[str, Path]:
    """Generate group comparison plots.

    Creates violin plots comparing metrics across subjects for tSNR, FD,
    DVARS, and spatial smoothness.

    Parameters
    ----------
    study : StudyResults
        Study results object with subject data
    output_dir : Path
        Output directory

    Returns
    -------
    Dict[str, Path]
        Dictionary mapping plot names to file paths
    """
    print("Generating group comparison plots...")
    plots_dir = output_dir / "group_plots"
    plots_dir.mkdir(exist_ok=True)

    group_plots = {}

    # tSNR
    plot_path = create_subject_comparison_plot(
        study,
        "tsnr_median",
        plots_dir / "tsnr_comparison.png",
        "Temporal SNR Distribution by Subject",
        "tSNR (median)",
    )
    if plot_path:
        group_plots["tsnr"] = plot_path

    # FD
    plot_path = create_subject_comparison_plot(
        study,
        "fd_median",
        plots_dir / "fd_comparison.png",
        "Framewise Displacement Distribution by Subject",
        "FD (median, mm)",
    )
    if plot_path:
        group_plots["fd"] = plot_path

    # DVARS
    plot_path = create_subject_comparison_plot(
        study,
        "dvars_std_median",
        plots_dir / "dvars_comparison.png",
        "Standardized DVARS Distribution by Subject",
        "Standardized DVARS (median)",
    )
    if plot_path:
        group_plots["dvars"] = plot_path

    # Smoothness
    plot_path = create_subject_comparison_plot(
        study,
        "apparent_smoothness_fwhm",
        plots_dir / "smoothness_comparison.png",
        "Spatial Smoothness Distribution by Subject",
        "FWHM (mm)",
    )
    if plot_path:
        group_plots["smoothness"] = plot_path

    return group_plots
