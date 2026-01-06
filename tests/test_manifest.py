"""Tests for manifest-based input handling.

This test suite covers manifest functionality including:
- BIDS entity extraction from paths
- Manifest data structure creation and serialization
- Manifest loading from YAML/JSON
- Path resolution (absolute and relative)
- Validation
"""

import pytest
import json
import yaml
from pathlib import Path

from fmriqa.io.manifest import (
    BIDSEntityExtractor,
    ManifestRun,
    ManifestSession,
    ManifestSubject,
    QAManifest,
)


# ============================================================================
# BIDS Entity Extraction Tests
# ============================================================================


class TestBIDSEntityExtractor:
    """Test BIDS entity extraction from file paths."""

    def test_extract_standard_bids_path(self):
        """Test extraction from standard BIDS path."""
        path = Path("/data/sub-01/ses-baseline/func/sub-01_ses-baseline_task-rest_run-01_bold.nii.gz")
        entities = BIDSEntityExtractor.extract_from_path(path)

        assert entities['sub'] == '01'
        assert entities['ses'] == 'baseline'
        assert entities['task'] == 'rest'
        assert entities['run'] == '01'
        assert entities['echo'] is None
        assert entities['part'] is None

    def test_extract_multiecho(self):
        """Test extraction from multiecho path."""
        path = Path("/data/sub-02/func/sub-02_task-motor_echo-1_bold.nii.gz")
        entities = BIDSEntityExtractor.extract_from_path(path)

        assert entities['sub'] == '02'
        assert entities['task'] == 'motor'
        assert entities['echo'] == '1'

    def test_extract_phase_part(self):
        """Test extraction of phase part entity."""
        path = Path("/data/sub-01/fmap/sub-01_part-phase_phasediff.nii.gz")
        entities = BIDSEntityExtractor.extract_from_path(path)

        assert entities['sub'] == '01'
        assert entities['part'] == 'phase'

    def test_extract_subject_session(self):
        """Test extracting only subject and session."""
        path = Path("/data/sub-10/ses-02/func/bold.nii.gz")
        subject, session = BIDSEntityExtractor.extract_subject_session(path)

        assert subject == '10'
        assert session == '02'

    def test_non_bids_path(self):
        """Test that non-BIDS paths return None values."""
        path = Path("/data/my_study/participant_001/scan_1.nii.gz")
        entities = BIDSEntityExtractor.extract_from_path(path)

        assert all(v is None for v in entities.values())

    def test_normalize_entity_with_prefix(self):
        """Test normalizing entity that already has prefix."""
        result = BIDSEntityExtractor.normalize_entity('sub', 'sub-01')
        assert result == 'sub-01'

    def test_normalize_entity_without_prefix(self):
        """Test normalizing entity without prefix."""
        result = BIDSEntityExtractor.normalize_entity('ses', 'baseline')
        assert result == 'ses-baseline'

    def test_normalize_empty_value(self):
        """Test normalizing empty value returns None."""
        result = BIDSEntityExtractor.normalize_entity('sub', '')
        assert result is None


# ============================================================================
# Manifest Data Structure Tests
# ============================================================================


class TestManifestRun:
    """Test ManifestRun data structure."""

    def test_create_run_with_all_fields(self, tmp_path):
        """Test creating run with all fields."""
        bold = tmp_path / "bold.nii.gz"
        mask = tmp_path / "mask.nii.gz"
        motion = tmp_path / "motion.par"

        run = ManifestRun(
            bold=bold,
            mask=mask,
            motion=motion,
            label="run-01"
        )

        assert run.bold == bold
        assert run.mask == mask
        assert run.motion == motion
        assert run.label == "run-01"

    def test_create_run_minimal(self, tmp_path):
        """Test creating run with only required field."""
        bold = tmp_path / "bold.nii.gz"
        run = ManifestRun(bold=bold)

        assert run.bold == bold
        assert run.mask is None
        assert run.motion is None
        assert run.label == ""

    def test_run_to_dict(self, tmp_path):
        """Test converting run to dictionary."""
        bold = tmp_path / "bold.nii.gz"
        run = ManifestRun(bold=bold, label="task-rest")

        data = run.to_dict()

        assert data['bold'] == str(bold)
        assert data['mask'] is None
        assert data['label'] == "task-rest"

    def test_run_from_dict_absolute_paths(self, tmp_path):
        """Test creating run from dict with absolute paths."""
        bold_path = tmp_path / "bold.nii.gz"
        bold_path.touch()

        data = {"bold": str(bold_path), "label": "run-01"}
        run = ManifestRun.from_dict(data)

        assert run.bold == bold_path
        assert run.label == "run-01"

    def test_run_from_dict_relative_paths(self, tmp_path):
        """Test creating run from dict with relative paths and base_path."""
        # Create directory structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        bold = data_dir / "bold.nii.gz"
        bold.touch()

        data = {"bold": "data/bold.nii.gz"}
        run = ManifestRun.from_dict(data, base_path=tmp_path)

        assert run.bold == bold
        assert run.bold.exists()


