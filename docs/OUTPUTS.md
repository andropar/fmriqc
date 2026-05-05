# Outputs

An assessment command creates a timestamped snapshot QA directory:

```text
QA_preproc/20260505_151200_snapshot-preproc/
  index.html
  snapshot.json
  qa_config.yaml
  qa_config_resolved.yaml
  study_summary.json
  metrics/run_metrics.tsv
  metrics/run_flags.tsv
  provenance/run_provenance.tsv
  censor/candidate_censor_vectors/
  sub-01/ses-01/sub-01_ses-01_task-rest_run-01/
    result.json
    arrays.npz
    series.json
    figures...
```

## Key Files

- `index.html`: main snapshot QA report.
- `snapshot.json`: snapshot id, label, source type, and pipeline metadata.
- `qa_config.yaml`: input configuration.
- `qa_config_resolved.yaml`: resolved thresholds used for flags.
- `metrics/run_metrics.tsv`: run-level metrics.
- `metrics/run_flags.tsv`: threshold-based run flags.
- `provenance/run_provenance.tsv`: BOLD, mask, and motion provenance.
- `censor/candidate_censor_vectors/`: optional candidate censor vectors.
- `result.json`: per-run metadata and flags.
- `arrays.npz`: per-run arrays for maps and series.
- `series.json`: web-friendly FD, DVARS, global signal, and related series.

## Review Data

Browser review decisions are exported as downloads from the HTML report. They
include schema version, snapshot id, run keys, statuses, and notes. Static HTML
reports do not write decisions back to disk automatically.
