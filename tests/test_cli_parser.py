"""Tests for CLI/config precedence."""

import yaml

from fmriqc.orchestration.cli_parser import parse_cli


def test_manifest_snapshot_is_used_when_no_cli_snapshot_override(tmp_path):
    bold = tmp_path / "sub-01_ses-01_task-rest_run-01_bold.nii.gz"
    bold.touch()
    manifest_path = tmp_path / "snapshot.yaml"
    manifest_path.write_text(yaml.safe_dump({
        "base_path": ".",
        "snapshot": {
            "id": "manifest-snap",
            "label": "Manifest Snapshot",
            "source_type": "preprocessed",
            "pipeline_name": "Example",
        },
        "runs": [{
            "bold": bold.name,
            "subject": "01",
            "session": "01",
            "task": "rest",
            "run": "01",
        }],
    }))

    command, config = parse_cli(["assess", "--manifest", str(manifest_path)])

    assert command == "assess"
    assert config.snapshot.id == "manifest-snap"
    assert config.snapshot.label == "Manifest Snapshot"
    assert config.snapshot.source_type == "preprocessed"


def test_cli_values_override_loaded_config_without_resetting_omitted_values(tmp_path):
    config_path = tmp_path / "qa_config.yaml"
    config_path.write_text(yaml.safe_dump({
        "processing": {
            "n_jobs": 2,
            "target_echo": 3,
        },
        "thresholds": {
            "fd_threshold": 0.4,
        },
        "visualization": {
            "generate_carpetplots": True,
        },
        "analysis": {
            "detect_outliers": True,
            "generate_exclusions": False,
        },
    }))

    _, config = parse_cli([
        "assess",
        "--config",
        str(config_path),
        "--n-jobs",
        "7",
        "--fd-threshold",
        "0.6",
        "--no-carpetplots",
        "--generate-review-recommendations",
    ])

    assert config.n_jobs == 7
    assert config.target_echo == 3
    assert config.fd_threshold == 0.6
    assert config.generate_carpetplots is False
    assert config.analysis.generate_exclusions is True