class TestManifestSession:
    """Test ManifestSession data structure."""

    def test_create_session(self):
        """Test creating session."""
        session = ManifestSession(id="ses-01")
        assert session.id == "ses-01"
        assert session.runs == []

    def test_session_with_runs(self, tmp_path):
        """Test session with multiple runs."""
        run1 = ManifestRun(bold=tmp_path / "run1.nii.gz", label="run-01")
        run2 = ManifestRun(bold=tmp_path / "run2.nii.gz", label="run-02")

        session = ManifestSession(id="ses-baseline", runs=[run1, run2])

        assert len(session.runs) == 2
        assert session.runs[0].label == "run-01"
        assert session.runs[1].label == "run-02"

    def test_session_roundtrip(self, tmp_path):
        """Test session to_dict/from_dict roundtrip."""
        bold1 = tmp_path / "run1.nii.gz"
        bold1.touch()

        run = ManifestRun(bold=bold1, label="task-rest")
        session = ManifestSession(id="ses-01", runs=[run])

        # Convert to dict and back
        data = session.to_dict()
        restored = ManifestSession.from_dict(data, base_path=tmp_path)

        assert restored.id == session.id
        assert len(restored.runs) == 1
        assert restored.runs[0].label == "task-rest"


class TestManifestSubject:
    """Test ManifestSubject data structure."""

    def test_create_subject(self):
        """Test creating subject."""
        subject = ManifestSubject(id="sub-01")
        assert subject.id == "sub-01"
        assert subject.sessions == []

    def test_subject_with_sessions(self, tmp_path):
        """Test subject with multiple sessions."""
        ses1 = ManifestSession(id="ses-01")
        ses2 = ManifestSession(id="ses-02")

        subject = ManifestSubject(id="sub-10", sessions=[ses1, ses2])

        assert len(subject.sessions) == 2
        assert subject.sessions[0].id == "ses-01"


# ============================================================================
# QAManifest Tests
# ============================================================================


