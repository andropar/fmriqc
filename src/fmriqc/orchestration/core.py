"""Core QA pipeline orchestration.

This module provides the main entry point for fMRI quality assessment.
It coordinates run discovery, processing, aggregation, and reporting by
delegating to specialized modules for each phase of the pipeline.
"""

import json
from pathlib import Path
from typing import List

from .aggregation import assign_aggregate_paths, generate_hierarchical_reports
from .cli_parser import parse_and_validate_args
from .config import QAConfig
from .group_analysis import (
    detect_outliers_for_study,
    generate_exclusions_for_study,
    generate_group_plots,
)
from fmriqc.io.io import QACache, load_all_results_from_previous_run
from .orchestration import (
    build_analysis_metadata,
    compute_overall_metrics,
    discover_runs,
    organize_results,
    process_runs,
    setup_output_and_cache,
)
from fmriqc.reporting import generate_study_report
from fmriqc.io.structures import RunResult


def run_qa(config: QAConfig) -> int:
    """Run comprehensive QA pipeline on fMRI data.

    This is the main entry point that orchestrates the entire QA process:
    1. Discover runs to process (from BIDS or manifest)
    2. Setup cache for incremental processing
    3. Process all runs (compute metrics, generate visualizations)
    4. Organize results into study structure
    5. Compute aggregate maps and statistics
    6. Detect outliers and generate exclusion recommendations
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

        # Friendly messaging for reports-only mode
        if config.reports_only:
            print(f"Reports-only mode: regenerating reports in {output_dir}")
        else:
            print(f"Loading results from previous QA run: {output_dir}")

        # Load all results from previous run
        try:
            results = load_all_results_from_previous_run(output_dir, output_dir)
            print(f"Loaded {len(results)} results from previous QA run")
        except Exception as e:
            raise SystemExit(f"Failed to load results from previous run: {e}")

        if not results:
            raise SystemExit("No results found in previous QA run directory")

        # Skip processing and go straight to report generation
        cached_results_used = len(results)
        run_paths = [r.info.path for r in results]  # For summary purposes
    else:
        # Standard mode: discover and process runs
        run_paths, manifest_contexts, base_output = discover_runs(config)

        if config.dry_run:
            for path in run_paths:
                print(path)
            return 0

        # Setup output directory and cache
        (
            output_dir,
            cache,
            runs_to_process,
            results_by_path,
            cached_results_used,
        ) = setup_output_and_cache(config, base_output, run_paths)

        # Process runs
        results = process_runs(
            runs_to_process,
            manifest_contexts,
            config,
            output_dir,
            run_paths,
            results_by_path,
        )

    if not results:
        print("ERROR: No runs were successfully processed")
        return 1

    # Update cache (only if not loading from previous run)
    if not config.reuse_run_dir:
        cache = QACache(output_dir, reuse_dir=None) if config.use_cache else None
        if cache:
            # Rebuild results_by_path for cache update
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

    # Outlier detection
    outlier_report = detect_outliers_for_study(results, config, output_dir, study)

    # Generate exclusion recommendations
    generate_exclusions_for_study(results, config, outlier_report, output_dir, study)

    # Aggregate maps
    assign_aggregate_paths(results, output_dir, study)

    # Generate group comparison plots
    study.group_plots = generate_group_plots(study, output_dir)

    # Generate hierarchical reports
    if config.organize_hierarchical:
        generate_hierarchical_reports(study, output_dir, study.aggregate_figure_path)
    else:
        # Generate single flat report (legacy)
        generate_study_report(study, output_dir, study.aggregate_figure_path)

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
    print(f"QA Complete!")
    print(f"{'='*60}")
    print(f"Report: {output_dir / 'index.html'}")
    print(f"Output directory: {output_dir}")
    print(f"\nSummary:")
    print(f"  - {len(results)} runs processed")
    print(
        f"  - {len(study.overall_outliers)} outliers detected ({len(study.overall_outliers)/len(results)*100:.1f}%)"
    )
    print(f"  - Median tSNR: {study.overall_metrics['tsnr_median']:.2f}")
    print(f"  - Median FD: {study.overall_metrics['fd_median']:.3f} mm")

    if study.overall_outliers:
        print(f"\nOutlier runs:")
        for outlier in study.overall_outliers[:5]:
            print(f"  - {outlier}")
        if len(study.overall_outliers) > 5:
            print(f"  ... and {len(study.overall_outliers) - 5} more")

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
    config = parse_and_validate_args()
    return run_qa(config)


if __name__ == "__main__":
    raise SystemExit(main())
