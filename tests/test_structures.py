"""Tests for snapshot-first data structures."""

from pathlib import Path

from fmriqc.io.structures import RunKey, SnapshotInfo


def test_run_key_normalization_and_string():
    key = RunKey(subject="sub-01", session="ses-02", task="rest", run="run-01")

    assert key.normalized().subject == "01"
    assert key.to_string() == "sub-01_ses-02_task-rest_run-01"


def test_snapshot_info_serialization():
    snapshot = SnapshotInfo(id="fmriprep", root=Path("/tmp/data"))

    assert snapshot.to_dict()["root"] == "/tmp/data"
    assert SnapshotInfo.from_dict(snapshot.to_dict()).root == Path("/tmp/data")
