"""Command-line interface parser for fmriqa.

This module provides argument parsing and validation for the fMRI quality
assessment pipeline. It handles configuration loading from YAML files and
command-line argument overrides.
"""

import argparse
from pathlib import Path
from typing import Optional

from .config import QAConfig
from fmriqa.core.constants import QualityThresholds, StatisticalConstants


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured argument parser with all CLI options
    """
    parser = argparse.ArgumentParser(
        description="fMRI Quality Assurance Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run QA on finalinterp data with config file
  fmriqa --config qa_config.yaml --derivatives-dir /path/to/derivatives

  # Run QA using a manifest file
  fmriqa --manifest my_runs.yaml

  # Regenerate reports from existing QA directory
  fmriqa --reports-only /path/to/existing/QA/20240101_120000

  # Run QA on tedana data with custom thresholds
  fmriqa --derivatives-dir /path/to/derivatives --data-source tedana \\
         --fd-threshold 0.5 --dvars-z-threshold 3.5
        """
    )

    # Input source options
    input_group = parser.add_argument_group('Input Options')
    input_group.add_argument(
        "--derivatives-dir",
        type=Path,
        help="Derivatives directory containing preprocessed data"
    )
    input_group.add_argument(
        "--bids-root",
        type=Path,
        help="BIDS root directory (optional, used for finding anatomical references)"
    )
    input_group.add_argument(
        "--config",
        type=Path,
        help="Configuration YAML file (see docs for format)"
    )
    input_group.add_argument(
        "--manifest",
        type=Path,
        metavar="FILE",
        help="Path to manifest file (YAML/JSON) for non-BIDS datasets"
    )

    # Data source configuration
    source_group = parser.add_argument_group('Data Source Configuration')
    source_group.add_argument(
        "--data-source",
        type=str,
        default=None,
        choices=["finalinterp", "tedana", "glmsingle", "manifest"],
        help="Data source preset (default: auto-detect from config, or finalinterp if no config)"
    )
    source_group.add_argument(
        "--glmsingle-input-source",
        type=str,
        default="finalinterp",
        choices=["finalinterp", "tedana"],
        help="For glmsingle: which preprocessing was used (default: finalinterp)"
    )
    source_group.add_argument(
        "--glob-pattern",
        type=str,
        default="",
        help="Custom glob pattern (overrides data-source preset)"
    )

    # Output configuration
    output_group = parser.add_argument_group('Output Configuration')
    output_group.add_argument(
        "--output-dir-name",
        type=str,
        default="QA",
        help="Name of output directory (default: QA)"
    )
    output_group.add_argument(
        "--no-hierarchical",
        action="store_true",
        help="Disable hierarchical reports (generate single flat report)"
    )
    output_group.add_argument(
        "--no-carpetplots",
        action="store_true",
        help="Disable carpetplot generation (saves time/space)"
    )

    # Processing options
    processing_group = parser.add_argument_group('Processing Options')
    processing_group.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Number of parallel jobs (default: 1)"
    )
    processing_group.add_argument(
        "--target-echo",
        type=int,
        default=2,
        help="Target echo number for multi-echo data (default: 2)"
    )
    processing_group.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable incremental caching"
    )
    processing_group.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Force reprocessing of all runs (ignore cache)"
    )

    # Quality thresholds
    threshold_group = parser.add_argument_group('Quality Thresholds')
    threshold_group.add_argument(
        "--dvars-z-threshold",
        type=float,
        default=StatisticalConstants.Z_SCORE_STRICT,
        help=f"Z-score threshold for DVARS outliers (default: {StatisticalConstants.Z_SCORE_STRICT})"
    )
    threshold_group.add_argument(
        "--fd-threshold",
        type=float,
        default=QualityThresholds.FD_THRESHOLD_STRICT,
        help=f"Framewise displacement threshold in mm (default: {QualityThresholds.FD_THRESHOLD_STRICT})"
    )
    threshold_group.add_argument(
        "--fd-median-threshold",
        type=float,
        default=0.2,
        help="Median FD threshold for run exclusion (default: 0.2 mm)"
    )
    threshold_group.add_argument(
        "--outlier-threshold",
        type=float,
        default=0.02,
        help="Proportion of outlier timepoints for flagging (default: 0.02)"
    )
    threshold_group.add_argument(
        "--tsnr-drop-threshold",
        type=float,
        default=0.25,
        help="tSNR dropout threshold (default: 0.25)"
    )
    threshold_group.add_argument(
        "--outlier-metric-threshold",
        type=float,
        default=3.0,
        help="Mahalanobis distance threshold for multivariate outlier detection (default: 3.0)"
    )

    # Exclusion configuration
    exclusion_group = parser.add_argument_group('Exclusion Recommendations')
    exclusion_group.add_argument(
        "--exclusion-stringency",
        type=str,
        default="moderate",
        choices=["liberal", "moderate", "conservative"],
        help="Stringency for exclusion recommendations (default: moderate)"
    )

    # Reuse/regenerate options
    reuse_group = parser.add_argument_group('Reuse Previous Results')
    reuse_group.add_argument(
        "--reuse-from",
        type=Path,
        help="Reuse cached QA results from a previous output directory"
    )
    reuse_group.add_argument(
        "--reports-only",
        type=Path,
        metavar="QA_DIR",
        help="Regenerate reports from existing QA directory without recomputing metrics"
    )

    # Utility options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print runs that would be processed without running QA"
    )

    return parser


