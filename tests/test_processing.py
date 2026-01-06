"""Tests for core QA processing pipeline.

This test suite covers the main processing orchestration including:
- Data loading and validation
- Spatial metrics computation
- Temporal metrics computation
- Quality assessment
- Results compilation
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from fmriqa.core.processing import (
    _compute_spatial_metrics,
    _compute_temporal_metrics,
    _compute_quality_flags,
    _create_run_directories,
    process_single_run,
)
from fmriqa.io.structures import RunInfo, RunResult
from fmriqa.orchestration.config import QAConfig


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestCreateRunDirectories:
    """Test run directory creation."""

    def test_create_directories(self, tmp_path, sample_run_info):
        """Test directory structure creation."""
        output_dir = tmp_path / "qa_output"

        run_dir = _create_run_directories(output_dir, sample_run_info)

        # Check directory structure
        assert run_dir.exists()
        assert run_dir.is_dir()
        # Should be: output_dir / sub-01 / ses-01 / sub-01_ses-01_run-01_task-rest
        assert "sub-01" in str(run_dir)
        assert "ses-01" in str(run_dir)
        assert "run-01" in str(run_dir)
        assert "task-rest" in str(run_dir)

    def test_idempotent_creation(self, tmp_path, sample_run_info):
        """Test that creating directories twice doesn't fail."""
        output_dir = tmp_path / "qa_output"

        run_dir1 = _create_run_directories(output_dir, sample_run_info)
        run_dir2 = _create_run_directories(output_dir, sample_run_info)

        assert run_dir1 == run_dir2
        assert run_dir1.exists()


class TestComputeSpatialMetrics:
    """Test spatial metrics computation."""

    def test_basic_spatial_metrics(self, synthetic_bold_data, brain_mask):
        """Test computation of basic spatial metrics."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T

        # Create minimal config
        config = Mock()
        config.get_threshold_dict.return_value = {
            "dvars_z": 2.5,
            "outlier": 0.02,
        }

        results = _compute_spatial_metrics(
            synthetic_bold_data,
            brain_mask,
            masked,
            config
        )

        # Check required keys
        assert "tsnr_median" in results
        assert "coverage" in results
        assert "dvars_std" in results
        assert "dvars_vstd" in results
        assert "dvars_percent" in results
        assert "outlier_fraction" in results
        assert "outlier_high" in results
        assert "maps" in results
        assert "voxel_count" in results

        # Check map types
        maps = results["maps"]
        assert "mean" in maps
        assert "std" in maps
        assert "tsnr" in maps
        assert "cov" in maps
        assert "dropout" in maps

    def test_tsnr_values(self, synthetic_bold_data, brain_mask):
        """Test tSNR computation produces reasonable values."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T

        config = Mock()
        config.get_threshold_dict.return_value = {"dvars_z": 2.5, "outlier": 0.02}

        results = _compute_spatial_metrics(
            synthetic_bold_data, brain_mask, masked, config
        )

        # tSNR should be positive
        assert results["tsnr_median"] > 0.0
        # Typical synthetic data should have reasonable tSNR
        assert 5.0 < results["tsnr_median"] < 50.0

    def test_coverage_calculation(self, synthetic_bold_data, brain_mask):
        """Test brain coverage calculation."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T

        config = Mock()
        config.get_threshold_dict.return_value = {"dvars_z": 2.5, "outlier": 0.02}

        results = _compute_spatial_metrics(
            synthetic_bold_data, brain_mask, masked, config
        )

        # Coverage should be between 0 and 1
        assert 0.0 <= results["coverage"] <= 1.0
        # For good synthetic data, coverage should be high
        assert results["coverage"] > 0.8


class TestComputeTemporalMetrics:
    """Test temporal metrics computation."""

    def test_basic_temporal_metrics(self, synthetic_bold_data, brain_mask):
        """Test computation of temporal metrics."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T
        mean_img = np.mean(synthetic_bold_data, axis=3)

        # Create mock NIfTI image
        data_img = Mock()
        data_img.header.get_zooms.return_value = (2.0, 2.0, 2.0, 2.0)  # TR = 2.0s
        data_img.ndim = 4

        results = _compute_temporal_metrics(
            masked, data_img, mean_img, synthetic_bold_data, brain_mask
        )

        # Check required keys
        assert "global_signal" in results
        assert "tr" in results
        assert "physio_metrics" in results
        assert "smoothness" in results
        assert "gcor" in results
        assert "ar1_median" in results
        assert "ar1_brain" in results

    def test_tr_extraction(self, synthetic_bold_data, brain_mask):
        """Test TR extraction from NIFTI header."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T
        mean_img = np.mean(synthetic_bold_data, axis=3)

        # Mock image with specific TR
        data_img = Mock()
        data_img.header.get_zooms.return_value = (3.0, 3.0, 3.0, 1.5)  # TR = 1.5s
        data_img.ndim = 4

        results = _compute_temporal_metrics(
            masked, data_img, mean_img, synthetic_bold_data, brain_mask
        )

        assert results["tr"] == 1.5

    def test_global_signal_shape(self, synthetic_bold_data, brain_mask):
        """Test global signal has correct shape."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T
        mean_img = np.mean(synthetic_bold_data, axis=3)

        data_img = Mock()
        data_img.header.get_zooms.return_value = (2.0, 2.0, 2.0, 2.0)
        data_img.ndim = 4

        results = _compute_temporal_metrics(
            masked, data_img, mean_img, synthetic_bold_data, brain_mask
        )

        # Global signal should have one value per timepoint
        assert len(results["global_signal"]) == synthetic_bold_data.shape[3]

    def test_gcor_range(self, synthetic_bold_data, brain_mask):
        """Test GCOR is in valid range."""
        masked = synthetic_bold_data[brain_mask].reshape(-1, synthetic_bold_data.shape[-1]).T
        mean_img = np.mean(synthetic_bold_data, axis=3)

        data_img = Mock()
        data_img.header.get_zooms.return_value = (2.0, 2.0, 2.0, 2.0)
        data_img.ndim = 4

        results = _compute_temporal_metrics(
            masked, data_img, mean_img, synthetic_bold_data, brain_mask
        )

        # GCOR should be between 0 and 1
        assert 0.0 <= results["gcor"] <= 1.0