class TestQAManifest:
    """Test complete QA manifest."""

    def test_create_empty_manifest(self):
        """Test creating empty manifest."""
        manifest = QAManifest()

        assert manifest.subjects == []
        assert manifest.name == ""
        assert manifest.base_path is None

    def test_create_manifest_with_data(self):
        """Test creating manifest with subjects."""
        subject = ManifestSubject(id="sub-01")
        manifest = QAManifest(
            subjects=[subject],
            name="Test Study",
            description="A test dataset"
        )

        assert len(manifest.subjects) == 1
        assert manifest.name == "Test Study"
        assert manifest.description == "A test dataset"

    def test_manifest_to_dict(self, tmp_path):
        """Test converting manifest to dictionary."""
        run = ManifestRun(bold=tmp_path / "bold.nii.gz")
        session = ManifestSession(id="ses-01", runs=[run])
        subject = ManifestSubject(id="sub-01", sessions=[session])

        manifest = QAManifest(subjects=[subject], name="Test")
        data = manifest.to_dict()

        assert data['name'] == "Test"
        assert len(data['subjects']) == 1
        assert data['subjects'][0]['id'] == "sub-01"

    def test_manifest_save_load_yaml(self, tmp_path):
        """Test saving and loading manifest as YAML."""
        # Create manifest
        bold = tmp_path / "data" / "bold.nii.gz"
        bold.parent.mkdir()
        bold.touch()

        run = ManifestRun(bold=bold, label="task-rest")
        session = ManifestSession(id="ses-01", runs=[run])
        subject = ManifestSubject(id="sub-01", sessions=[session])
        manifest = QAManifest(subjects=[subject], name="Test Study")

        # Save
        manifest_file = tmp_path / "manifest.yaml"
        manifest.to_file(manifest_file)

        assert manifest_file.exists()

        # Load
        loaded = QAManifest.from_file(manifest_file)

        assert loaded.name == "Test Study"
        assert len(loaded.subjects) == 1
        assert loaded.subjects[0].id == "sub-01"
        assert len(loaded.subjects[0].sessions) == 1

    def test_manifest_save_load_json(self, tmp_path):
        """Test saving and loading manifest as JSON."""
        bold = tmp_path / "bold.nii.gz"
        bold.touch()

        run = ManifestRun(bold=bold)
        session = ManifestSession(id="ses-baseline", runs=[run])
        subject = ManifestSubject(id="sub-10", sessions=[session])
        manifest = QAManifest(subjects=[subject])

        # Save as JSON
        manifest_file = tmp_path / "manifest.json"
        manifest.to_file(manifest_file)

        # Load
        loaded = QAManifest.from_file(manifest_file)

        assert len(loaded.subjects) == 1
        assert loaded.subjects[0].id == "sub-10"

    def test_manifest_with_base_path_resolution(self, tmp_path):
        """Test manifest with base_path resolves relative paths."""
        # Create directory structure
        base = tmp_path / "study"
        base.mkdir()
        data_dir = base / "data"
        data_dir.mkdir()
        bold = data_dir / "bold.nii.gz"
        bold.touch()

        # Create manifest with relative path
        manifest_file = base / "manifest.yaml"
        manifest_data = {
            "name": "Test",
            "base_path": ".",  # Relative to manifest file
            "subjects": [
                {
                    "id": "sub-01",
                    "sessions": [
                        {
                            "id": "ses-01",
                            "runs": [
                                {"bold": "data/bold.nii.gz"}
                            ]
                        }
                    ]
                }
            ]
        }

        with open(manifest_file, 'w') as f:
            yaml.dump(manifest_data, f)

        # Load manifest
        loaded = QAManifest.from_file(manifest_file)

        # Base path should be resolved relative to manifest
        assert loaded.base_path == base

        # File paths should be resolved correctly
        run_bold = loaded.subjects[0].sessions[0].runs[0].bold
        assert run_bold == bold
        assert run_bold.exists()

    def test_manifest_validation_empty(self):
        """Test validation catches empty manifest."""
        manifest = QAManifest()
        errors = manifest.validate()

        assert len(errors) > 0
        assert any("no subjects" in e.lower() for e in errors)

    def test_manifest_with_qa_config(self):
        """Test manifest with embedded QA configuration."""
        manifest = QAManifest(
            subjects=[ManifestSubject(id="sub-01")],
            qa_config={"fd_threshold": 0.5, "dvars_threshold": 2.5}
        )

        data = manifest.to_dict()

        assert 'qa_config' in data
        assert data['qa_config']['fd_threshold'] == 0.5

    def test_roundtrip_with_all_features(self, tmp_path):
        """Test complete roundtrip with all features."""
        # Create files
        bold = tmp_path / "data" / "bold.nii.gz"
        mask = tmp_path / "data" / "mask.nii.gz"
        bold.parent.mkdir()
        bold.touch()
        mask.touch()

        # Create complex manifest
        run = ManifestRun(bold=bold, mask=mask, label="run-01")
        session = ManifestSession(id="ses-baseline", runs=[run])
        subject = ManifestSubject(id="sub-participant1", sessions=[session])

        manifest = QAManifest(
            subjects=[subject],
            name="Complex Study",
            description="Multi-session study",
            base_path=tmp_path,
            qa_config={"carpetplots": False}
        )

        # Save and load
        manifest_file = tmp_path / "manifest.yaml"
        manifest.to_file(manifest_file)
        loaded = QAManifest.from_file(manifest_file)

        # Verify everything survived roundtrip
        assert loaded.name == manifest.name
        assert loaded.description == manifest.description
        assert loaded.qa_config == manifest.qa_config
        assert len(loaded.subjects) == 1

        loaded_run = loaded.subjects[0].sessions[0].runs[0]
        assert loaded_run.bold.exists()
        assert loaded_run.mask.exists()
        assert loaded_run.label == "run-01"
