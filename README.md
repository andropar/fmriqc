# fmriqa

> **Disclaimer:** Large portions of this codebase were AI-generated and have not been fully manually reviewed. Please verify correctness before using in production or for published research.

Quality assurance pipeline for fMRI preprocessing outputs. Generates interactive HTML reports with metrics, visualizations, and outlier detection.

## Installation

```bash
pip install fmriqa
```

For development:
```bash
git clone https://github.com/andropar/fmriqa.git
cd fmriqa
pip install -e ".[dev]"
```

## Quick start

### Command-line interface

```bash
# Basic usage
fmriqa --derivatives-dir /path/to/derivatives --data-source tedana --n-jobs 4

# Using a manifest for non-standard directory structures
fmriqa --manifest manifest.yaml --n-jobs 4

# Generate reports only (skip metric computation)
fmriqa --reports-only /path/to/existing/QA/dir
```

### Python API

```python
from pathlib import Path
from fmriqa import QAConfig, run_qa
from fmriqa.manifest import generate_manifest_from_globs

# Standard usage
config = QAConfig(
    derivatives_dir=Path("/path/to/derivatives"),
    data_source="tedana",
    n_jobs=4,
)
run_qa(config)

# With manifest - pass it directly, no need to save to disk
manifest = generate_manifest_from_globs(
    bold_pattern="data/**/func/*bold.nii.gz",
    mask_pattern="data/**/func/*mask.nii.gz",
)
config = QAConfig(manifest=manifest, n_jobs=4)
run_qa(config)
```

## What you need

**Required:**
- 4D BOLD NIfTI (`.nii.gz`) - the preprocessed fMRI timeseries

**Optional (but recommended):**
- Brain mask (`.nii.gz`) - if missing, a threshold-based mask is generated
- Motion parameters (`.par` or `.txt`) - needed for FD computation

## Manifest files

For non-standard directory structures, create a manifest that lists your files explicitly.

**YAML format:**
```yaml
name: "My Study"
base_path: "/data/my_study"  # paths below are relative to this

subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "sub-01/ses-01/func/bold.nii.gz"
            mask: "sub-01/ses-01/func/mask.nii.gz"  # optional
            motion: "sub-01/ses-01/func/motion.par"  # optional
            label: "run-01"
```

**Auto-generate from globs:**
```bash
python scripts/generate_qa_manifest.py \
    --bold "data/**/func/*bold.nii.gz" \
    --mask "data/**/func/*mask.nii.gz" \
    --subject-regex "sub-([^/_]+)" \
    --session-regex "ses-([^/_]+)" \
    --validate \
    --output manifest.yaml
```

The `--validate` flag checks that all files exist before writing.

## Command line options

```
--derivatives-dir PATH    Where preprocessed data lives
--manifest FILE           Use manifest instead of glob patterns
--data-source TYPE        tedana, finalinterp, glmsingle, or manifest
--output-dir-name NAME    Output folder name (default: QA)
--n-jobs N                Parallel jobs (default: 1)

--dvars-z-threshold       Standardized DVARS threshold (default: 2.5)
--fd-threshold            FD threshold in mm (default: 0.3)
--exclusion-stringency    liberal, moderate, or conservative

--no-carpetplots          Skip carpetplot generation (faster)
--force-reprocess         Ignore cache, reprocess everything
--reports-only DIR        Just regenerate reports from existing QA dir
--dry-run                 Show what would be processed
```

## Output

```
QA/YYYYMMDD_HHMMSS/
├── index.html                # Main report - open this!
├── qa_config.yaml            # Config used
├── study_summary.json        # Overall metrics
├── outlier_report.json       # Outlier detection
├── exclusions/
│   ├── excluded_runs.tsv     # Runs to exclude
│   └── censor_files/         # Volume-level censoring
├── aggregate_maps/           # Average maps across runs
├── group_plots/              # Comparison plots
└── sub-*/                    # Per-subject reports
```

## Interactive report features

The HTML reports have keyboard shortcuts:
- `j` / `k` - Next/prev run
- `Space` - Toggle run quality (good/bad)
- `f` - Jump to next flagged run
- `/` - Search
- `e` / `c` - Expand/collapse all

You can mark runs as good/bad and export your decisions to JSON.

## Computed metrics

| Metric | What it measures | Good values |
|--------|------------------|-------------|
| tSNR | Temporal signal-to-noise | > 50 |
| DVARS | Frame-to-frame signal change | < 1.5 |
| FD | Head motion (mm) | < 0.3 |
| GCOR | Global correlation | < 0.2 |
| Smoothness | Spatial smoothness (FWHM mm) | depends on your data |

## Module structure

```
src/fmriqa/
├── core.py              # Main pipeline + CLI
├── config.py            # Configuration
├── manifest.py          # Manifest handling
├── processing.py        # Per-run QA computation
├── metrics.py           # Metric functions
├── reporting.py         # HTML generation
├── visualization.py     # Figures
├── outliers.py          # Outlier detection
├── exclusions.py        # Exclusion recommendations
└── report_components/   # CSS, JS, tooltips
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.
