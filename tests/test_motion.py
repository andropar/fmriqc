"""Tests for motion loading and FD provenance."""

import numpy as np

from fmriqc.core.motion import load_fd_series


def test_load_fd_from_fmriprep_confounds(tmp_path):
    confounds = tmp_path / "confounds.tsv"
    confounds.write_text("framewise_displacement\n\n0.1\n0.2\n")

    fd, info = load_fd_series(confounds)

    assert fd.tolist() == [0.0, 0.1, 0.2]
    assert info.source == "provided_confounds"
    assert info.fd_source == "framewise_displacement_column"


def test_load_fd_from_confounds_motion_columns(tmp_path):
    confounds = tmp_path / "confounds.tsv"
    confounds.write_text(
        "rot_x\trot_y\trot_z\ttrans_x\ttrans_y\ttrans_z\n"
        "0\t0\t0\t0\t0\t0\n"
        "0.01\t0\t0\t1\t0\t0\n"
    )

    fd, info = load_fd_series(confounds)

    assert len(fd) == 2
    assert fd[0] == 0.0
    assert fd[1] > 0.0
    assert info.fd_source == "computed_from_6params"


def test_load_fd_from_fsl_par(tmp_path):
    par = tmp_path / "motion.par"
    np.savetxt(par, np.array([
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0, 2.0, 0.0],
    ]))

    fd, info = load_fd_series(par, generated=True, diagnostic_only=True)

    assert fd.tolist() == [0.0, 1.0, 2.0]
    assert info.source == "generated_from_snapshot_mcflirt"
    assert info.generated is True
    assert info.diagnostic_only is True


def test_confounds_without_motion_columns_warns(tmp_path):
    confounds = tmp_path / "confounds.tsv"
    confounds.write_text("csf\twhite_matter\n1\t2\n")

    fd, info = load_fd_series(confounds)

    assert fd.size == 0
    assert info.fd_source == "none"
    assert info.warnings
