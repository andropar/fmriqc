# Snapshots

A snapshot is one concrete version of an fMRI dataset. Examples:

- raw BOLD
- fMRIPrep output
- tedana output
- denoised output
- smoothed output
- a custom preprocessing result

The main `fmriqc` workflow assesses exactly one snapshot:

```bash
fmriqc assess --manifest snapshot.yaml -o QA_preproc
```

Each output directory includes:

- `snapshot.json`
- `qa_config.yaml`
- `qa_config_resolved.yaml`
- per-run results and provenance
- HTML reports
- TSV/JSON exports

The snapshot id is part of the output directory name:

```text
QA_preproc/20260505_151200_snapshot-preproc/
```

This keeps raw, preprocessed, denoised, and other snapshot outputs distinct.

## Snapshot Metadata

```yaml
snapshot:
  id: preproc
  label: fMRIPrep output
  source_type: preprocessed
  description: Standard fMRIPrep BOLD time series
  pipeline_name: fMRIPrep
  pipeline_version: "24.0.1"
```

## Core Rule

Every snapshot QA output should be interpretable on its own. Comparison is an
optional layer that consumes two completed snapshot QA outputs.
