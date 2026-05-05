# Configuration Options

This page documents the public configuration surface for snapshot QA.

## Assess CLI

Input:

- `--manifest FILE`: YAML or JSON manifest.
- `--derivatives-dir PATH`: directory to search in glob mode.
- `--bids-root PATH`: optional BIDS root.
- `--config FILE`: load a saved YAML config.
- `--data-source finalinterp|tedana|manifest`: discovery preset.
- `--glob-pattern PATTERN`: custom discovery pattern.

Snapshot identity:

- `--snapshot-id ID`: short stable snapshot id.
- `--snapshot-label LABEL`: display label.
- `--snapshot-source-type raw|preprocessed|denoised|smoothed|custom`.

Output:

- `-o, --output-dir-name NAME`: output root name.
- `--no-carpetplots`: skip carpet plots.

Processing:

- `--n-jobs N`: number of worker processes.
- `--target-echo N`: target echo for legacy motion lookup.
- `--no-cache`: disable cache reuse.
- `--force-reprocess`: ignore existing cache entries.
- `--dry-run`: list discovered runs.

Motion:

- `--generate-motion`: generate MCFLIRT motion only when supported motion is missing.
- `--motion-strategy prefer_provided|generate_if_missing|none`.
- `--fsl-container PATH`: FSL container path.
- `--container-download ask|never|auto`.

Thresholds:

- `--threshold-profile lenient|default|strict`.
- `--fd-threshold FLOAT`: volume FD threshold.
- `--fd-median-threshold FLOAT`: run-level median FD threshold.
- `--dvars-z-threshold FLOAT`: standardized DVARS threshold.
- `--outlier-threshold FLOAT`: outlier-fraction threshold.
- `--outlier-metric-threshold FLOAT`: Mahalanobis threshold.

Review support:

- `--disable-outliers`: skip study-level outlier detection.
- `--generate-review-recommendations`: write candidate run flags and candidate
  censor vectors.
- `--exclusion-stringency liberal|moderate|conservative`: legacy name for the
  candidate review profile.

Reuse:

- `--reuse-from PATH`: reuse cached results from a previous output directory.

## Compare CLI

```bash
fmriqc compare LEFT_QA_DIR RIGHT_QA_DIR -o OUTPUT
```

Options:

- `--left-label LABEL`
- `--right-label LABEL`
- `--spatial-compare-mode side-by-side|resample-left-to-right|resample-right-to-left`

The default spatial mode is side-by-side.

## YAML Shape

```yaml
paths:
  derivatives_dir: /data/derivatives/fmriprep
  bids_root: /data/bids
  manifest_path: null
  output_dir_name: QA_preproc

snapshot:
  id: preproc
  label: fMRIPrep output
  source_type: preprocessed
  pipeline_name: fMRIPrep
  pipeline_version: "24.0.1"

processing:
  n_jobs: 4
  use_cache: true
  force_reprocess: false
  data_source: finalinterp
  glob_pattern: ""

motion:
  strategy: prefer_provided
  generation_tool: mcflirt
  fsl_container_path: null
  download_policy: ask
  diagnostic_only_for_preprocessed: true

thresholds:
  profile: default
  fd_threshold: 0.3
  fd_median_threshold: 0.2
  dvars_z_threshold: 2.5
  outlier_threshold: 0.02
  outlier_metric_threshold: 3.0

analysis:
  detect_outliers: true
  generate_exclusions: false
  exclusion_stringency: moderate

visualization:
  generate_carpetplots: true

reporting:
  generate_group_plots: true
```

`qa_config_resolved.yaml` records resolved thresholds for each output run.
