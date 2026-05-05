"""Pytest configuration and fixtures for fmriqc tests."""


import nibabel as nib
import numpy as np
import pytest

from fmriqc.io.structures import RunInfo


@pytest.fixture
def synthetic_bold_data():
    """Generate synthetic 4D fMRI data.

    Returns:
        np.ndarray: 4D array of shape (10, 10, 10, 20)
    """
    # 10x10x10 spatial, 20 timepoints
    # Mean signal ~1000, std ~100
    np.random.seed(42)  # Reproducible tests
    data = np.random.randn(10, 10, 10, 20) * 100 + 1000
    return data


@pytest.fixture
def brain_mask():
    """Generate synthetic brain mask.

    Returns:
        np.ndarray: 3D boolean array of shape (10, 10, 10)
    """
    mask = np.ones((10, 10, 10), dtype=bool)
    # Exclude edges to simulate realistic brain mask
    mask[0:2, :, :] = False
    mask[:, 0:2, :] = False
    mask[:, :, 0:2] = False
    mask[-2:, :, :] = False
    mask[:, -2:, :] = False
    mask[:, :, -2:] = False
    return mask


@pytest.fixture
def motion_params():
    """Generate synthetic motion parameters.

    Returns:
        np.ndarray: 2D array of shape (20, 6) - 20 timepoints, 6 motion parameters
    """
    np.random.seed(42)
    # Generate realistic small motion: 3 translations (mm), 3 rotations (radians)
    params = np.random.randn(20, 6) * 0.1
    return params


@pytest.fixture
def temp_nifti(tmp_path, synthetic_bold_data):
    """Create temporary NIFTI file.

    Args:
        tmp_path: pytest tmp_path fixture
        synthetic_bold_data: Fixture providing 4D fMRI data

    Returns:
        Path: Path to temporary NIFTI file
    """
    filepath = tmp_path / "test_bold.nii.gz"
    affine = np.eye(4)  # Identity affine
    img = nib.Nifti1Image(synthetic_bold_data, affine)
    nib.save(img, filepath)
    return filepath


@pytest.fixture
def temp_mask(tmp_path, brain_mask):
    """Create temporary brain mask NIFTI file.

    Args:
        tmp_path: pytest tmp_path fixture
        brain_mask: Fixture providing 3D mask data

    Returns:
        Path: Path to temporary mask NIFTI file
    """
    filepath = tmp_path / "test_mask.nii.gz"
    affine = np.eye(4)
    img = nib.Nifti1Image(brain_mask.astype(np.uint8), affine)
    nib.save(img, filepath)
    return filepath


@pytest.fixture
def temp_motion_file(tmp_path, motion_params):
    """Create temporary motion parameter file (.par format).

    Args:
        tmp_path: pytest tmp_path fixture
        motion_params: Fixture providing motion parameters

    Returns:
        Path: Path to temporary .par file
    """
    filepath = tmp_path / "test_motion.par"
    # FSL format: 6 columns (rotations then translations)
    np.savetxt(filepath, motion_params, fmt='%.6f')
    return filepath


@pytest.fixture
def sample_run_info(temp_nifti):
    """Create sample RunInfo structure.

    Args:
        temp_nifti: Temporary BOLD NIFTI file

    Returns:
        RunInfo: Complete RunInfo object for testing
    """
    return RunInfo(
        path=temp_nifti,
        subject="01",
        session="01",
        run="01",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )


@pytest.fixture
def sample_run_info_no_motion(temp_nifti):
    """Create sample RunInfo without motion parameters.

    Useful for testing motion generation.

    Returns:
        RunInfo: RunInfo object
    """
    return RunInfo(
        path=temp_nifti,
        subject="01",
        session="01",
        run="01",
        task="rest",
        echo=None,
        part=None,
        desc=None,
    )


@pytest.fixture
def known_fd_values():
    """Provide known FD values for validation.

    Calculated manually for specific motion parameter patterns.

    Returns:
        dict: Known FD values for different scenarios
    """
    return {
        'zero_motion': 0.0,
        'small_motion': 0.1,  # ~0.1mm translation
        'large_motion': 1.0,  # ~1mm translation
    }


@pytest.fixture
def known_tsnr_values():
    """Provide known tSNR values for validation.

    Returns:
        dict: Expected tSNR ranges for different SNR levels
    """
    return {
        'low_snr': (5.0, 15.0),    # Poor quality
        'medium_snr': (30.0, 50.0),  # Acceptable
        'high_snr': (60.0, 100.0),   # Good quality
    }
