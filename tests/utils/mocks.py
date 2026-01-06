"""Mocking utilities for fmriqa tests."""

from unittest.mock import Mock, patch, MagicMock
import subprocess
from pathlib import Path
from typing import List, Optional
import numpy as np


def mock_docker_available():
    """Mock Docker availability check.

    Usage:
        with mock_docker_available():
            # Test code that checks for Docker
    """
    def mock_which(cmd):
        if cmd == "docker":
            return "/usr/local/bin/docker"
        return None

    def mock_run(*args, **kwargs):
        # Mock `docker info` command
        if args[0][0] == "docker" and args[0][1] == "info":
            return Mock(returncode=0, stdout=b"Docker info", stderr=b"")
        return Mock(returncode=0)

    return patch.multiple(
        'shutil',
        which=mock_which,
    ), patch('subprocess.run', side_effect=mock_run)


def mock_singularity_available():
    """Mock Singularity availability check.

    Usage:
        with mock_singularity_available():
            # Test code that checks for Singularity
    """
    def mock_which(cmd):
        if cmd == "singularity":
            return "/usr/bin/singularity"
        return None

    return patch('shutil.which', side_effect=mock_which)


def mock_container_execution(output_files: List[Path], success: bool = True):
    """Mock container execution that creates expected output files.

    Args:
        output_files: List of paths to create as mock outputs
        success: Whether execution should succeed

    Usage:
        par_file = tmp_path / "motion.par"
        with mock_container_execution([par_file]):
            # Test code that runs containers
    """
    def side_effect(*args, **kwargs):
        if success:
            # Create mock output files
            for filepath in output_files:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                if filepath.suffix == '.par':
                    # Create mock motion parameters
                    mock_params = np.random.randn(20, 6) * 0.1
                    np.savetxt(filepath, mock_params, fmt='%.6f')
                else:
                    filepath.write_text("# Mock output\n")
            return Mock(returncode=0, stdout=b"Success", stderr=b"")
        else:
            return Mock(returncode=1, stdout=b"", stderr=b"Error")

    return patch('subprocess.run', side_effect=side_effect)


def mock_subprocess_timeout():
    """Mock subprocess timeout exception.

    Usage:
        with mock_subprocess_timeout():
            # Test code that should timeout
    """
    def side_effect(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get('timeout', 300))

    return patch('subprocess.run', side_effect=side_effect)


def mock_file_not_found(filepath: Path):
    """Mock file not found scenario.

    Args:
        filepath: Path that should not exist

    Usage:
        with mock_file_not_found(Path("/nonexistent/file")):
            # Test code
    """
    original_exists = Path.exists

    def mock_exists(self):
        if self == filepath:
            return False
        return original_exists(self)

    return patch.object(Path, 'exists', mock_exists)


def mock_nibabel_load(data: Optional[np.ndarray] = None, affine: Optional[np.ndarray] = None):
    """Mock nibabel.load() for NIFTI files.

    Args:
        data: 3D/4D numpy array to return
        affine: Affine matrix (default: identity)

    Usage:
        data = np.random.randn(10, 10, 10, 20)
        with mock_nibabel_load(data):
            # Test code that loads NIFTI files
    """
    if data is None:
        data = np.random.randn(10, 10, 10, 20)
    if affine is None:
        affine = np.eye(4)

    mock_img = MagicMock()
    mock_img.get_fdata.return_value = data
    mock_img.affine = affine
    mock_img.shape = data.shape

    return patch('nibabel.load', return_value=mock_img)


def mock_config(overrides: Optional[dict] = None):
    """Mock QAConfig with optional overrides.

    Args:
        overrides: Dict of config values to override

    Returns:
        Mock QAConfig object
    """
    from fmriqa.orchestration.config import QAConfig, PathConfig, ProcessingConfig, ThresholdConfig

    config = QAConfig()

    if overrides:
        for key, value in overrides.items():
            setattr(config, key, value)

    return config


class MockProcessPoolExecutor:
    """Mock ProcessPoolExecutor for testing parallel processing without actually parallelizing."""

    def __init__(self, max_workers=None):
        self.max_workers = max_workers

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def map(self, func, *iterables, timeout=None, chunksize=1):
        """Execute function sequentially instead of in parallel."""
        return map(func, *iterables)

    def submit(self, func, *args, **kwargs):
        """Execute function immediately and return a completed future."""
        from concurrent.futures import Future
        future = Future()
        try:
            result = func(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future


def mock_parallel_execution():
    """Mock parallel processing to run sequentially for testing.

    Usage:
        with mock_parallel_execution():
            # Test code that uses ProcessPoolExecutor
    """
    return patch('concurrent.futures.ProcessPoolExecutor', MockProcessPoolExecutor)