class TestComputeQualityFlags:
    """Test quality flag computation."""

    def test_no_flags_for_good_data(self):
        """Test that good quality data has no flags."""
        metrics = {
            "tsnr_median": 40.0,  # Good
            "dvars_percent_above": 5.0,  # Low
            "outlier_percent_above": 3.0,  # Low
            "fd_percent_above": 5.0,  # Low
            "fd_median": 0.2,  # Low
            "physiological_power_ratio": 0.2,  # Acceptable
            "mask_components": 1,  # Single component
        }

        slice_qc = {
            "hyperintense_slices": np.array([False] * 10),
            "slice_outliers": np.array([0.05] * 10),
        }

        thresholds = {"fd": 0.5, "dvars_z": 2.5, "outlier": 0.02}

        flags = _compute_quality_flags(metrics, thresholds, slice_qc)

        # All flags should be False for good data
        assert not flags["tsnr_low"]
        assert not flags["dvars_high"]
        assert not flags["outliers_high"]
        assert not flags["motion_high"]
        assert not flags["hyperintense_slices"]
        assert not flags["slice_outliers"]
        assert not flags["mask_fragmented"]
        assert not flags["physiological_noise_high"]

    def test_tsnr_low_flag(self):
        """Test tSNR low flag."""
        metrics = {
            "tsnr_median": 20.0,  # Low!
            "dvars_percent_above": 5.0,
            "outlier_percent_above": 3.0,
            "fd_percent_above": 5.0,
            "fd_median": 0.2,
            "physiological_power_ratio": 0.2,
            "mask_components": 1,
        }

        slice_qc = {
            "hyperintense_slices": np.array([False] * 10),
            "slice_outliers": np.array([0.05] * 10),
        }

        thresholds = {"fd": 0.5, "dvars_z": 2.5, "outlier": 0.02}

        flags = _compute_quality_flags(metrics, thresholds, slice_qc)

        assert flags["tsnr_low"]

    def test_motion_high_flag(self):
        """Test motion high flag."""
        metrics = {
            "tsnr_median": 40.0,
            "dvars_percent_above": 5.0,
            "outlier_percent_above": 3.0,
            "fd_percent_above": 25.0,  # High!
            "fd_median": 0.6,  # High!
            "physiological_power_ratio": 0.2,
            "mask_components": 1,
        }

        slice_qc = {
            "hyperintense_slices": np.array([False] * 10),
            "slice_outliers": np.array([0.05] * 10),
        }

        thresholds = {"fd": 0.5, "dvars_z": 2.5, "outlier": 0.02}

        flags = _compute_quality_flags(metrics, thresholds, slice_qc)

        assert flags["motion_high"]

    def test_hyperintense_slices_flag(self):
        """Test hyperintense slices flag."""
        metrics = {
            "tsnr_median": 40.0,
            "dvars_percent_above": 5.0,
            "outlier_percent_above": 3.0,
            "fd_percent_above": 5.0,
            "fd_median": 0.2,
            "physiological_power_ratio": 0.2,
            "mask_components": 1,
        }

        # 5 hyperintense slices (> 3 threshold)
        hyperintense = np.array([True] * 5 + [False] * 5)
        slice_qc = {
            "hyperintense_slices": hyperintense,
            "slice_outliers": np.array([0.05] * 10),
        }

        thresholds = {"fd": 0.5, "dvars_z": 2.5, "outlier": 0.02}

        flags = _compute_quality_flags(metrics, thresholds, slice_qc)

        assert flags["hyperintense_slices"]


