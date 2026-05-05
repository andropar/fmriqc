"""Run discovery that resolves concrete InputRun objects."""

from __future__ import annotations

from pathlib import Path

from fmriqc.io.bids import run_key_from_path
from fmriqc.io.io import (
    create_run_info,
    find_mask_path,
    load_default_derivatives,
    locate_motion_params,
)
from fmriqc.io.structures import InputRun
from fmriqc.orchestration.config import QAConfig


def _find_confounds(path: Path) -> Path | None:
    """Find a nearby fMRIPrep confounds TSV using BIDS entities when possible."""
    candidates = sorted(path.parent.glob("*desc-confounds_timeseries.tsv"))
    if not candidates:
        candidates = sorted(path.parent.glob("*confounds*.tsv"))
    if not candidates:
        return None

    stem_tokens = set(path.name.split("_"))
    best = None
    best_score = -1
    for candidate in candidates:
        score = len(stem_tokens.intersection(candidate.name.split("_")))
        if score > best_score:
            best = candidate
            best_score = score
    return best


def discover_input_runs(config: QAConfig) -> tuple[list[InputRun], Path]:
    """Discover all runs and return resolved InputRun objects plus output base."""
    snapshot = config.get_snapshot_info()

    if config.is_manifest_mode():
        manifest = config.get_manifest()
        if manifest is None:
            raise SystemExit(f"Could not load manifest from: {config.manifest_path}")

        errors = manifest.validate()
        if errors:
            print("Manifest validation errors:")
            for error in errors[:10]:
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
            raise SystemExit("Manifest validation failed")

        input_runs = manifest.to_input_runs(snapshot)
        if config.derivatives_dir:
            base_output = config.derivatives_dir
        elif manifest.base_path:
            base_output = manifest.base_path
        else:
            base_output = config.manifest_path.parent

        print(f"Data source: manifest ({config.manifest_path})")
        print(manifest.summary())
    else:
        if config.derivatives_dir is None:
            if config.config_file and config.config_file.exists():
                config.derivatives_dir = load_default_derivatives(config.config_file)
            if config.derivatives_dir is None:
                raise SystemExit("Unable to determine derivatives directory")

        config.derivatives_dir = config.derivatives_dir.resolve()
        base_output = config.derivatives_dir
        effective_pattern = config.get_effective_glob_pattern()
        print(f"Data source: {config.data_source}")
        print(f"Using pattern: {effective_pattern}")

        run_paths = sorted(config.derivatives_dir.glob(effective_pattern))
        input_runs = []
        for path in run_paths:
            run_key = run_key_from_path(path)
            info = create_run_info(path)
            input_runs.append(
                InputRun(
                    snapshot=snapshot,
                    run_key=run_key,
                    bold_path=path,
                    mask_path=find_mask_path(path, info),
                    motion_path=locate_motion_params(config.derivatives_dir, info, config.target_echo),
                    confounds_path=_find_confounds(path),
                )
            )

    if not input_runs:
        raise SystemExit("No valid runs found")

    print(f"Found {len(input_runs)} runs")
    return input_runs, base_output
