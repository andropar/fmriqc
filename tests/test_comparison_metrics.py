"""Tests for snapshot comparison metrics."""

from pathlib import Path

import numpy as np

from fmriqc.comparison.metrics import compare_pair, compare_series, dice, scalar_delta
from fmriqc.comparison.structures import RunPair
from fmriqc.io.structures import RunInfo, RunKey, RunResult, SnapshotInfo


def _result(
    metrics: dict | None = None,
    series: dict | None = None,
    mask: np.ndarray | None = None,
    affine: np.ndarray | None = None,
    snapshot_id: str = "snap",
) -> RunResult:
    run_key = RunKey(subject="01", session="01", task="rest", run="01")
    return RunResult(
        info=RunInfo(path=Path(f"/tmp/{snapshot_id}.nii.gz"), subject="01", session="01", task="rest", run="01"),
        metrics=metrics or {},
        flags={},
        series=series or {},
        maps={},
        mask=mask if mask is not None else np.ones((2, 2, 2), dtype=bool),
        affine=affine if affine is not None else np.eye(4),
        header=None,
        figure_path=Path("/tmp/figure.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(2),
        snapshot=SnapshotInfo(id=snapshot_id),
        run_key=run_key,
    )


def test_scalar_delta_percent_delta():
    delta = scalar_delta("tsnr_median", 10.0, 12.5)

    assert delta.left == 10.0
    assert delta.right == 12.5
    assert delta.delta == 2.5
    assert delta.percent_delta == 25.0


def test_series_comparison_handles_length_mismatch():
    left = _result(series={"fd": np.array([0.0, 0.1, 0.2])})
    right = _result(series={"fd": np.array([0.0, 0.1])})

    comparison = compare_series(left, right)

    assert comparison["fd"]["n_overlap"] == 2
    assert comparison["fd"]["length_match"] is False
    assert comparison["warnings"]


def test_mask_dice_same_grid():
    a = np.array([True, True, False, False])
    b = np.array([True, False, True, False])

    assert dice(a, b) == 0.5


def test_compare_pair_status_uses_directionality():
    left = _result(
        metrics={
            "tsnr_median": 20.0,
            "fd_median": 0.3,
            "coverage_signal_fraction": 0.8,
        },
        snapshot_id="raw",
    )
    right = _result(
        metrics={
            "tsnr_median": 30.0,
            "fd_median": 0.2,
            "coverage_signal_fraction": 0.9,
        },
        snapshot_id="preproc",
    )
    pair = RunPair(run_key=left.run_key, left=left, right=right)

    comparison = compare_pair(pair)

    assert comparison.status == "mostly_better"
    assert comparison.metric_deltas["tsnr_median"].delta == 10.0
    assert "mask_dice" in comparison.metric_deltas
