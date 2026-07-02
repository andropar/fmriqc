"""Tests for v2 flat manifests and v1 compatibility."""


import yaml

from fmriqc.io.manifest import QAManifest


def test_manifest_v2_to_input_runs(tmp_path):
    bold = tmp_path / "sub-01" / "ses-01" / "func" / "sub-01_ses-01_task-rest_run-01_desc-preproc_bold.nii.gz"
    mask = tmp_path / "sub-01" / "ses-01" / "func" / "sub-01_ses-01_task-rest_run-01_desc-brain_mask.nii.gz"
    confounds = tmp_path / "sub-01" / "ses-01" / "func" / "sub-01_ses-01_task-rest_run-01_desc-confounds_timeseries.tsv"
    bold.parent.mkdir(parents=True)
    bold.touch()
    mask.touch()
    confounds.touch()

    manifest_path = tmp_path / "snapshot.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "version": 2,
        "base_path": ".",
        "snapshot": {
            "id": "fmriprep",
            "label": "fMRIPrep output",
            "source_type": "preprocessed",
        },
        "runs": [{
            "subject": "01",
            "session": "01",
            "task": "rest",
            "run": "01",
            "label": "display-only",
            "bold": str(bold.relative_to(tmp_path)),
            "mask": str(mask.relative_to(tmp_path)),
            "confounds": str(confounds.relative_to(tmp_path)),
        }],
    }))

    manifest = QAManifest.from_file(manifest_path)
    input_runs = manifest.to_input_runs()

    assert manifest.version == 2
    assert input_runs[0].snapshot.id == "fmriprep"
    assert input_runs[0].run_key.to_string() == "sub-01_ses-01_task-rest_run-01"
    assert input_runs[0].label == "display-only"
    assert input_runs[0].bold_path == bold
    assert input_runs[0].mask_path == mask
    assert input_runs[0].confounds_path == confounds


def test_manifest_v1_backward_compatibility(tmp_path):
    bold = tmp_path / "sub-02" / "ses-01" / "func" / "sub-02_ses-01_task-rest_bold.nii.gz"
    bold.parent.mkdir(parents=True)
    bold.touch()

    manifest_path = tmp_path / "legacy.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "base_path": ".",
        "subjects": [{
            "id": "sub-02",
            "sessions": [{
                "id": "ses-01",
                "runs": [{
                    "bold": str(bold.relative_to(tmp_path)),
                    "label": "run-03",
                }],
            }],
        }],
    }))

    manifest = QAManifest.from_file(manifest_path)
    input_run = manifest.to_input_runs()[0]

    assert manifest.version == 1
    assert input_run.run_key.to_string() == "sub-02_ses-01_task-rest_run-03"


def test_hierarchical_manifest_preserves_run_entities_and_motion_format(tmp_path):
    bold = tmp_path / "custom_bold.nii.gz"
    bold.touch()

    manifest_path = tmp_path / "legacy_entities.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "base_path": ".",
        "subjects": [{
            "id": "sub-03",
            "sessions": [{
                "id": "ses-02",
                "runs": [{
                    "bold": str(bold.relative_to(tmp_path)),
                    "task": "nback",
                    "run": "07",
                    "echo": "2",
                    "acquisition": "mb",
                    "part": "mag",
                    "motion_format": "fsl_par",
                    "label": "display-label",
                }],
            }],
        }],
    }))

    input_run = QAManifest.from_file(manifest_path).to_input_runs()[0]

    assert input_run.run_key.to_string() == (
        "sub-03_ses-02_task-nback_run-07_echo-2_acq-mb_part-mag"
    )
    assert input_run.metadata["motion_format"] == "fsl_par"
