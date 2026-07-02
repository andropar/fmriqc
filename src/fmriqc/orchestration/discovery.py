"""Run discovery that resolves concrete InputRun objects."""

from __future__ import annotations

from pathlib import Path

from fmriqc.io.bids import parse_bids_entities, run_key_from_path
from fmriqc.io.io import (
    create_run_info,
    find_mask_path,
    load_default_derivatives,
    locate_motion_params,
)
from fmriqc.io.structures import InputRun
from fmriqc.orchestration.config import QAConfig


def _find_confounds(path: Path) -> Path | None:
    """Find a nearby fMRIPrep confounds TSV with matching BIDS entities."""
    candidates = sorted(path.parent.glob("*desc-confounds_timeseries.tsv"))
    if not candidates:
        candidates = sorted(path.parent.glob("*confounds*.tsv"))
    if not candidates:
        return None

    target_entities = parse_bids_entities(path)
    space_is_specific = target_entities.get("space") is not None and any(
        parse_bids_entities(candidate).get("space") is not None
        for candidate in candidates
    )
    required_entities = ["sub", "ses", "task", "run", "acq", "echo"]
    if space_is_specific:
        required_entities.append("space")

    matches = []
    for candidate in candidates:
        candidate_entities = parse_bids_entities(candidate)
        if all(
            candidate_entities.get(entity) == target_entities.get(entity)
            for entity in required_entities
            if target_entities.get(entity) is not None
        ) and all(
            target_entities.get(entity) == candidate_entities.get(entity)
            for entity in required_entities
            if candidate_entities.get(entity) is not None
        ):
            matches.append(candidate)

    return matches[0] if matches else None


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

        if manifest.snapshot is not None and config.snapshot == type(config.snapshot)():
            input_runs = manifest.to_input_runs()
        else:
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
