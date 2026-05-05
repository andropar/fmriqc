"""Tests for I/O operations and BIDS parsing.

This test suite covers I/O functionality including:
- BIDS entity extraction
- RunInfo creation from paths and manifests
- BIDSPathResolver for finding related files
- File discovery (masks, motion params)
- Path resolution and normalization
"""

from pathlib import Path

import pytest

from fmriqc.io.io import (
    BIDSPathResolver,
    create_run_info,
    create_run_info_from_manifest,
    extract_entities,
    find_mask_path,
    locate_motion_params,
    resolve_subject_session,
)
from fmriqc.io.structures import RunInfo

# ============================================================================
# Entity Extraction Tests
# ============================================================================


class TestExtractEntities:
    """Test BIDS entity extraction from filenames."""

    def test_extract_standard_bids_filename(self):
        """Test extraction from standard BIDS filename."""
        filename = "sub-01_ses-baseline_task-rest_run-01_bold.nii.gz"
        entities = extract_entities(filename)

        assert entities['sub'] == '01'
        assert entities['ses'] == 'baseline'
        assert entities['task'] == 'rest'
        assert entities['run'] == '01'
        assert entities['echo'] is None
        assert entities['part'] is None

    def test_extract_multiecho_filename(self):
        """Test extraction from multiecho filename."""
        filename = "sub-02_task-motor_echo-2_bold.nii.gz"
        entities = extract_entities(filename)

        assert entities['sub'] == '02'
        assert entities['task'] == 'motor'
        assert entities['echo'] == '2'

    def test_extract_with_part(self):
        """Test extraction with part entity."""
        filename = "sub-01_ses-01_task-rest_part-phase_bold.nii.gz"
        entities = extract_entities(filename)

        assert entities['sub'] == '01'
        assert entities['ses'] == '01'
        assert entities['task'] == 'rest'
        assert entities['part'] == 'phase'

    def test_extract_with_desc(self):
        """Test extraction with desc entity."""
        filename = "sub-01_task-rest_desc-preprocessed_bold.nii.gz"
        entities = extract_entities(filename)

        assert entities['sub'] == '01'
        assert entities['task'] == 'rest'
        assert entities['desc'] == 'preprocessed'

    def test_extract_minimal_filename(self):
        """Test extraction from minimal filename."""
        filename = "sub-10_bold.nii.gz"
        entities = extract_entities(filename)

        assert entities['sub'] == '10'
        # All others should be None
        assert all(entities[k] is None for k in ['ses', 'task', 'run', 'echo', 'part', 'desc'])


# ============================================================================
# Subject/Session Resolution Tests
# ============================================================================


class TestResolveSubjectSession:
    """Test subject/session resolution from paths."""

    def test_resolve_from_standard_path(self):
        """Test resolution from standard BIDS path."""
        path = Path("/data/sub-01/ses-baseline/func/file.nii.gz")
        subject, session = resolve_subject_session(path)

        assert subject == "sub-01"
        assert session == "ses-baseline"

    def test_resolve_from_deep_path(self):
        """Test resolution from deeply nested path."""
        path = Path("/study/derivatives/pipeline/sub-02/ses-01/func/processed/file.nii.gz")
        subject, session = resolve_subject_session(path)

        assert subject == "sub-02"
        assert session == "ses-01"

    def test_resolve_missing_session_raises(self):
        """Test that missing session raises ValueError."""
        path = Path("/data/sub-01/func/file.nii.gz")

        with pytest.raises(ValueError, match="Cannot resolve subject/session"):
            resolve_subject_session(path)

    def test_resolve_missing_subject_raises(self):
        """Test that missing subject raises ValueError."""
        path = Path("/data/ses-01/func/file.nii.gz")

        with pytest.raises(ValueError, match="Cannot resolve subject/session"):
            resolve_subject_session(path)


# ============================================================================
# RunInfo Creation Tests
# ============================================================================


