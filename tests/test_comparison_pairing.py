"""Tests for snapshot comparison pairing."""

from pathlib import Path

import numpy as np

from fmriqc.comparison.pairing import pair_results
from fmriqc.io.structures import RunInfo, RunKey, RunResult, SnapshotInfo


def _result(subject: str = "01", run: str = "01", snapshot_id: str = "left") -> RunResult:
    run_key = RunKey(subject=subject, session="01", task="rest", run=run)
    return RunResult(
        info=RunInfo(path=Path(f"/tmp/{snapshot_id}_{subject}_{run}.nii.gz"), subject=subject, session="01", task="rest", run=run),
        metrics={},
        flags={},
        series={},
        maps={},
        mask=np.ones((2, 2, 2), dtype=bool),
        affine=np.eye(4),
        header=None,
        figure_path=Path("/tmp/figure.png"),
        carpetplot_path=None,
        thumbnail_path=None,
        mean_vector=np.ones(2),
        snapshot=SnapshotInfo(id=snapshot_id),
        run_key=run_key,
    )


def test_pair_results_by_run_key():
    left = [_result(snapshot_id="raw")]
    right = [_result(snapshot_id="preproc")]

    report = pair_results(left, right)

    assert len(report.paired) == 1
    assert report.paired[0].run_key.to_string() == "sub-01_ses-01_task-rest_run-01"
    assert report.left_only == []
    assert report.right_only == []


def test_left_only_and_right_only_reported():
    report = pair_results([_result(subject="01")], [_result(subject="02")])

    assert len(report.paired) == 0
    assert [key.subject for key in report.left_only] == ["01"]
    assert [key.subject for key in report.right_only] == ["02"]


def test_duplicate_keys_not_silently_paired():
    duplicate_left = [_result(snapshot_id="raw-a"), _result(snapshot_id="raw-b")]
    right = [_result(snapshot_id="preproc")]

    report = pair_results(duplicate_left, right)

    assert len(report.paired) == 0
    assert "sub-01_ses-01_task-rest_run-01" in report.duplicates_left
    assert report.warnings
