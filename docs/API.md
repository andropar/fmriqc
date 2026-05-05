# Python API Reference

The command-line interface is the primary interface. The Python API mirrors the
same snapshot-first workflow.

## Assess

```python
from fmriqc.orchestration.config import QAConfig
from fmriqc.orchestration.core import run_assess

config = QAConfig.from_yaml("qa_config.yaml")
run_assess(config)
```

`run_qa(config)` remains as a compatibility wrapper for `run_assess(config)`.

## Core Structures

```python
from pathlib import Path
from fmriqc.io.structures import InputRun, RunKey, SnapshotInfo

snapshot = SnapshotInfo(id="preproc", source_type="preprocessed")
run_key = RunKey(subject="01", session="01", task="rest", run="01")
input_run = InputRun(
    snapshot=snapshot,
    run_key=run_key,
    bold_path=Path("sub-01_task-rest_run-01_bold.nii.gz"),
)
```

## Manifests

```python
from fmriqc.io.manifest import QAManifest

manifest = QAManifest.from_file("snapshot.yaml")
input_runs = manifest.to_input_runs()
```

## Single Run Processing

```python
from fmriqc.core.processing import process_single_run

result = process_single_run(input_run, config, output_dir)
```

The legacy `Path` input is still accepted, but new code should pass
`InputRun`.

## Motion Loading

```python
from fmriqc.core.motion import load_fd_series

fd, motion_info = load_fd_series("confounds.tsv")
```

## Comparison

```python
from fmriqc.comparison.io import load_snapshot_results
from fmriqc.comparison.metrics import compare_pair
from fmriqc.comparison.pairing import pair_results

left_snapshot, left_results = load_snapshot_results("QA_raw/...")
right_snapshot, right_results = load_snapshot_results("QA_preproc/...")
pairing = pair_results(left_results, right_results)
comparisons = [compare_pair(pair) for pair in pairing.paired]
```
