"""Tabular exports for snapshot QA outputs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from fmriqc.io.structures import RunResult

RUN_METRIC_COLUMNS = [
    "snapshot_id",
    "run_id",
    "subject",
    "session",
    "task",
    "run",
    "echo",
    "bold_path",
    "mask_source",
    "motion_source",
    "n_volumes",
    "tr",
    "tsnr_median",
    "fd_median",
    "fd_percent_above",
    "dvars_std_median",
    "dvars_percent_above",
    "outlier_percent_above",
    "coverage_signal_fraction",
    "apparent_smoothness_fwhm",
    "gcor",
    "ar1_median",
    "n_warnings",
    "n_flags",
]


def _write_tsv(path: Path, columns: list[str], rows: Iterable[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def export_run_metrics(results: list[RunResult], output_dir: Path) -> Path:
    """Export one row of scalar metrics per run."""
    rows = []
    for result in results:
        snapshot_id = result.snapshot.id if result.snapshot else result.info.snapshot_id
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "run_id": result.info.get_identifier(),
                "subject": result.info.subject,
                "session": result.info.session,
                "task": result.info.task or "",
                "run": result.info.run,
                "echo": result.info.echo or "",
                "bold_path": str(result.info.path),
                "mask_source": result.mask_info.source if result.mask_info else "",
                "motion_source": result.motion_info.source if result.motion_info else "",
                "n_warnings": len(result.warnings),
                "n_flags": sum(1 for value in result.flags.values() if value),
                **result.metrics,
            }
        )
    return _write_tsv(output_dir / "metrics" / "run_metrics.tsv", RUN_METRIC_COLUMNS, rows)


def export_run_flags(results: list[RunResult], output_dir: Path) -> Path:
    """Export boolean run flags."""
    flag_keys = sorted({key for result in results for key in result.flags})
    columns = ["snapshot_id", "run_id", "subject", "session", "task", "run"] + flag_keys
    rows = []
    for result in results:
        rows.append(
            {
                "snapshot_id": result.snapshot.id if result.snapshot else result.info.snapshot_id,
                "run_id": result.info.get_identifier(),
                "subject": result.info.subject,
                "session": result.info.session,
                "task": result.info.task or "",
                "run": result.info.run,
                **{key: int(bool(result.flags.get(key))) for key in flag_keys},
            }
        )
    return _write_tsv(output_dir / "metrics" / "run_flags.tsv", columns, rows)


def export_provenance(results: list[RunResult], output_dir: Path) -> Path:
    """Export per-run provenance."""
    columns = [
        "snapshot_id",
        "run_id",
        "bold_path",
        "mask_source",
        "mask_path",
        "mask_resampled",
        "motion_source",
        "motion_path",
        "motion_diagnostic_only",
        "warnings",
    ]
    rows = []
    for result in results:
        mask_info = result.mask_info
        motion_info = result.motion_info
        rows.append(
            {
                "snapshot_id": result.snapshot.id if result.snapshot else result.info.snapshot_id,
                "run_id": result.info.get_identifier(),
                "bold_path": str(result.info.path),
                "mask_source": mask_info.source if mask_info else "",
                "mask_path": str(mask_info.path) if mask_info and mask_info.path else "",
                "mask_resampled": int(bool(mask_info and mask_info.resampled)),
                "motion_source": motion_info.source if motion_info else "",
                "motion_path": str(motion_info.path) if motion_info and motion_info.path else "",
                "motion_diagnostic_only": int(bool(motion_info and motion_info.diagnostic_only)),
                "warnings": "; ".join(result.warnings),
            }
        )
    return _write_tsv(output_dir / "provenance" / "run_provenance.tsv", columns, rows)
