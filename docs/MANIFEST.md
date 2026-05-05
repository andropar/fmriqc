# Manifest File Format

Manifest files explicitly list the runs in a snapshot. Version 2 uses a flat
`runs:` list and is the recommended format.

## Version 2

```yaml
version: 2
name: Main fMRIPrep QA
description: Standard preprocessed BOLD time series
base_path: /data/project

snapshot:
  id: preproc
  label: fMRIPrep output
  source_type: preprocessed
  pipeline_name: fMRIPrep
  pipeline_version: "24.0.1"

runs:
  - subject: "01"
    session: "01"
    task: rest
    run: "01"
    bold: derivatives/fmriprep/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-preproc_bold.nii.gz
    mask: derivatives/fmriprep/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-brain_mask.nii.gz
    confounds: derivatives/fmriprep/sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-confounds_timeseries.tsv
```

Fields:

- `bold`: required 4D BOLD NIfTI.
- `mask`: optional mask. If omitted, `fmriqc` tries derivative discovery or an
  automatic threshold mask.
- `confounds`: optional fMRIPrep-style TSV. Preferred when it contains
  `framewise_displacement`.
- `motion`: optional FSL/MCFLIRT `.par` file.
- `subject`, `session`, `task`, `run`, `echo`, `acquisition`, `part`: optional
  explicit BIDS entities. Explicit manifest entities override path parsing.
- `label`: display label only. If both `run` and `label` are present, `run`
  controls identity.

## Legacy Version 1

The older hierarchical manifest shape is still accepted:

```yaml
base_path: /data/project
subjects:
  - id: sub-01
    sessions:
      - id: ses-01
        runs:
          - bold: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_bold.nii.gz
            mask: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_mask.nii.gz
            motion: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01.par
            label: run-01
```

Version 1 manifests are converted internally to `InputRun` objects.

## Embedded Config

Manifests may include a `qa_config:` block. CLI options still override values
provided on the command line.

```yaml
qa_config:
  snapshot:
    id: preproc
  motion:
    strategy: prefer_provided
  analysis:
    generate_exclusions: false
```

## Validation

Validation checks that required BOLD paths exist and that optional mask,
motion, and confounds paths exist when provided. Missing subject information
must be recoverable from the manifest or path.
