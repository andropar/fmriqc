# Manifest File Format

Manifest files allow you to specify custom data layouts for non-BIDS datasets.

## Format

YAML format with hierarchical structure:

```yaml
name: "Study Name"  # optional
base_path: "/path/to/data"  # optional, paths below are relative to this

subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "path/to/bold.nii.gz"  # required
            mask: "path/to/mask.nii.gz"  # optional
            motion: "path/to/motion.par"  # optional
            run: "run-01"  # run label
            label: "task-rest"  # optional task label

qa_config:  # optional embedded configuration
  processing:
    generate_motion: true
    n_jobs: 2
  thresholds:
    fd_threshold: 0.5
    dvars_z_threshold: 3.0
```

## Examples

### Minimal Manifest

```yaml
subjects:
  - id: "01"
    sessions:
      - id: "01"
        runs:
          - bold: "data/sub-01/bold.nii.gz"
            run: "run-01"
```

### With Motion Generation

```yaml
subjects:
  - id: "01"
    sessions:
      - id: "01"
        runs:
          - bold: "data/sub-01/bold.nii.gz"
            mask: "data/sub-01/mask.nii.gz"
            # motion: omitted - will be generated
            run: "run-01"

qa_config:
  processing:
    generate_motion: true
```

### Multiple Subjects and Sessions

```yaml
base_path: "/data/study"

subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "sub-01/ses-01/func/bold_run-01.nii.gz"
            motion: "sub-01/ses-01/func/motion_run-01.par"
            run: "run-01"
          - bold: "sub-01/ses-01/func/bold_run-02.nii.gz"
            motion: "sub-01/ses-01/func/motion_run-02.par"
            run: "run-02"
      - id: "ses-02"
        runs:
          - bold: "sub-01/ses-02/func/bold_run-01.nii.gz"
            run: "run-01"
  - id: "sub-02"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "sub-02/ses-01/func/bold_run-01.nii.gz"
            run: "run-01"
```

## Validation

The manifest is validated when loaded:
- All `bold` files must exist
- If `mask` specified, must exist
- If `motion` specified, must exist
- Subject, session, and run IDs must be unique

## Related

- [Motion Generation Guide](MOTION_GENERATION.md) - Using `--generate-motion`
- [Usage Guide](USAGE.md) - Command-line examples
