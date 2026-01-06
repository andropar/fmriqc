# Python API Reference

## Main Entry Point

```python
from fmriqa.orchestration.orchestration import run_qa
from fmriqa.orchestration.config import QAConfig

config = QAConfig.from_yaml("config.yaml")
results = run_qa(config)
```

## Configuration

```python
from fmriqa.orchestration.config import (
    QAConfig,
    PathConfig,
    ProcessingConfig,
    ThresholdConfig,
)

config = QAConfig(
    paths=PathConfig(...),
    processing=ProcessingConfig(...),
    thresholds=ThresholdConfig(...),
)
```

## Manifest Generation

```python
from fmriqa.io.manifest import generate_manifest_from_globs

manifest = generate_manifest_from_globs(
    bold_pattern="data/**/func/*bold.nii.gz",
    mask_pattern="data/**/func/*mask.nii.gz",
    motion_pattern="data/**/func/*motion.par",
)
manifest.to_yaml("manifest.yaml")
```

## Processing Single Runs

```python
from fmriqa.core.processing import process_single_run
from fmriqa.io.structures import RunInfo

info = RunInfo(
    subject="sub-01",
    session="ses-01",
    run="run-01",
    bold_path=Path("data/bold.nii.gz"),
)

result = process_single_run(info, config, output_dir)
```

## Metrics Computation

```python
from fmriqa.core.metrics import (
    compute_tsnr,
    compute_dvars,
    compute_fd,
    compute_gcor,
)

# Compute specific metrics
tsnr = compute_tsnr(func_data, mask)
dvars = compute_dvars(func_data, mask)
fd = compute_fd(motion_params)
gcor = compute_gcor(func_data, mask)
```

## Outlier Detection

```python
from fmriqa.analysis.outliers import detect_outliers_mahalanobis

outlier_ids, distances = detect_outliers_mahalanobis(
    results,
    metrics=["tsnr_median", "fd_median", "dvars_std_median"],
    threshold=3.0
)
```

For complete API documentation, see source code in `src/fmriqa/`.