def parse_and_validate_args(args: Optional[list] = None) -> QAConfig:
    """Parse and validate CLI arguments, returning a configuration object.

    This function creates an argument parser, parses the provided arguments
    (or sys.argv if not provided), and constructs a QAConfig object with
    the specified settings.

    Parameters
    ----------
    args : list, optional
        List of argument strings to parse. If None, uses sys.argv.

    Returns
    -------
    QAConfig
        Configuration object populated from CLI arguments and config file

    Examples
    --------
    >>> config = parse_and_validate_args(['--derivatives-dir', '/path/to/data'])
    >>> config = parse_and_validate_args()  # Uses sys.argv
    """
    parser = create_argument_parser()
    parsed_args = parser.parse_args(args)

    # Handle --reports-only as a shortcut for --reuse-from with same output dir
    if parsed_args.reports_only:
        parsed_args.reuse_from = parsed_args.reports_only

    # Handle manifest mode
    if parsed_args.manifest:
        parsed_args.data_source = "manifest"

    # Load or create config
    if parsed_args.config and Path(parsed_args.config).exists():
        config = QAConfig.from_yaml(Path(parsed_args.config))

        # Override config with command-line args if provided
        if parsed_args.derivatives_dir:
            config.derivatives_dir = Path(parsed_args.derivatives_dir)
        if parsed_args.bids_root:
            config.bids_root = Path(parsed_args.bids_root)
        if parsed_args.manifest:
            config.manifest_path = Path(parsed_args.manifest)
            config.data_source = "manifest"
        elif parsed_args.data_source is not None:
            # User explicitly provided --data-source, override config
            config.data_source = parsed_args.data_source
        if parsed_args.glob_pattern:
            config.glob_pattern = parsed_args.glob_pattern
        if parsed_args.output_dir_name != "QA":
            config.output_dir_name = parsed_args.output_dir_name
        if parsed_args.target_echo != 2:
            config.target_echo = parsed_args.target_echo
        if parsed_args.n_jobs != 1:
            config.n_jobs = parsed_args.n_jobs
        if parsed_args.dvars_z_threshold != StatisticalConstants.Z_SCORE_STRICT:
            config.dvars_z_threshold = parsed_args.dvars_z_threshold
        if parsed_args.fd_threshold != QualityThresholds.FD_THRESHOLD_STRICT:
            config.fd_threshold = parsed_args.fd_threshold
        if parsed_args.fd_median_threshold != 0.2:
            config.fd_median_threshold = parsed_args.fd_median_threshold
        if parsed_args.outlier_threshold != 0.02:
            config.outlier_threshold = parsed_args.outlier_threshold
        if parsed_args.tsnr_drop_threshold != 0.25:
            config.tsnr_drop_threshold = parsed_args.tsnr_drop_threshold
        if parsed_args.outlier_metric_threshold != 3.0:
            config.outlier_metric_threshold = parsed_args.outlier_metric_threshold
        if parsed_args.exclusion_stringency != "moderate":
            config.exclusion_stringency = parsed_args.exclusion_stringency
        if parsed_args.no_hierarchical:
            config.organize_hierarchical = False
        if parsed_args.no_carpetplots:
            config.generate_carpetplots = False
        if parsed_args.no_cache:
            config.use_cache = False
        if parsed_args.force_reprocess:
            config.force_reprocess = True
        if parsed_args.reuse_from:
            config.reuse_run_dir = Path(parsed_args.reuse_from)
        if parsed_args.reports_only:
            config.reports_only = Path(parsed_args.reports_only)
        if parsed_args.dry_run:
            config.dry_run = True
    else:
        # Create config from command-line args
        config = QAConfig(
            derivatives_dir=Path(parsed_args.derivatives_dir) if parsed_args.derivatives_dir else None,
            bids_root=Path(parsed_args.bids_root) if parsed_args.bids_root else None,
            manifest_path=Path(parsed_args.manifest) if parsed_args.manifest else None,
            data_source=parsed_args.data_source if parsed_args.data_source is not None else "finalinterp",
            glmsingle_input_source=parsed_args.glmsingle_input_source,
            glob_pattern=parsed_args.glob_pattern,
            output_dir_name=parsed_args.output_dir_name,
            target_echo=parsed_args.target_echo,
            n_jobs=parsed_args.n_jobs,
            dvars_z_threshold=parsed_args.dvars_z_threshold,
            fd_threshold=parsed_args.fd_threshold,
            fd_median_threshold=parsed_args.fd_median_threshold,
            outlier_threshold=parsed_args.outlier_threshold,
            tsnr_drop_threshold=parsed_args.tsnr_drop_threshold,
            outlier_metric_threshold=parsed_args.outlier_metric_threshold,
            exclusion_stringency=parsed_args.exclusion_stringency,
            organize_hierarchical=not parsed_args.no_hierarchical,
            generate_carpetplots=not parsed_args.no_carpetplots,
            use_cache=not parsed_args.no_cache,
            force_reprocess=parsed_args.force_reprocess,
            reuse_run_dir=Path(parsed_args.reuse_from) if parsed_args.reuse_from else None,
            reports_only=Path(parsed_args.reports_only) if parsed_args.reports_only else None,
            dry_run=parsed_args.dry_run,
        )

    return config
