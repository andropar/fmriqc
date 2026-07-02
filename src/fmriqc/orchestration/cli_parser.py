"""Command-line parsing for fmriqc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fmriqc.orchestration.config import (
    QAConfig,
    SnapshotConfig,
)


def _add_assess_args(parser: argparse.ArgumentParser) -> None:
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument("--derivatives-dir", type=Path)
    input_group.add_argument("--bids-root", type=Path)
    input_group.add_argument("--config", type=Path)
    input_group.add_argument("--manifest", type=Path, metavar="FILE")

    source_group = parser.add_argument_group("Data Source")
    source_group.add_argument(
        "--data-source",
        choices=["finalinterp", "tedana", "fmriprep", "manifest"],
        default=None,
    )
    source_group.add_argument("--glob-pattern", default=None)

    snapshot_group = parser.add_argument_group("Snapshot")
    snapshot_group.add_argument("--snapshot-id", default=None)
    snapshot_group.add_argument("--snapshot-label", default=None)
    snapshot_group.add_argument(
        "--snapshot-source-type",
        default=None,
        choices=["raw", "preprocessed", "denoised", "smoothed", "custom"],
    )

    output_group = parser.add_argument_group("Output")
    output_group.add_argument("-o", "--output-dir-name", default=None)
    output_group.add_argument("--no-carpetplots", action="store_true", default=None)

    processing_group = parser.add_argument_group("Processing")
    processing_group.add_argument("--n-jobs", type=int, default=None)
    processing_group.add_argument("--target-echo", type=int, default=None)
    processing_group.add_argument("--no-cache", action="store_true", default=None)
    processing_group.add_argument("--force-reprocess", action="store_true", default=None)
    processing_group.add_argument("--generate-motion", action="store_true", default=None)
    processing_group.add_argument(
        "--motion-strategy",
        choices=["prefer_provided", "generate_if_missing", "none"],
        default=None,
    )
    processing_group.add_argument("--fsl-container", type=Path)
    processing_group.add_argument(
        "--container-download",
        choices=["ask", "never", "auto"],
        default=None,
    )

    threshold_group = parser.add_argument_group("Quality Thresholds")
    threshold_group.add_argument(
        "--threshold-profile",
        choices=["lenient", "default", "strict"],
        default=None,
    )
    threshold_group.add_argument(
        "--dvars-z-threshold",
        type=float,
        default=None,
    )
    threshold_group.add_argument(
        "--fd-threshold",
        type=float,
        default=None,
    )
    threshold_group.add_argument("--fd-median-threshold", type=float, default=None)
    threshold_group.add_argument("--outlier-threshold", type=float, default=None)
    threshold_group.add_argument("--outlier-metric-threshold", type=float, default=None)

    analysis_group = parser.add_argument_group("Review Support")
    analysis_group.add_argument(
        "--generate-review-recommendations",
        action="store_true",
        default=None,
        help="Generate candidate run flags and candidate censor vectors",
    )
    analysis_group.add_argument(
        "--exclusion-stringency",
        default=None,
        choices=["liberal", "moderate", "conservative"],
    )
    analysis_group.add_argument("--disable-outliers", action="store_true", default=None)

    reuse_group = parser.add_argument_group("Reuse")
    reuse_group.add_argument("--reuse-from", type=Path)

    parser.add_argument("--dry-run", action="store_true", default=None)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="fMRI snapshot quality assessment and review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    assess = subparsers.add_parser("assess", help="Assess one fMRI data snapshot")
    _add_assess_args(assess)

    compare = subparsers.add_parser("compare", help="Compare two existing snapshot QA outputs")
    compare.add_argument("left_qa_dir", type=Path)
    compare.add_argument("right_qa_dir", type=Path)
    compare.add_argument("-o", "--output-dir", type=Path, required=True)
    compare.add_argument("--left-label", default="")
    compare.add_argument("--right-label", default="")
    compare.add_argument(
        "--spatial-compare-mode",
        choices=["side-by-side", "resample-left-to-right", "resample-right-to-left"],
        default="side-by-side",
    )

    report = subparsers.add_parser("report", help="Regenerate reports for an existing QA output")
    report.add_argument("qa_dir", type=Path)
    report.add_argument("--reviews", type=Path)

    return parser


def _snapshot_config_from_manifest(snapshot) -> SnapshotConfig:
    return SnapshotConfig(
        id=snapshot.id,
        label=snapshot.label,
        source_type=snapshot.source_type,
        description=snapshot.description,
        pipeline_name=snapshot.pipeline_name,
        pipeline_version=snapshot.pipeline_version,
    )


def _manifest_config_has_snapshot(manifest_config: dict | None) -> bool:
    return bool(manifest_config and isinstance(manifest_config.get("snapshot"), dict))


def _build_assess_config(parsed_args: argparse.Namespace) -> QAConfig:
    if parsed_args.manifest:
        parsed_args.data_source = "manifest"

    manifest_config = None
    manifest_config_data = None
    manifest = None
    if parsed_args.manifest and Path(parsed_args.manifest).exists():
        from fmriqc.io.manifest import QAManifest

        manifest = QAManifest.from_file(Path(parsed_args.manifest))
        if manifest.qa_config:
            manifest_config_data = dict(manifest.qa_config)
            manifest_config = QAConfig.from_dict(manifest_config_data)

    if parsed_args.config and Path(parsed_args.config).exists():
        config = QAConfig.from_yaml(Path(parsed_args.config))
        config.config_file = parsed_args.config
        if manifest and manifest.snapshot and config.snapshot == SnapshotConfig():
            config.snapshot = _snapshot_config_from_manifest(manifest.snapshot)
    elif manifest_config is not None:
        config = manifest_config
        if manifest and manifest.snapshot and not _manifest_config_has_snapshot(manifest_config_data):
            config.snapshot = _snapshot_config_from_manifest(manifest.snapshot)
    else:
        config = QAConfig()
        if manifest and manifest.snapshot:
            config.snapshot = _snapshot_config_from_manifest(manifest.snapshot)

    if manifest is not None:
        config.manifest = manifest

    if parsed_args.derivatives_dir is not None:
        config.derivatives_dir = parsed_args.derivatives_dir
    if parsed_args.bids_root is not None:
        config.bids_root = parsed_args.bids_root
    if parsed_args.manifest is not None:
        config.manifest_path = parsed_args.manifest
        config.data_source = "manifest"
        config.manifest = manifest
    elif parsed_args.data_source is not None:
        config.data_source = parsed_args.data_source
    if parsed_args.glob_pattern is not None:
        config.glob_pattern = parsed_args.glob_pattern
    if parsed_args.output_dir_name is not None:
        config.output_dir_name = parsed_args.output_dir_name

    if parsed_args.reuse_from is not None:
        config.reuse_run_dir = parsed_args.reuse_from

    if parsed_args.snapshot_id is not None:
        config.snapshot.id = parsed_args.snapshot_id
    if parsed_args.snapshot_label is not None:
        config.snapshot.label = parsed_args.snapshot_label
    if parsed_args.snapshot_source_type is not None:
        config.snapshot.source_type = parsed_args.snapshot_source_type

    if parsed_args.n_jobs is not None:
        config.n_jobs = parsed_args.n_jobs
    if parsed_args.target_echo is not None:
        config.target_echo = parsed_args.target_echo
    if parsed_args.no_cache:
        config.use_cache = False
    if parsed_args.force_reprocess:
        config.force_reprocess = True
    if parsed_args.dry_run:
        config.dry_run = True

    if parsed_args.generate_motion:
        config.generate_motion = True
    if parsed_args.motion_strategy is not None:
        config.motion.strategy = parsed_args.motion_strategy
    if parsed_args.fsl_container is not None:
        config.fsl_container_path = parsed_args.fsl_container
    if parsed_args.container_download is not None:
        config.motion.download_policy = parsed_args.container_download
    if parsed_args.no_carpetplots:
        config.generate_carpetplots = False

    if parsed_args.threshold_profile is not None:
        config.thresholds.profile = parsed_args.threshold_profile
    if parsed_args.dvars_z_threshold is not None:
        config.dvars_z_threshold = parsed_args.dvars_z_threshold
    if parsed_args.fd_threshold is not None:
        config.fd_threshold = parsed_args.fd_threshold
    if parsed_args.fd_median_threshold is not None:
        config.fd_median_threshold = parsed_args.fd_median_threshold
    if parsed_args.outlier_threshold is not None:
        config.outlier_threshold = parsed_args.outlier_threshold
    if parsed_args.outlier_metric_threshold is not None:
        config.outlier_metric_threshold = parsed_args.outlier_metric_threshold

    if parsed_args.disable_outliers:
        config.analysis.detect_outliers = False
    if parsed_args.generate_review_recommendations:
        config.analysis.generate_exclusions = True
    if parsed_args.exclusion_stringency is not None:
        config.exclusion_stringency = parsed_args.exclusion_stringency

    return config


def parse_cli(args: list | None = None) -> tuple[str, object]:
    """Parse CLI args, preserving no-subcommand assess compatibility."""
    parser = create_argument_parser()
    raw_args = list(args) if args is not None else sys.argv[1:]

    if raw_args and raw_args[0] not in {"assess", "compare", "report", "-h", "--help"}:
        assess_parser = argparse.ArgumentParser(description="Assess one fMRI data snapshot")
        _add_assess_args(assess_parser)
        parsed = assess_parser.parse_args(raw_args)
        return "assess", _build_assess_config(parsed)

    if not raw_args:
        raw_args = ["assess"]

    parsed = parser.parse_args(raw_args)
    command = parsed.command or "assess"
    if command == "assess":
        return command, _build_assess_config(parsed)
    return command, parsed


def parse_and_validate_args(args: list | None = None) -> QAConfig:
    """Backward-compatible parser that returns an assess config."""
    command, payload = parse_cli(args)
    if command != "assess":
        raise SystemExit(f"Expected assess command, got {command}")
    return payload  # type: ignore[return-value]