class TestCreateRunInfo:
    """Test RunInfo creation from paths."""

    def test_create_from_bids_path(self):
        """Test creating RunInfo from BIDS path."""
        path = Path("/data/sub-01/ses-baseline/func/sub-01_ses-baseline_task-rest_run-01_bold.nii.gz")
        info = create_run_info(path)

        assert info.subject == "01"
        assert info.session == "baseline"
        assert info.task == "rest"
        assert info.run == "01"
        assert info.path == path

    def test_create_from_path_without_entities(self):
        """Test creating RunInfo from path without all entities in filename."""
        # Path has sub/ses in directory structure
        path = Path("/data/sub-10/ses-02/func/bold.nii.gz")
        info = create_run_info(path)

        assert info.subject == "10"
        assert info.session == "02"
        assert info.run == "01"  # Default run

    def test_create_from_multiecho(self):
        """Test creating RunInfo from multiecho."""
        path = Path("/data/sub-01/ses-01/func/sub-01_ses-01_task-motor_echo-2_bold.nii.gz")
        info = create_run_info(path)

        assert info.subject == "01"
        assert info.session == "01"
        assert info.task == "motor"
        assert info.echo == "2"


class TestCreateRunInfoFromManifest:
    """Test RunInfo creation from manifest data."""

    def test_create_from_manifest(self, tmp_path):
        """Test creating RunInfo from manifest entry."""
        bold_path = tmp_path / "sub-01_ses-01_task-rest_bold.nii.gz"

        info = create_run_info_from_manifest(
            bold_path=bold_path,
            subject_id="sub-01",
            session_id="ses-01",
            run_label="run-01",
        )

        assert info.subject == "01"
        assert info.session == "01"
        assert info.run == "01"
        assert info.task == "rest"

    def test_create_strips_prefixes(self, tmp_path):
        """Test that sub-/ses- prefixes are stripped."""
        bold_path = tmp_path / "bold.nii.gz"

        info = create_run_info_from_manifest(
            bold_path=bold_path,
            subject_id="sub-participant1",
            session_id="ses-baseline",
            run_label="run-02",
        )

        assert info.subject == "participant1"
        assert info.session == "baseline"
        assert info.run == "02"

    def test_create_extracts_run_from_label(self, tmp_path):
        """Test extracting run number from label."""
        bold_path = tmp_path / "bold.nii.gz"

        info = create_run_info_from_manifest(
            bold_path=bold_path,
            subject_id="01",
            session_id="01",
            run_label="run-03",
        )

        assert info.run == "03"

    def test_create_with_custom_label(self, tmp_path):
        """Test with custom run label."""
        bold_path = tmp_path / "bold.nii.gz"

        info = create_run_info_from_manifest(
            bold_path=bold_path,
            subject_id="01",
            session_id="01",
            run_label="resting_state",
        )

        # Custom label used as-is if no run- prefix
        assert info.run == "resting_state"


# ============================================================================
# BIDSPathResolver Tests
# ============================================================================


