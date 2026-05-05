# Snapshot Comparison

Comparison is optional. It consumes two existing snapshot QA output directories:

```bash
fmriqc compare \
  QA_raw/20260505_143000_snapshot-raw \
  QA_preproc/20260505_151200_snapshot-preproc \
  -o QA_compare/raw_vs_preproc
```

## Pairing

Runs are paired by normalized `RunKey`:

```text
sub-01_ses-01_task-rest_run-01
```

File paths and snapshot ids are not used for pairing. Left-only, right-only,
and duplicate run keys are written to the pairing report.

## Outputs

```text
QA_compare/raw_vs_preproc/
  index.html
  comparison.json
  comparison_summary.tsv
  pairing_report.json
  run_comparisons/
    sub-01_ses-01_task-rest_run-01/
      comparison.json
      series_comparison.json
```

## Interpretation Guardrails

- tSNR increases are often desirable but can be caused by smoothing.
- DVARS decreases may reflect denoising or smoothing; they are not proof of
  better data by themselves.
- Apparent smoothness is contextual.
- FD comparisons are meaningful only when motion provenance is comparable.
- Spatial deltas are only valid when grids match or explicit resampling is
  requested.

Every comparison row includes warnings when inputs are incomplete or not fully
comparable.
