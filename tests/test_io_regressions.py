"""Regression tests for serialization, masks, cache identity, and package data."""

import json
import os
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from fmriqc.io.io import (
    QACache,
    RunResultSerializer,
    ensure_mask_aligned,
    images_same_grid,
    load_all_results_from_previous_run,
)
from fmriqc.io.structures import InputRun, RunInfo, RunKey, RunResult, SnapshotInfo
from fmriqc.reporting.reporting import get_templates_dir


def _minimal_result() -> RunResult:
    return RunResult(
        info=RunInfo(path=Path("/tmp/sub-01_ses-01_task-rest_run-01_bold.nii.gz"), subject="01", session="01", task="rest", run="01"),
        metrics={"n_volumes": 3, "tr": 2.0},
        flags={},
        series={
            "fd": np.array([0.0, 0.1, 0.2]),
            "dvars_std": np.array([np.nan, 1.0, 1.2]),
            "fd_threshold": 0.3,
            "dvars_threshold": 2.5,
        },
        maps={},
        mask=np.ones((2, 2, 2), dtype=bool),
        affine=np.eye(4),
        header=nib.Nifti1Header(),
        figure_path=Path("/tmp/figure.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(3),
    )


def _input_run(bold: Path, mask: Path | None = None, motion: Path | None = None) -> InputRun:
    return InputRun(
        snapshot=SnapshotInfo(id="snap"),
        run_key=RunKey(subject="01", session="01", task="rest", run="01"),
        bold_path=bold,
        mask_path=mask,
        motion_path=motion,
    )


def test_series_json_contains_fd_tr_n_volumes_and_thresholds(tmp_path):
    result = _minimal_result()
    series_path = tmp_path / "series.json"

    RunResultSerializer()._save_series_json(result, series_path)

    data = json.loads(series_path.read_text())
    assert data["n_volumes"] == 3
    assert data["tr"] == 2.0
    assert data["fd_threshold"] == 0.3
    assert data["dvars_threshold"] == 2.5
    assert data["series"]["fd"] == [0.0, 0.1, 0.2]


def test_same_grid_mask_does_not_resample():
    data_img = nib.Nifti1Image(np.ones((3, 3, 3, 2)), np.eye(4))
    mask_img = nib.Nifti1Image(np.ones((3, 3, 3)), np.eye(4))

    aligned, resampled = ensure_mask_aligned(data_img, mask_img)

    assert images_same_grid(data_img, mask_img)
    assert aligned is mask_img
    assert resampled is False


def test_same_shape_different_affine_is_not_same_grid():
    data_img = nib.Nifti1Image(np.ones((3, 3, 3, 2)), np.eye(4))
    shifted = np.eye(4)
    shifted[0, 3] = 2.0
    mask_img = nib.Nifti1Image(np.ones((3, 3, 3)), shifted)

    assert not images_same_grid(data_img, mask_img)
    with pytest.raises(ValueError, match="grid/affine"):
        ensure_mask_aligned(data_img, mask_img, allow_resample=False)


def test_cache_key_changes_when_config_hash_changes(tmp_path):
    bold = tmp_path / "bold.nii.gz"
    bold.write_text("bold")
    input_run = _input_run(bold)

    key_a = QACache(tmp_path / "cache-a", config_hash="a", input_runs=[input_run]).get_cache_key(bold)
    key_b = QACache(tmp_path / "cache-b", config_hash="b", input_runs=[input_run]).get_cache_key(bold)

    assert key_a != key_b


def test_cache_key_changes_when_mask_mtime_changes(tmp_path):
    bold = tmp_path / "bold.nii.gz"
    mask = tmp_path / "mask.nii.gz"
    bold.write_text("bold")
    mask.write_text("mask")

    input_run = _input_run(bold, mask=mask)
    key_a = QACache(tmp_path / "cache-a", config_hash="same", input_runs=[input_run]).get_cache_key(bold)

    new_time = time.time() + 10
    os.utime(mask, (new_time, new_time))
    key_b = QACache(tmp_path / "cache-b", config_hash="same", input_runs=[input_run]).get_cache_key(bold)

    assert key_a != key_b


def test_load_all_results_from_previous_run_uses_stored_metadata_not_recomputed_key(tmp_path):
    previous = tmp_path / "previous"
    new_output = tmp_path / "new"
    result = _minimal_result()
    bold = tmp_path / "sub-01_ses-01_task-rest_run-01_bold.nii.gz"
    bold.write_text("bold")
    result.info.path = bold
    RunResultSerializer().serialize_to_disk(result, previous)
    metadata = result.to_cache()

    (previous / "qa_cache.json").write_text(
        json.dumps({"key-from-original-run": metadata}),
        encoding="utf-8",
    )

    loaded = load_all_results_from_previous_run(previous, new_output)

    assert len(loaded) == 1
    assert loaded[0].info.path == bold
    assert (new_output / "sub-01" / "ses-01").exists()


def test_active_reporting_templates_are_packaged():
    templates = get_templates_dir()

    assert (templates / "study_report.html").exists()
    assert (templates / "subject_report.html").exists()