# ============================================================================
# Integration Tests (with mocking)
# ============================================================================


class TestProcessSingleRun:
    """Test the main processing function with mocking."""

    @patch('fmriqa.core.processing.create_run_info')
    @patch('fmriqa.core.processing.nib.load')
    @patch('fmriqa.core.processing.find_mask_path')
    @patch('fmriqa.core.processing.locate_motion_params')
    @patch('fmriqa.core.processing.persist_run_assets')
    @patch('fmriqa.core.processing.create_run_figure')
    @patch('fmriqa.core.processing.create_run_thumbnail')
    def test_successful_processing(
        self,
        mock_thumbnail,
        mock_figure,
        mock_persist,
        mock_locate_motion,
        mock_find_mask,
        mock_nib_load,
        mock_create_info,
        tmp_path,
        synthetic_bold_data,
        brain_mask,
        sample_run_info
    ):
        """Test successful processing of a run."""
        # Setup mocks
        run_path = tmp_path / "test_bold.nii.gz"
        run_path.touch()  # Create empty file for st_mtime

        # Mock create_run_info
        mock_create_info.return_value = sample_run_info

        # Mock nibabel load for BOLD data
        mock_bold_img = Mock()
        mock_bold_img.get_fdata.return_value = synthetic_bold_data
        mock_bold_img.affine = np.eye(4)
        mock_bold_img.ndim = 4
        # Setup header with proper get_zooms
        mock_header = Mock()
        mock_header.get_zooms.return_value = (2.0, 2.0, 2.0, 2.0)
        mock_bold_img.header = mock_header

        # Mock nibabel load for mask
        mock_mask_img = Mock()
        mock_mask_img.get_fdata.return_value = brain_mask.astype(np.uint8)
        mock_mask_img.affine = np.eye(4)
        mock_mask_img.shape = brain_mask.shape

        # Return BOLD first, then mask
        mock_nib_load.side_effect = [mock_bold_img, mock_mask_img]

        # Mock find_mask_path
        mock_find_mask.return_value = tmp_path / "mask.nii.gz"

        # Mock motion params (return None for now)
        mock_locate_motion.return_value = None

        # Mock visualization
        mock_figure.return_value = tmp_path / "figure.png"
        mock_thumbnail.return_value = tmp_path / "thumb.png"

        # Create config
        config = QAConfig()
        output_dir = tmp_path / "output"

        # Process
        result = process_single_run(run_path, config, output_dir)

        # Verify result
        assert result is not None
        assert isinstance(result, RunResult)
        assert result.info == sample_run_info

        # Check metrics exist
        assert "tsnr_median" in result.metrics
        assert "dvars_percent_above" in result.metrics
        assert "gcor" in result.metrics

        # Check series data
        assert "global_signal" in result.series
        assert "dvars_std" in result.series

        # Check maps
        assert "mean" in result.maps
        assert "tsnr" in result.maps
        assert "ar1" in result.maps

    @patch('fmriqa.core.processing.create_run_info')
    @patch('fmriqa.core.processing.nib.load')
    def test_handles_load_error(
        self,
        mock_nib_load,
        mock_create_info,
        tmp_path,
        sample_run_info
    ):
        """Test handling of data loading errors."""
        run_path = tmp_path / "test_bold.nii.gz"
        run_path.touch()

        mock_create_info.return_value = sample_run_info

        # Make nibabel.load raise an error
        mock_nib_load.side_effect = Exception("Failed to load NIFTI")

        config = QAConfig()
        output_dir = tmp_path / "output"

        # Process should return None on error
        result = process_single_run(run_path, config, output_dir)

        assert result is None

    @patch('fmriqa.core.processing.create_run_info')
    @patch('fmriqa.core.processing.nib.load')
    @patch('fmriqa.core.processing.find_mask_path')
    def test_handles_empty_mask(
        self,
        mock_find_mask,
        mock_nib_load,
        mock_create_info,
        tmp_path,
        synthetic_bold_data,
        sample_run_info
    ):
        """Test handling of empty brain mask."""
        run_path = tmp_path / "test_bold.nii.gz"
        run_path.touch()

        mock_create_info.return_value = sample_run_info

        # Mock BOLD data
        mock_bold_img = Mock()
        mock_bold_img.get_fdata.return_value = synthetic_bold_data

        # Mock empty mask
        empty_mask = np.zeros((10, 10, 10), dtype=bool)
        mock_mask_img = Mock()
        mock_mask_img.get_fdata.return_value = empty_mask
        mock_mask_img.affine = np.eye(4)
        mock_mask_img.shape = empty_mask.shape

        mock_nib_load.side_effect = [mock_bold_img, mock_mask_img]
        mock_find_mask.return_value = tmp_path / "mask.nii.gz"

        config = QAConfig()
        output_dir = tmp_path / "output"

        # Should return None for empty mask
        result = process_single_run(run_path, config, output_dir)

        assert result is None