class TestBIDSPathResolver:
    """Test BIDSPathResolver functionality."""

    def test_find_mask_final_convention(self, tmp_path):
        """Test finding mask with _final convention."""
        # Create directory structure
        func_dir = tmp_path / "sub-01" / "ses-01" / "func"
        func_dir.mkdir(parents=True)

        bold_path = func_dir / "sub-01_ses-01_task-rest_run-01_final.nii.gz"
        mask_path = func_dir / "sub-01_ses-01_task-rest_run-01_final_mask.nii.gz"

        bold_path.touch()
        mask_path.touch()

        info = RunInfo(
            path=bold_path,
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        resolver = BIDSPathResolver()
        found_mask = resolver.find_mask(bold_path, info)

        assert found_mask == mask_path

    def test_find_mask_glob_pattern(self, tmp_path):
        """Test finding mask using glob pattern."""
        func_dir = tmp_path / "sub-01" / "ses-01" / "func"
        func_dir.mkdir(parents=True)

        bold_path = func_dir / "sub-01_ses-01_task-rest_run-01_bold.nii.gz"
        mask_path = func_dir / "sub-01_ses-01_run-01_mask_brain.nii.gz"

        bold_path.touch()
        mask_path.touch()

        info = RunInfo(
            path=bold_path,
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        resolver = BIDSPathResolver()
        found_mask = resolver.find_mask(bold_path, info)

        assert found_mask == mask_path

    def test_find_mask_no_mask(self, tmp_path):
        """Test that None is returned when no mask found."""
        func_dir = tmp_path / "sub-01" / "ses-01" / "func"
        func_dir.mkdir(parents=True)

        bold_path = func_dir / "sub-01_ses-01_task-rest_run-01_bold.nii.gz"
        bold_path.touch()

        info = RunInfo(
            path=bold_path,
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        resolver = BIDSPathResolver()
        found_mask = resolver.find_mask(bold_path, info)

        assert found_mask is None

    def test_find_motion_params(self, tmp_path):
        """Test finding motion parameters."""
        # Create directory structure
        derivatives_dir = tmp_path / "derivatives"
        mc_dir = derivatives_dir / "sub-01" / "ses-01" / "mc"
        mc_dir.mkdir(parents=True)

        motion_file = mc_dir / "sub-01_ses-01_task-rest_run-01_echo-1_part-mag_bold_mc.nii.gz.par"
        motion_file.touch()

        info = RunInfo(
            path=Path("/data/sub-01_ses-01_task-rest_run-01_bold.nii.gz"),
            subject="01", session="01", run="01", task="rest",
            echo="1", part="mag", desc=None,
        )

        resolver = BIDSPathResolver(derivatives_dir)
        found_motion = resolver.find_motion_params(info, target_echo=1)

        assert found_motion == motion_file

    def test_find_motion_params_no_derivatives(self):
        """Test finding motion params when no derivatives dir."""
        info = RunInfo(
            path=Path("/data/bold.nii.gz"),
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        resolver = BIDSPathResolver(derivatives_dir=None)
        found_motion = resolver.find_motion_params(info, target_echo=1)

        assert found_motion is None


# ============================================================================
# Backward Compatibility Wrapper Tests
# ============================================================================


class TestBackwardCompatibilityWrappers:
    """Test backward compatibility wrapper functions."""

    def test_find_mask_path_wrapper(self, tmp_path):
        """Test find_mask_path wrapper."""
        func_dir = tmp_path / "sub-01" / "ses-01" / "func"
        func_dir.mkdir(parents=True)

        bold_path = func_dir / "sub-01_ses-01_task-rest_run-01_final.nii.gz"
        mask_path = func_dir / "sub-01_ses-01_task-rest_run-01_final_mask.nii.gz"

        bold_path.touch()
        mask_path.touch()

        info = RunInfo(
            path=bold_path,
            subject="01", session="01", run="01", task="rest",
            echo=None, part=None, desc=None,
        )

        found_mask = find_mask_path(bold_path, info)
        assert found_mask == mask_path

    def test_locate_motion_params_wrapper(self, tmp_path):
        """Test locate_motion_params wrapper."""
        derivatives_dir = tmp_path / "derivatives"
        mc_dir = derivatives_dir / "sub-01" / "ses-01" / "mc"
        mc_dir.mkdir(parents=True)

        motion_file = mc_dir / "sub-01_ses-01_task-rest_run-01_echo-1_part-mag_bold_mc.nii.gz.par"
        motion_file.touch()

        info = RunInfo(
            path=Path("/data/bold.nii.gz"),
            subject="01", session="01", run="01", task="rest",
            echo="1", part="mag", desc=None,
        )

        found_motion = locate_motion_params(derivatives_dir, info, target_echo=1)
        assert found_motion == motion_file
