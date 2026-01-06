# Configuration Options

Complete reference for all configuration options.

## Command-Line Options

### Input Options

- `--derivatives-dir PATH` - Derivatives directory containing preprocessed data
- `--bids-root PATH` - BIDS root directory (optional)
- `--manifest FILE` - Manifest file path (YAML/JSON)
- `--config FILE` - Configuration YAML file

### Data Source

- `--data-source TYPE` - Data source preset (finalinterp, tedana, glmsingle, manifest)
- `--glob-pattern PATTERN` - Custom glob pattern (overrides preset)
- `--glmsingle-input-source TYPE` - Which preprocessing was used for glmsingle (finalinterp or tedana)

### Output

- `--output-dir-name NAME` - Output directory name (default: QA)
- `--no-hierarchical` - Disable hierarchical reports
- `--no-carpetplots` - Skip carpetplot generation

### Processing

- `--n-jobs N` - Number of parallel jobs (default: 1)
- `--target-echo N` - Target echo for multi-echo data (default: 2)
- `--no-cache` - Disable incremental caching
- `--force-reprocess` - Force reprocessing (ignore cache)
- `--generate-motion` - Generate motion parameters using FSL mcflirt
- `--fsl-container PATH` - Path to FSL Singularity container (for custom locations)

### Quality Thresholds

- `--dvars-z-threshold FLOAT` - DVARS Z-score threshold (default: 2.5)
- `--fd-threshold FLOAT` - FD threshold in mm (default: 0.3)
- `--fd-median-threshold FLOAT` - Median FD threshold for run exclusion (default: 0.2)
- `--outlier-threshold FLOAT` - Proportion of outlier timepoints for flagging (default: 0.02)
- `--tsnr-drop-threshold FLOAT` - tSNR dropout threshold (default: 0.25)
- `--outlier-metric-threshold FLOAT` - Mahalanobis distance threshold (default: 3.0)

### Exclusion Recommendations

- `--exclusion-stringency TYPE` - Stringency level (liberal, moderate, conservative)

### Reuse/Regenerate

- `--reuse-from PATH` - Reuse cached QA results from previous output directory
- `--reports-only PATH` - Regenerate reports from existing QA directory without recomputing metrics

### Utility

- `--dry-run` - Print runs that would be processed without running QA

## Configuration File Format

YAML format with hierarchical structure:

```yaml
paths:
  derivatives_dir: /path/to/derivatives
  bids_root: /path/to/bids  # optional
  output_dir_name: QA

processing:
  n_jobs: 4
  target_echo: 2
  use_cache: true
  force_reprocess: false
  data_source: tedana
  glob_pattern: ""  # empty = use data_source preset
  generate_motion: false
  fsl_container_path: null  # null = auto-download

thresholds:
  dvars_z_threshold: 2.5
  fd_threshold: 0.3
  fd_median_threshold: 0.2
  outlier_threshold: 0.02
  tsnr_drop_threshold: 0.25
  outlier_metric_threshold: 3.0

visualization:
  generate_carpetplots: true

analysis:
  exclusion_stringency: moderate  # liberal, moderate, conservative

reporting:
  organize_hierarchical: true
```

## Python API

```python
from pathlib import Path
from fmriqa.orchestration.config import (
    QAConfig,
    PathConfig,
    ProcessingConfig,
    ThresholdConfig,
)

# Create config programmatically
config = QAConfig(
    paths=PathConfig(
        derivatives_dir=Path("/data/derivatives"),
        output_dir_name="QA",
    ),
    processing=ProcessingConfig(
        n_jobs=4,
        generate_motion=True,
    ),
    thresholds=ThresholdConfig(
        fd_threshold=0.5,
        dvars_z_threshold=3.0,
    ),
)

# Or load from YAML
config = QAConfig.from_yaml("qa_config.yaml")

# Save to YAML
config.to_yaml("saved_config.yaml")
```

For more details, see `src/fmriqa/orchestration/config.py`.
