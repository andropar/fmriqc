# Motion Inputs and Generation

`fmriqc` uses framewise displacement for run flags, volume review, and
candidate censor vectors. Motion provenance is recorded for every run.

## Supported Motion Inputs

Preferred:

- fMRIPrep-style confounds TSV with a `framewise_displacement` column.

Also supported:

- fMRIPrep-style confounds TSV with six motion columns:
  `rot_x`, `rot_y`, `rot_z`, `trans_x`, `trans_y`, `trans_z`.
- FSL/MCFLIRT `.par` files.
- Generated MCFLIRT `.par` files when motion is missing and generation is
  enabled.

When both `confounds` and `motion` are provided in a manifest, the first
existing file is used, preferring confounds over `.par` files.

## Generating Missing Motion

```bash
fmriqc assess --manifest snapshot.yaml --generate-motion --n-jobs 2
```

Equivalent explicit configuration:

```bash
fmriqc assess \
  --manifest snapshot.yaml \
  --motion-strategy generate_if_missing
```

MCFLIRT generation requires Docker, Singularity, or Apptainer and an FSL
container. You can provide a container explicitly:

```bash
fmriqc assess \
  --manifest snapshot.yaml \
  --generate-motion \
  --fsl-container /path/to/fsl_container.sif
```

For Singularity/Apptainer, `--container-download ask|never|auto` controls what
happens when the default FSL container is missing. `never` fails without a
prompt, which is safer for batch jobs; `auto` downloads without prompting.

## Interpretation

Motion generated from raw BOLD can be used as a fallback estimate of acquisition
head motion.

Motion generated from already-preprocessed BOLD is a residual realignment
estimate. It may be useful diagnostically, but it should not be interpreted as
the original amount of subject motion. `fmriqc` records this distinction in
`motion_info` and report provenance.

## Manifest Example

```yaml
version: 2
snapshot:
  id: preproc
  source_type: preprocessed
runs:
  - subject: "01"
    session: "01"
    run: "01"
    bold: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-preproc_bold.nii.gz
    mask: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-brain_mask.nii.gz
    confounds: sub-01/ses-01/func/sub-01_ses-01_task-rest_run-01_desc-confounds_timeseries.tsv
```

If `confounds` and `motion` are both absent and generation is disabled, the run
is still processed with missing-motion warnings and FD metrics marked missing.
