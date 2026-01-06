# Usage Guide

Comprehensive usage examples for fmriqa.

## Basic Examples

### Standard BIDS Dataset

```bash
fmriqa --derivatives-dir /path/to/derivatives --data-source tedana --n-jobs 4
```

### Custom Manifest

```bash
fmriqa --manifest my_study.yaml --n-jobs 4
```

## Advanced Examples

### With Motion Generation

```bash
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 2
```

### Custom Thresholds

```bash
fmriqa --derivatives-dir /path/to/data \
    --fd-threshold 0.5 \
    --dvars-z-threshold 3.0 \
    --exclusion-stringency conservative
```

### Reports Only (Skip Computation)

```bash
fmriqa --reports-only /path/to/existing/QA/20241217_120000
```

## Python API

```python
from pathlib import Path
from fmriqa.orchestration.config import QAConfig
from fmriqa.orchestration.orchestration import run_qa

# Load config from YAML
config = QAConfig.from_yaml("qa_config.yaml")
results = run_qa(config)

# Or create config programmatically
config = QAConfig(
    paths=PathConfig(
        derivatives_dir=Path("/data/derivatives"),
        output_dir_name="QA",
    ),
    processing=ProcessingConfig(
        n_jobs=4,
        generate_motion=True,
    ),
)
results = run_qa(config)
```

For more details, see:
- [Manifest Files](MANIFEST.md)
- [Configuration Options](CONFIGURATION.md)
- [Motion Generation](MOTION_GENERATION.md)
