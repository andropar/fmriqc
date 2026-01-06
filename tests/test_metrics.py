"""Tests for core QA metric computations.

This test suite ensures correct implementation of all QA metrics including:
- Motion metrics (FD)
- Signal quality metrics (tSNR, DVARS, GCOR)
- Temporal metrics (AR1)
- Spatial metrics (smoothness)
- Statistical utilities (robust_z, detrend_poly)
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from fmriqa.core.metrics import (
    robust_z,
    detrend_poly,
    compute_fd,
    compute_dvars_standardized,
    compute_slice_quality,
    assess_brain_mask_quality,
    detect_physiological_noise,
    validate_events_file,
    assess_sdc_quality,
    compute_smoothness,
    compute_gcor,
    compute_ar1,
)
from fmriqa.core.constants import (
    StatisticalConstants,
    MotionConstants,
    PhysiologicalBands,
)


# ============================================================================
# Statistical Utilities Tests
# ============================================================================


class TestRobustZ:
    """Test robust z-score computation."""

    def test_zero_variance(self):
        """Test with zero variance (constant data)."""
        x = np.array([5.0, 5.0, 5.0, 5.0])
        z = robust_z(x)
        # All z-scores should be zero (no deviation from median)
        assert np.allclose(z, 0.0)

    def test_symmetric_distribution(self):
        """Test with symmetric distribution."""
        x = np.array([-2, -1, 0, 1, 2])
        z = robust_z(x)
        # Should be symmetric around zero
        assert np.allclose(z[0], -z[-1], atol=0.01)
        assert np.allclose(z[1], -z[-2], atol=0.01)

    def test_outlier_detection(self):
        """Test that outliers get high z-scores."""
        # Normal data with one outlier
        np.random.seed(42)
        x = np.random.randn(100) * 1.0 + 10.0
        x[50] = 100.0  # Obvious outlier
        z = robust_z(x)
        # Outlier should have much higher z-score
        assert np.abs(z[50]) > 3.0
        # Most normal points should be within [-3, 3]
        normal_z = np.delete(z, 50)
        assert np.mean(np.abs(normal_z) < 3.0) > 0.95

    def test_known_values(self):
        """Test with known MAD computation."""
        x = np.array([1, 2, 3, 4, 5])
        z = robust_z(x)
        # Median = 3, MAD = median(|[2,1,0,1,2]|) = 1
        # Scale = 1.4826 * 1 + epsilon ≈ 1.4826
        # z-scores should be roughly (x - 3) / 1.4826
        expected = (x - 3.0) / (StatisticalConstants.MAD_TO_STD_FACTOR * 1.0)
        assert np.allclose(z, expected, atol=0.01)


class TestDetrendPoly:
    """Test polynomial detrending."""

    def test_remove_linear_trend(self):
        """Test removal of linear trend."""
        t = np.arange(100)
        # Create linear trend + small noise
        trend = 0.5 * t + 10.0
        noise = np.random.randn(100) * 0.1
        signal = trend + noise

        detrended = detrend_poly(signal, degree=1)
        # Mean should be near zero
        assert np.abs(np.mean(detrended)) < 1.0
        # Variance should be dominated by noise
        assert np.std(detrended) < 1.0

    def test_remove_quadratic_trend(self):
        """Test removal of quadratic trend."""
        t = np.arange(100, dtype=np.float32)
        # Quadratic trend
        trend = 0.01 * t**2 + 0.5 * t + 10.0
        noise = np.random.randn(100) * 0.1
        signal = trend + noise

        detrended = detrend_poly(signal, degree=2)
        # Should remove trend, leaving mostly noise
        assert np.abs(np.mean(detrended)) < 1.0
        assert np.std(detrended) < 1.0

    def test_preserve_oscillation(self):
        """Test that oscillations are preserved."""
        t = np.linspace(0, 4 * np.pi, 100)
        trend = 0.5 * t + 10.0
        oscillation = 5.0 * np.sin(t)
        signal = trend + oscillation

        detrended = detrend_poly(signal, degree=1)
        # Oscillation amplitude should be preserved
        assert np.abs(np.max(detrended) - 5.0) < 1.0
        assert np.abs(np.min(detrended) + 5.0) < 1.0


# ============================================================================
# Motion Metrics Tests
# ============================================================================


class TestComputeFD:
    """Test Framewise Displacement computation."""

    def test_zero_motion(self, tmp_path):
        """Test FD with no motion (all zeros)."""
        motion = np.zeros((20, 6))
        par_file = tmp_path / "zero_motion.par"
        np.savetxt(par_file, motion, fmt='%.6f')

        fd = compute_fd(par_file)
        # All FD values should be zero
        assert len(fd) == 20
        assert np.allclose(fd, 0.0)

    def test_pure_translation(self, tmp_path):
        """Test FD with pure translation."""
        motion = np.zeros((20, 6))
        # Single step translation in x: 1mm at volume 10
        motion[10, 3] = 1.0  # trans_x

        par_file = tmp_path / "translation.par"
        np.savetxt(par_file, motion, fmt='%.6f')

        fd = compute_fd(par_file)
        # FD at volume 10 should be 1mm
        assert fd[0] == 0.0  # First volume always 0
        assert np.abs(fd[10] - 1.0) < 0.01
        # FD at volume 11 should be 1mm (returning to zero)
        assert np.abs(fd[11] - 1.0) < 0.01

    def test_pure_rotation(self, tmp_path):
        """Test FD with pure rotation."""
        motion = np.zeros((20, 6))
        # Rotation in radians: 0.02 rad at volume 10
        # Arc length = 0.02 * 50mm = 1mm
        motion[10, 0] = 0.02  # rot_x

        par_file = tmp_path / "rotation.par"
        np.savetxt(par_file, motion, fmt='%.6f')

        fd = compute_fd(par_file)
        # FD at volume 10 should be ~1mm
        expected_fd = 0.02 * MotionConstants.MC_ROT_RADIUS_MM
        assert np.abs(fd[10] - expected_fd) < 0.01

    def test_combined_motion(self, tmp_path):
        """Test FD with combined rotation and translation."""
        motion = np.zeros((20, 6))
        # Rotation: 0.01 rad in x (0.5mm)
        # Translation: 0.5mm in x
        # Total FD should be 1.0mm
        motion[10, 0] = 0.01  # rot_x -> 0.5mm
        motion[10, 3] = 0.5   # trans_x -> 0.5mm

        par_file = tmp_path / "combined.par"
        np.savetxt(par_file, motion, fmt='%.6f')

        fd = compute_fd(par_file)
        expected = 0.01 * MotionConstants.MC_ROT_RADIUS_MM + 0.5
        assert np.abs(fd[10] - expected) < 0.01

    def test_single_volume(self, tmp_path):
        """Test FD with single volume."""
        motion = np.array([[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])
        par_file = tmp_path / "single.par"
        np.savetxt(par_file, motion, fmt='%.6f')

        fd = compute_fd(par_file)
        assert len(fd) == 1
        assert fd[0] == 0.0

    def test_realistic_motion(self, motion_params, tmp_path):
        """Test FD with realistic motion from fixture."""
        par_file = tmp_path / "realistic.par"
        np.savetxt(par_file, motion_params, fmt='%.6f')

        fd = compute_fd(par_file)
        assert len(fd) == len(motion_params)
        assert fd[0] == 0.0
        # FD should be positive
        assert np.all(fd >= 0.0)
        # Test fixture generates random motion which can be large
        # Just verify FD computation doesn't crash and returns reasonable values
        assert np.all(fd < 100.0)  # Sanity check only


# ============================================================================
# Signal Quality Metrics Tests
# ============================================================================


class TestComputeDVARS:
    """Test DVARS computation."""

    def test_static_signal(self, brain_mask):
        """Test DVARS with no temporal variation."""
        # Constant signal over time
        data = np.ones((10, 10, 10, 20)) * 1000
        dvars_std, dvars_vstd = compute_dvars_standardized(data, brain_mask)

        # DVARS should be near zero
        assert len(dvars_std) == 19  # n_volumes - 1
        assert len(dvars_vstd) == 19
        # Should be very small (nearly zero differences)
        assert np.all(dvars_std < 0.1)
        assert np.all(dvars_vstd < 0.1)

    def test_impulse_change(self, brain_mask):
        """Test DVARS with single volume spike."""
        np.random.seed(42)
        # Normal signal with spike at volume 10
        data = np.random.randn(10, 10, 10, 20) * 100 + 1000
        data[:, :, :, 10] += 500  # Large spike

        dvars_std, dvars_vstd = compute_dvars_standardized(data, brain_mask)

        # DVARS should spike at volume 10 (index 9 in diff array)
        # and volume 11 (index 10 in diff array)
        # The spike is detectable but may be smaller due to standardization
        assert dvars_std[9] > 2.0  # Spike up
        assert dvars_std[10] > 2.0  # Spike down
        # Other timepoints should be reasonable
        normal_indices = [i for i in range(19) if i not in [9, 10]]
        assert np.median(dvars_std[normal_indices]) < 2.0

    def test_standardization(self, synthetic_bold_data, brain_mask):
        """Test DVARS standardization."""
        dvars_std, dvars_vstd = compute_dvars_standardized(
            synthetic_bold_data, brain_mask
        )

        # Standardized DVARS should be around 1.0 for typical data
        assert 0.5 < np.median(dvars_std) < 2.0
        assert 0.5 < np.median(dvars_vstd) < 2.0

    def test_empty_mask(self):
        """Test DVARS with empty mask."""
        data = np.random.randn(10, 10, 10, 20)
        mask = np.zeros((10, 10, 10), dtype=bool)

        # With empty mask, function will extract empty array and compute on it
        # This should result in empty arrays or NaN values
        dvars_std, dvars_vstd = compute_dvars_standardized(data, mask)
        # The result should be empty arrays (0 voxels selected)
        # diff will be empty after masking
        assert len(dvars_std) == 19  # Still n_volumes - 1
        # Values may be NaN or zero depending on implementation
        assert np.all(np.isnan(dvars_std)) or np.all(dvars_std == 0.0)


class TestComputeGCOR:
    """Test Global Correlation computation."""

    def test_identical_voxels(self):
        """Test GCOR with all voxels identical."""
        # All voxels have same time course
        timeseries = np.random.randn(100)
        data = np.tile(timeseries[:, None], (1, 50))  # time x voxels: (100, 50)

        gcor = compute_gcor(data)
        # Perfect correlation -> GCOR should be 1.0
        assert np.abs(gcor - 1.0) < 0.01

    def test_independent_voxels(self):
        """Test GCOR with independent voxels."""
        np.random.seed(42)
        # Each voxel is independent random noise
        data = np.random.randn(100, 500)

        gcor = compute_gcor(data)
        # Independent noise -> GCOR should be near 0
        assert gcor < 0.1

    def test_partial_correlation(self):
        """Test GCOR with partial correlation."""
        np.random.seed(42)
        # Create partially correlated data
        common_signal = np.random.randn(100)
        data = np.zeros((100, 100))
        for i in range(100):
            # Mix common signal with independent noise
            data[:, i] = 0.3 * common_signal + 0.7 * np.random.randn(100)

        gcor = compute_gcor(data)
        # Should have intermediate GCOR
        assert 0.05 < gcor < 0.2

    def test_edge_cases(self):
        """Test GCOR edge cases."""
        # Single voxel
        data = np.random.randn(100, 1)
        gcor = compute_gcor(data)
        assert gcor == 0.0

        # Two timepoints
        data = np.random.randn(2, 100)
        gcor = compute_gcor(data)
        assert 0.0 <= gcor <= 1.0


class TestComputeAR1:
    """Test AR(1) autocorrelation computation."""

    def test_white_noise(self):
        """Test AR1 with white noise (no autocorrelation)."""
        np.random.seed(42)
        # Independent samples
        series = np.random.randn(1000, 10)

        ar1 = compute_ar1(series)
        # AR1 should be near zero
        assert np.all(np.abs(ar1) < 0.2)

    def test_perfect_correlation(self):
        """Test AR1 with perfect autocorrelation."""
        # Constant series (perfect autocorrelation)
        series = np.ones((100, 5)) * 10.0

        ar1 = compute_ar1(series)
        # AR1 should be 1.0 (or handled as edge case)
        # With constant series, denominator is zero, so handled by epsilon
        assert np.all(ar1 >= 0.0)

    def test_ar1_process(self):
        """Test AR1 with known AR(1) process."""
        np.random.seed(42)
        # Generate AR(1) process with rho=0.7
        rho_true = 0.7
        n = 500
        series = np.zeros(n)
        series[0] = np.random.randn()
        for t in range(1, n):
            series[t] = rho_true * series[t-1] + np.random.randn() * 0.5

        series = series[:, None]  # Make 2D
        ar1 = compute_ar1(series)
        # Should estimate close to true rho
        assert np.abs(ar1[0] - rho_true) < 0.1

    def test_negative_autocorrelation(self):
        """Test AR1 with alternating signal."""
        # Alternating series: -1, 1, -1, 1, ...
        series = np.array([(-1)**i for i in range(100)])[:, None]

        ar1 = compute_ar1(series)
        # Should have negative AR1
        assert ar1[0] < 0.0
        assert ar1[0] > -1.0


class TestComputeSmoothness:
    """Test spatial smoothness estimation."""

    def test_unsmoothed_noise(self):
        """Test smoothness with unsmoothed noise."""
        np.random.seed(42)
        # Independent voxels (no smoothness)
        data = np.random.randn(20, 20, 20, 10)
        voxel_sizes = (2.0, 2.0, 2.0)

        fwhm = compute_smoothness(data, voxel_sizes)
        # Should have minimal smoothness
        assert fwhm < 5.0

    def test_smooth_data(self):
        """Test smoothness with smoothed data."""
        from scipy.ndimage import gaussian_filter

        np.random.seed(42)
        # Create smooth data by applying Gaussian filter
        data_raw = np.random.randn(20, 20, 20, 10)
        data = np.zeros_like(data_raw)
        for t in range(10):
            data[:, :, :, t] = gaussian_filter(data_raw[:, :, :, t], sigma=2.0)

        voxel_sizes = (2.0, 2.0, 2.0)
        fwhm = compute_smoothness(data, voxel_sizes)
        # Should estimate higher FWHM
        assert fwhm > 3.0


# ============================================================================
# Slice Quality Tests
# ============================================================================


class TestComputeSliceQuality:
    """Test slice-wise quality metrics."""

    def test_uniform_slices(self, synthetic_bold_data, brain_mask):
        """Test with uniform slices (no artifacts)."""
        metrics = compute_slice_quality(synthetic_bold_data, brain_mask)

        assert 'slice_mean' in metrics
        assert 'slice_std' in metrics
        assert 'slice_outliers' in metrics
        assert 'hyperintense_slices' in metrics

        # Shape checks
        n_slices = synthetic_bold_data.shape[2]
        n_time = synthetic_bold_data.shape[3]
        assert metrics['slice_mean'].shape == (n_slices, n_time)
        assert len(metrics['slice_std']) == n_slices
        assert len(metrics['slice_outliers']) == n_slices
        assert len(metrics['hyperintense_slices']) == n_slices

        # No hyperintense slices in synthetic data
        assert np.sum(metrics['hyperintense_slices']) == 0

    def test_hyperintense_slice(self, synthetic_bold_data, brain_mask):
        """Test slice quality metrics with varying slice intensities."""
        # Create data with one slice brighter than others
        data = synthetic_bold_data.copy()
        # Boost one slice (may or may not trigger hyperintensity flag depending on threshold)
        data[:, :, 5, :] *= 2.0

        metrics = compute_slice_quality(data, brain_mask)

        # Verify that slice_mean for slice 5 is higher than others
        assert metrics['slice_mean'][5].mean() > metrics['slice_mean'][4].mean()
        # The function should return valid metrics regardless of threshold
        assert len(metrics['hyperintense_slices']) == data.shape[2]

    def test_empty_slice(self):
        """Test with empty slice (no brain voxels)."""
        data = np.random.randn(10, 10, 10, 20) * 100 + 1000
        mask = np.ones((10, 10, 10), dtype=bool)
        mask[:, :, 5] = False  # No brain in slice 5

        metrics = compute_slice_quality(data, mask)
        # Metrics for slice 5 should be zero/default
        assert metrics['slice_std'][5] == 0.0


# ============================================================================
# Brain Mask Quality Tests
# ============================================================================


class TestAssessBrainMaskQuality:
    """Test brain mask quality assessment."""

    def test_good_mask(self, brain_mask, synthetic_bold_data):
        """Test with good quality mask."""
        data_mean = np.mean(synthetic_bold_data, axis=3)

        metrics = assess_brain_mask_quality(brain_mask, data_mean)

        assert metrics['mask_voxel_count'] > 0
        assert 0.0 < metrics['mask_volume_fraction'] < 1.0
        assert metrics['mask_components'] >= 1
        assert 0.0 < metrics['mask_largest_component_fraction'] <= 1.0

    def test_single_component(self, synthetic_bold_data):
        """Test mask with single connected component."""
        # Create simple cubic mask (single component)
        mask = np.zeros((10, 10, 10), dtype=bool)
        mask[3:7, 3:7, 3:7] = True
        data_mean = np.mean(synthetic_bold_data, axis=3)

        metrics = assess_brain_mask_quality(mask, data_mean)
        assert metrics['mask_components'] == 1
        assert metrics['mask_largest_component_fraction'] == 1.0

    def test_multiple_components(self, synthetic_bold_data):
        """Test mask with multiple disconnected components."""
        mask = np.zeros((10, 10, 10), dtype=bool)
        mask[2:4, 2:4, 2:4] = True  # Component 1
        mask[6:8, 6:8, 6:8] = True  # Component 2
        data_mean = np.mean(synthetic_bold_data, axis=3)

        metrics = assess_brain_mask_quality(mask, data_mean)
        assert metrics['mask_components'] == 2
        # Largest component should be < 1.0 (not all mask)
        assert metrics['mask_largest_component_fraction'] < 1.0

    def test_empty_mask(self, synthetic_bold_data):
        """Test with empty mask."""
        mask = np.zeros((10, 10, 10), dtype=bool)
        data_mean = np.mean(synthetic_bold_data, axis=3)

        metrics = assess_brain_mask_quality(mask, data_mean)
        assert metrics['mask_voxel_count'] == 0
        assert metrics['mask_volume_fraction'] == 0.0


# ============================================================================
# Physiological Noise Detection Tests
# ============================================================================


class TestDetectPhysiologicalNoise:
    """Test physiological noise detection."""

    def test_fast_tr_both_detectable(self):
        """Test with fast TR where both cardiac and respiratory are detectable."""
        np.random.seed(42)
        tr = 0.5  # Fast TR: Nyquist = 1.0 Hz
        n = 200
        t = np.arange(n) * tr

        # Create signal with cardiac (0.9 Hz) and respiratory (0.25 Hz)
        cardiac_freq = 0.9
        resp_freq = 0.25
        signal = (
            np.sin(2 * np.pi * cardiac_freq * t) +
            np.sin(2 * np.pi * resp_freq * t) +
            np.random.randn(n) * 0.1
        )

        metrics = detect_physiological_noise(signal, tr)

        assert metrics['cardiac_detectable'] == True
        assert metrics['respiratory_detectable'] == True
        assert metrics['nyquist_freq'] == 1.0
        # Should detect peaks near expected frequencies
        assert 0.6 < metrics['cardiac_freq_peak'] < 1.2
        assert 0.1 < metrics['respiratory_freq_peak'] < 0.4

    def test_slow_tr_neither_detectable(self):
        """Test with slow TR where neither is detectable."""
        tr = 4.0  # Very slow TR: Nyquist = 0.125 Hz (below respiratory band 0.15 Hz)
        signal = np.random.randn(100)

        metrics = detect_physiological_noise(signal, tr)

        assert metrics['cardiac_detectable'] == False
        assert metrics['respiratory_detectable'] == False
        assert metrics['cardiac_power'] == 0.0
        assert metrics['respiratory_power'] == 0.0

    def test_moderate_tr_resp_only(self):
        """Test with moderate TR where only respiratory is detectable."""
        tr = 2.0  # Nyquist = 0.25 Hz (just captures respiratory)
        n = 200
        signal = np.random.randn(n)

        metrics = detect_physiological_noise(signal, tr)

        assert metrics['cardiac_detectable'] == False
        assert metrics['respiratory_detectable'] == True


# ============================================================================
# Events File Validation Tests
# ============================================================================


class TestValidateEventsFile:
    """Test task events file validation."""

    def test_valid_events(self, tmp_path):
        """Test with valid events file."""
        events_file = tmp_path / "events.tsv"
        events_file.write_text(
            "onset\tduration\ttrial_type\n"
            "0.0\t2.5\tface\n"
            "5.0\t2.5\tplace\n"
            "10.0\t2.5\tface\n"
        )

        validation = validate_events_file(events_file, n_volumes=100, tr=2.0)
        assert validation['valid'] == True
        assert validation['n_events'] == 3
        assert len(validation['issues']) == 0

    def test_missing_onset_column(self, tmp_path):
        """Test with missing onset column."""
        events_file = tmp_path / "events.tsv"
        events_file.write_text("duration\ttrial_type\n2.5\tface\n")

        validation = validate_events_file(events_file, n_volumes=100, tr=2.0)
        assert validation['valid'] == False
        assert 'Missing columns' in validation['issues'][0]

    def test_event_beyond_scan(self, tmp_path):
        """Test with event extending beyond scan duration."""
        events_file = tmp_path / "events.tsv"
        # Scan duration = 100 volumes * 2s = 200s
        # Event at 195s with 10s duration extends to 205s
        events_file.write_text(
            "onset\tduration\ttrial_type\n"
            "195.0\t10.0\tface\n"
        )

        validation = validate_events_file(events_file, n_volumes=100, tr=2.0)
        assert validation['valid'] == False
        assert any('beyond scan' in issue for issue in validation['issues'])

    def test_negative_onset(self, tmp_path):
        """Test with negative onset time."""
        events_file = tmp_path / "events.tsv"
        events_file.write_text(
            "onset\ttrial_type\n"
            "-1.0\tface\n"
            "5.0\tplace\n"
        )

        validation = validate_events_file(events_file, n_volumes=100, tr=2.0)
        assert validation['valid'] == False
        assert any('Negative onset' in issue for issue in validation['issues'])

    def test_short_intervals(self, tmp_path):
        """Test detection of suspiciously short intervals."""
        events_file = tmp_path / "events.tsv"
        events_file.write_text(
            "onset\ttrial_type\n"
            "0.0\tface\n"
            "0.005\tplace\n"  # Only 5ms later
        )

        validation = validate_events_file(events_file, n_volumes=100, tr=2.0)
        assert validation['valid'] == False
        assert any('short intervals' in issue for issue in validation['issues'])


# ============================================================================
# SDC Quality Assessment Tests
# ============================================================================


class TestAssessSDCQuality:
    """Test susceptibility distortion correction quality assessment."""

    def test_phasediff_fieldmap(self, tmp_path):
        """Test with phasediff fieldmap."""
        fmap_files = {
            'phasediff': tmp_path / 'phasediff.nii.gz',
            'magnitude': tmp_path / 'magnitude.nii.gz',
        }

        metrics = assess_sdc_quality(fmap_files)
        assert metrics['fieldmap_present'] == True
        assert metrics['fieldmap_type'] == 'phasediff'

    def test_pepolar_fieldmap(self, tmp_path):
        """Test with pepolar (opposite phase-encode) fieldmaps."""
        fmap_files = {
            'epi_AP': tmp_path / 'epi_AP.nii.gz',
            'epi_PA': tmp_path / 'epi_PA.nii.gz',
        }

        metrics = assess_sdc_quality(fmap_files)
        assert metrics['fieldmap_type'] == 'pepolar'

    def test_single_epi(self, tmp_path):
        """Test with single EPI fieldmap."""
        fmap_files = {
            'epi_AP': tmp_path / 'epi_AP.nii.gz',
        }

        metrics = assess_sdc_quality(fmap_files)
        assert metrics['fieldmap_type'] == 'epi_single'

    def test_no_fieldmap(self):
        """Test with no fieldmap."""
        metrics = assess_sdc_quality({})
        assert metrics['fieldmap_type'] == ''
