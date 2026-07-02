# fmriqc

`fmriqc` is an interactive QA and review tool for fMRI data snapshots.

A snapshot is one concrete version of a dataset, such as raw BOLD, fMRIPrep
output, tedana output, denoised data, smoothed data, or a custom preprocessing
result. The main workflow assesses one snapshot. An optional comparison command
can then compare two already-assessed snapshots of the same dataset.

The project is intended as a lightweight derivative-snapshot QA, comparison, and
manual review companion, not as a full replacement for MRIQC's broader BIDS-App
metric catalog.

> Disclaimer: Large portions of this codebase were AI-generated and have not
> been fully manually reviewed. Verify correctness before using it for published
> research or production workflows.

## Features

- Snapshot-based fMRI time-series QA
- Manifest and BIDS-derivative input modes
- Run-level metrics including tSNR, DVARS, FD, GCOR, AR(1), signal coverage,
  and apparent smoothness
- fMRIPrep confounds TSV, FSL `.par`, and optional MCFLIRT motion fallback
- Provenance-aware HTML reports for run review
- Exported metrics, flags, provenance, and candidate censor vectors
- Optional comparison of two existing snapshot QA outputs
- Output-local cache metadata for report regeneration and explicit reuse loading

`fmriqc` does not currently provide beta-map QA, task event validation,
distortion-correction quality assessment, cardiac/respiratory noise inference
from BOLD alone, final automatic exclusion decisions, or non-HTML reports.

## Report Preview

The main output is a self-contained HTML review report. The study view gives a
snapshot-level summary, run table, and metric distributions:

![fmriqc study dashboard](docs/assets/screenshots/fmriqc-study-dashboard.jpg)

Subject reports add the review timeline and per-run drill-downs:

![fmriqc subject report](docs/assets/screenshots/fmriqc-subject-report.jpg)

## Installation

```bash
pip install fmriqc
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

Assess one snapshot from a manifest:

```bash
fmriqc assess --manifest snapshot.yaml -o QA_preproc --n-jobs 4
```

The included `ds001419_simple.yaml` smoke manifest can be used with a local
sample dataset when developing docs or checking the report flow:

```bash
fmriqc assess \
  --manifest ds001419_simple.yaml \
  --snapshot-id docs-smoke \
  --snapshot-label "ds001419 docs smoke" \
  --snapshot-source-type raw \
  -o QA_docs_screenshots
```

Backward-compatible assess mode also works:

```bash
fmriqc --manifest snapshot.yaml -o QA_preproc --n-jobs 4
```

Assess a BIDS-derivative tree:

```bash
fmriqc assess \
  --derivatives-dir /data/derivatives/fmriprep \
  --data-source fmriprep \
  --snapshot-id fmriprep \
  --snapshot-source-type preprocessed \
  -o QA_preproc
```

Compare two completed snapshot QA outputs:

```bash
fmriqc compare \
  QA_raw/20260505_143000_snapshot-raw \
  QA_preproc/20260505_151200_snapshot-preproc \
  -o QA_compare/raw_vs_preproc
```

Regenerate reports for an existing QA directory:

```bash
fmriqc report QA_preproc/20260505_151200_snapshot-preproc
```

## Manifest Example

```yaml
version: 2
name: Main fMRIPrep QA
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

## Output Shape

```text
QA_preproc/20260505_151200_snapshot-preproc/
  index.html
  snapshot.json
  qa_config.yaml
  qa_config_resolved.yaml
  qa_cache.json
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

Each `assess` run creates a new timestamped output directory. The cache stored in
that directory is used for report regeneration and explicit reuse/report-loading
workflows; normal repeat runs do not currently share a persistent global cache.

## Documentation

- [Installation](docs/INSTALL.md)
- [Usage](docs/USAGE.md)
- [Snapshots](docs/SNAPSHOTS.md)
- [Manifest Files](docs/MANIFEST.md)
- [Metrics](docs/METRICS.md)
- [Motion Generation](docs/MOTION_GENERATION.md)
- [Outputs](docs/OUTPUTS.md)
- [Comparison](docs/COMPARISON.md)
- [Configuration](docs/CONFIGURATION.md)
- [Python API](docs/API.md)

## Development Checks

```bash
python -m compileall src tests
pytest tests -q
ruff check src tests
```

## License

MIT License. See [LICENSE](LICENSE).
