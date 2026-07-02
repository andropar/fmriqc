"""Tests for input discovery and BIDS-sidecar matching."""

from fmriqc.orchestration.config import PathConfig, ProcessingConfig, QAConfig
from fmriqc.orchestration.discovery import _find_confounds, discover_input_runs


def test_find_confounds_requires_matching_bids_entities(tmp_path):
    func = tmp_path / "sub-01" / "ses-01" / "func"
    func.mkdir(parents=True)
    bold = func / "sub-01_ses-01_task-rest_run-01_desc-preproc_bold.nii.gz"
    wrong_run = func / "sub-01_ses-01_task-rest_run-02_desc-confounds_timeseries.tsv"
    right_run = func / "sub-01_ses-01_task-rest_run-01_desc-confounds_timeseries.tsv"
    bold.touch()
    wrong_run.touch()
    right_run.touch()

    assert _find_confounds(bold) == right_run


def test_fmriprep_data_source_discovers_preproc_bold_mask_and_confounds(tmp_path):
    func = tmp_path / "sub-01" / "ses-01" / "func"
    func.mkdir(parents=True)
    bold = func / "sub-01_ses-01_task-rest_run-01_desc-preproc_bold.nii.gz"
    mask = func / "sub-01_ses-01_task-rest_run-01_desc-brain_mask.nii.gz"
    confounds = func / "sub-01_ses-01_task-rest_run-01_desc-confounds_timeseries.tsv"
    bold.touch()
    mask.touch()
    confounds.touch()

    config = QAConfig(
        paths=PathConfig(derivatives_dir=tmp_path),
        processing=ProcessingConfig(data_source="fmriprep"),
    )

    input_runs, base_output = discover_input_runs(config)

    assert base_output == tmp_path.resolve()
    assert len(input_runs) == 1
    assert input_runs[0].bold_path == bold
    assert input_runs[0].mask_path == mask
    assert input_runs[0].confounds_path == confounds
