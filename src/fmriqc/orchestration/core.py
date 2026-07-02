"""Core QA pipeline orchestration.

This module provides the main entry point for fMRI quality assessment.
It coordinates run discovery, processing, aggregation, and reporting by
delegating to specialized modules for each phase of the pipeline.
"""

import csv
import json
from pathlib import Path

from fmriqc.comparison.io import load_snapshot_results
from fmriqc.comparison.metrics import compare_pair
from fmriqc.comparison.pairing import pair_results
from fmriqc.comparison.reporting import generate_comparison_report
from fmriqc.io.exports import export_provenance, export_run_flags, export_run_metrics
from fmriqc.io.io import load_all_results_from_previous_run

from .aggregation import assign_aggregate_paths, generate_hierarchical_reports
from .cli_parser import parse_cli
from .config import QAConfig
from .discovery import discover_input_runs
from .group_analysis import (
    detect_outliers_for_study,
    generate_exclusions_for_study,
    generate_group_plots,
)
from .orchestration import (
    build_analysis_metadata,
    compute_overall_metrics,
    organize_results,
    process_runs,
    setup_output_and_cache,
)


def run_qa(config: QAConfig) -> int:
    return run_assess(config)


def run_assess(config: QAConfig) -> int:
    """Run comprehensive QA pipeline on fMRI data.

    This is the main entry point that orchestrates the entire QA process:
    1. Discover runs to process (from BIDS or manifest)
    2. Setup output-local cache metadata
    3. Process all runs (compute metrics, generate visualizations)
    4. Organize results into study structure
    5. Compute aggregate maps and statistics
    6. Detect outliers and optional candidate review recommendations
    7. Generate HTML reports

    Parameters
    ----------
    config : QAConfig
        Configuration object with all settings

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    # Handle reuse mode: load results from previous run
    if config.reuse_run_dir:
        output_dir = config.reuse_run_dir.resolve()
        if not output_dir.exists():
            raise SystemExit(f"Reuse directory {output_dir} does not exist")

        print(f"Loading results from previous QA run: {output_dir}")

        # Load all results from previous run
        try:
            results = load_all_results_from_previous_run(output_dir, output_dir)
            print(f"Loaded {len(results)} results from previous QA run")
        except Exception as e:
            raise SystemExit(f"Failed to load results from previous run: {e}") from e

        if not results:
            raise SystemExit("No results found in previous QA run directory")

        # Skip processing and go straight to report generation
        cached_results_used = len(results)
        run_paths = [r.info.path for r in results]  # For summary purposes
    else:
        # Standard mode: discover and process runs
        input_runs, base_output = discover_input_runs(config)
        run_paths = [run.bold_path for run in input_runs]
        manifest_contexts = {}

        if config.dry_run:
            for input_run in input_runs:
                print(f"{input_run.get_identifier()}\t{input_run.bold_path}")
            return 0

        # Setup output directory and cache
        (
            output_dir,
            cache,
            runs_to_process,
            results_by_path,
            cached_results_used,
        ) = setup_output_and_cache(config, base_output, input_runs)

        # Process runs
        results = process_runs(
            runs_to_process,
            manifest_contexts,
            config,
            output_dir,
            input_runs,
            results_by_path,
        )

    if not results:
        print("ERROR: No runs were successfully processed")
        return 1

    # Update cache (only if not loading from previous run)
    if not config.reuse_run_dir and cache:
        # Rebuild results_by_path for cache update.
        results_by_path = {r.info.path: r for r in results}
        for path in run_paths:
            if path in results_by_path:
                cache.set(path, results_by_path[path])
        cache.save()

    # Build analysis metadata for provenance
    analysis_metadata = build_analysis_metadata(config, run_paths)

    # Organize results hierarchically
    study = organize_results(results, analysis_metadata=analysis_metadata)

    # Compute overall metrics
    study.overall_metrics = compute_overall_metrics(results)

    # Export tabular outputs before reports so HTML and comparison can reference them
    export_run_metrics(results, output_dir)
    export_run_flags(results, output_dir)
    export_provenance(results, output_dir)

    # Outlier detection
    outlier_report = {}
    if config.analysis.detect_outliers:
        outlier_report = detect_outliers_for_study(results, config, output_dir, study)
    else:
        study.overall_outliers = []
        study.outlier_report = {"disabled": True}

    # Generate candidate review recommendations
    if config.analysis.generate_exclusions:
        generate_exclusions_for_study(results, config, outlier_report, output_dir, study)
    else:
        study.exclusion_report = None

    # Aggregate maps
    assign_aggregate_paths(results, output_dir, study)

    # Generate group comparison plots
    if config.reporting.generate_group_plots:
        study.group_plots = generate_group_plots(study, output_dir)
    else:
        study.group_plots = {}

    # Generate snapshot reports
    generate_hierarchical_reports(study, output_dir, study.aggregate_figure_path)

    # Processing summary
    study.processing_summary = {
        "total_runs_found": len(run_paths),
        "runs_processed": len(results),
        "runs_failed": len(run_paths) - len(results),
        "cached_results_used": cached_results_used,
        "outliers_detected": len(study.overall_outliers),
        "total_warnings": sum(len(r.warnings) for r in results),
    }

    # Save study summary
    with open(output_dir / "study_summary.json", "w") as f:
        json.dump(
            {
                "overall_metrics": study.overall_metrics,
                "processing_summary": study.processing_summary,
                "outliers": study.overall_outliers,
            },
            f,
            indent=2,
        )

    # Print summary
    print(f"\n{'='*60}")
    print("QA Complete!")
    print(f"{'='*60}")
    print(f"Report: {output_dir / 'index.html'}")
    print(f"Output directory: {output_dir}")
    print("\nSummary:")
    print(f"  - {len(results)} runs processed")
    print(
        f"  - {len(study.overall_outliers)} outliers detected ({len(study.overall_outliers)/len(results)*100:.1f}%)"
    )
    print(f"  - Median tSNR: {study.overall_metrics['tsnr_median']:.2f}")
    median_fd = study.overall_metrics.get("fd_median")
    if median_fd is None:
        print("  - Median FD: unavailable (motion parameters not found)")
    else:
        print(f"  - Median FD: {median_fd:.3f} mm")

    if study.overall_outliers:
        print("\nOutlier runs:")
        for outlier in study.overall_outliers[:5]:
            print(f"  - {outlier}")
        if len(study.overall_outliers) > 5:
            print(f"  ... and {len(study.overall_outliers) - 5} more")

    return 0


def _write_pairing_report(pairing, output_dir: Path) -> None:
    payload = {
        "paired": [pair.run_key.to_string() for pair in pairing.paired],
        "left_only": [key.to_string() for key in pairing.left_only],
        "right_only": [key.to_string() for key in pairing.right_only],
        "duplicates_left": list(pairing.duplicates_left.keys()),
        "duplicates_right": list(pairing.duplicates_right.keys()),
        "warnings": pairing.warnings,
    }
    (output_dir / "pairing_report.json").write_text(json.dumps(payload, indent=2))


def _write_comparison_summary(comparisons, output_dir: Path) -> None:
    columns = [
        "run_id",
        "left_snapshot",
        "right_snapshot",
        "status",
        "left_tsnr_median",
        "right_tsnr_median",
        "delta_tsnr_median",
        "left_fd_median",
        "right_fd_median",
        "delta_fd_median",
        "left_dvars_std_median",
        "right_dvars_std_median",
        "delta_dvars_std_median",
        "left_coverage_signal_fraction",
        "right_coverage_signal_fraction",
        "delta_coverage_signal_fraction",
        "warnings",
    ]
    with (output_dir / "comparison_summary.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for comparison in comparisons:
            row = {
                "run_id": comparison.run_key.to_string(),
                "left_snapshot": comparison.left_snapshot_id,
                "right_snapshot": comparison.right_snapshot_id,
                "status": comparison.status,
                "warnings": "; ".join(comparison.warnings),
            }
            for metric in ["tsnr_median", "fd_median", "dvars_std_median", "coverage_signal_fraction"]:
                delta = comparison.metric_deltas.get(metric)
                if delta:
                    row[f"left_{metric}"] = delta.left
                    row[f"right_{metric}"] = delta.right
                    row[f"delta_{metric}"] = delta.delta
            writer.writerow(row)


def run_compare(args) -> int:
    """Compare two existing snapshot QA outputs."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    left_snapshot, left_results = load_snapshot_results(args.left_qa_dir)
    right_snapshot, right_results = load_snapshot_results(args.right_qa_dir)
    pairing = pair_results(left_results, right_results)
    comparisons = [compare_pair(pair) for pair in pairing.paired]

    (output_dir / "comparison.json").write_text(
        json.dumps([comparison.to_dict() for comparison in comparisons], indent=2)
    )
    run_dir_root = output_dir / "run_comparisons"
    for comparison in comparisons:
        run_dir = run_dir_root / comparison.run_key.to_string()
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "comparison.json").write_text(json.dumps(comparison.to_dict(), indent=2))
        (run_dir / "series_comparison.json").write_text(json.dumps(comparison.series, indent=2))

    _write_pairing_report(pairing, output_dir)
    _write_comparison_summary(comparisons, output_dir)
    report_path = generate_comparison_report(
        left_snapshot, right_snapshot, pairing, comparisons, output_dir
    )
    print(f"Comparison complete: {report_path}")
    return 0


def run_report(args) -> int:
    """Regenerate reports for an existing QA directory."""
    output_dir = Path(args.qa_dir)
    results = load_all_results_from_previous_run(output_dir, output_dir)
    if not results:
        raise SystemExit("No cached results found for report regeneration")
    analysis_metadata = {"snapshot": (results[0].snapshot.to_dict() if results[0].snapshot else {})}
    study = organize_results(results, analysis_metadata=analysis_metadata)
    study.overall_metrics = compute_overall_metrics(results)
    assign_aggregate_paths(results, output_dir, study)
    generate_hierarchical_reports(study, output_dir, study.aggregate_figure_path)
    print(f"Report regenerated: {output_dir / 'index.html'}")
    return 0


def main() -> int:
    """Command-line entry point for the fMRI QA pipeline.

    Parses command-line arguments, creates a configuration object,
    and runs the QA pipeline.

    Returns
    -------
    int
        Exit code (0 for success, 1 for error)
    """
    command, payload = parse_cli()
    if command == "assess":
        return run_assess(payload)
    if command == "compare":
        return run_compare(payload)
    if command == "report":
        return run_report(payload)
    raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
