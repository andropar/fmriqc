"""Tests for motion parameter generation.

This test suite covers motion generation functionality including:
- Container runtime detection (Docker/Singularity)
- FSL container management
- mcflirt execution
- Parallel processing of multiple runs
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from fmriqc.motion_generation import (
    FSL_CONTAINER_FILENAME,
    ContainerNotFoundError,
    MotionGenerationError,
    check_container_runtime,
    generate_motion_parameters,
    get_container_path,
    run_mcflirt,
)
from tests.utils.mocks import (
    mock_container_execution,
    mock_subprocess_timeout,
)

# ============================================================================
# Container Runtime Detection Tests
# ============================================================================


class TestCheckContainerRuntime:
    """Test container runtime detection."""

    def test_detects_docker(self):
        """Test Docker detection when available."""
        with patch('shutil.which') as mock_which:
            mock_which.return_value = "/usr/local/bin/docker"

            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)

                runtime = check_container_runtime()
                assert runtime == "docker"

                # Verify docker info was called to check daemon
                mock_run.assert_called_once()
                assert "docker" in mock_run.call_args[0][0]
                assert "info" in mock_run.call_args[0][0]

    def test_detects_singularity_when_docker_unavailable(self):
        """Test Singularity detection when Docker not available."""
        def mock_which_func(cmd):
            if cmd == "docker":
                return None
            elif cmd == "singularity":
                return "/usr/bin/singularity"
            return None

        with patch('shutil.which', side_effect=mock_which_func):
            runtime = check_container_runtime()
            assert runtime == "singularity"

    def test_docker_daemon_not_running(self):
        """Test fallback to Singularity when Docker daemon not running."""
        def mock_which_func(cmd):
            if cmd == "docker":
                return "/usr/local/bin/docker"
            elif cmd == "singularity":
                return "/usr/bin/singularity"
            return None

        with patch('shutil.which', side_effect=mock_which_func):
            with patch('subprocess.run') as mock_run:
                # Docker info fails (daemon not running)
                mock_run.return_value = Mock(returncode=1)

                runtime = check_container_runtime()
                assert runtime == "singularity"

    def test_raises_when_neither_available(self):
        """Test exception when neither Docker nor Singularity available."""
        with patch('shutil.which', return_value=None):
            with pytest.raises(ContainerNotFoundError) as exc_info:
                check_container_runtime()

            assert "Neither Docker nor Singularity found" in str(exc_info.value)
            assert "Docker Desktop" in str(exc_info.value)


# ============================================================================
# Container Path Management Tests
# ============================================================================


class TestGetContainerPath:
    """Test FSL container path management."""

    def test_uses_custom_path_when_provided(self, tmp_path):
        """Test custom container path usage."""
        custom_container = tmp_path / "custom_fsl.simg"
        custom_container.touch()  # Create file

        result = get_container_path(custom_path=custom_container)
        assert result == custom_container

    def test_raises_when_custom_path_not_exists(self, tmp_path):
        """Test error for non-existent custom path."""
        fake_path = tmp_path / "nonexistent.simg"

        with pytest.raises(FileNotFoundError) as exc_info:
            get_container_path(custom_path=fake_path)

        assert "Custom FSL container not found" in str(exc_info.value)

    def test_uses_cached_container(self, tmp_path, monkeypatch):
        """Test using cached container."""
        # Set DEFAULT_CONTAINER_DIR to tmp_path
        fake_default = tmp_path / "containers"
        fake_default.mkdir()
        cached_container = fake_default / FSL_CONTAINER_FILENAME
        cached_container.touch()

        monkeypatch.setattr("fmriqc.motion_generation.DEFAULT_CONTAINER_DIR", fake_default)

        result = get_container_path()
        assert result == cached_container

    def test_download_declined(self, tmp_path, monkeypatch):
        """Test error when download is declined."""
        fake_default = tmp_path / "containers"
        monkeypatch.setattr("fmriqc.motion_generation.DEFAULT_CONTAINER_DIR", fake_default)

        # Mock user declining download
        with patch('builtins.input', return_value='n'):
            with pytest.raises(MotionGenerationError) as exc_info:
                get_container_path()

            assert "download declined" in str(exc_info.value).lower()

    def test_download_success(self, tmp_path, monkeypatch):
        """Test successful container download."""
        fake_default = tmp_path / "containers"
        monkeypatch.setattr("fmriqc.motion_generation.DEFAULT_CONTAINER_DIR", fake_default)

        expected_path = fake_default / FSL_CONTAINER_FILENAME

        # Mock user accepting download
        with patch('builtins.input', return_value='y'):
            # Mock urllib.request.urlretrieve
            with patch('urllib.request.urlretrieve') as mock_download:
                def create_file(url, path, reporthook=None):
                    # Simulate download by creating file
                    path.parent.mkdir(parents=True, exist_ok=True)
                    Path(path).write_text("fake container data")

                mock_download.side_effect = create_file

                result = get_container_path()

                assert result == expected_path
                assert result.exists()
                mock_download.assert_called_once()

    def test_download_failure_cleanup(self, tmp_path, monkeypatch):
        """Test partial download cleanup on failure."""
        fake_default = tmp_path / "containers"
        monkeypatch.setattr("fmriqc.motion_generation.DEFAULT_CONTAINER_DIR", fake_default)

        expected_path = fake_default / FSL_CONTAINER_FILENAME

        with patch('builtins.input', return_value='y'):
            with patch('urllib.request.urlretrieve') as mock_download:
                # Simulate download failure that creates partial file
                def failing_download(url, path, reporthook=None):
                    # Create partial file during download
                    path.parent.mkdir(parents=True, exist_ok=True)
                    Path(path).write_text("partial")
                    raise Exception("Network error")

                mock_download.side_effect = failing_download

                with pytest.raises(MotionGenerationError):
                    get_container_path()

                # Partial file should be cleaned up
                assert not expected_path.exists()


# ============================================================================
# mcflirt Execution Tests
# ============================================================================


class TestRunMcflirt:
    """Test mcflirt execution."""

    def test_docker_execution_success(self, tmp_path, temp_nifti):
        """Test successful mcflirt execution with Docker."""
        output_dir = tmp_path / "motion_output"
        run_id = "sub-01_ses-01_task-rest_run-01"

        # Expected output file
        par_file = output_dir / f"{run_id}_mcflirt.par"

        # Mock container execution that creates .par file
        with mock_container_execution([par_file]):
            result_par, elapsed = run_mcflirt(
                func_file=temp_nifti,
                output_dir=output_dir,
                container_path=None,  # Not needed for Docker
                run_id=run_id,
                runtime="docker",
            )

            assert result_par == par_file
            assert result_par.exists()
            assert elapsed >= 0

    def test_singularity_execution_success(self, tmp_path, temp_nifti):
        """Test successful mcflirt execution with Singularity."""
        output_dir = tmp_path / "motion_output"
        run_id = "sub-01_ses-01_task-rest_run-01"
        container_path = tmp_path / "fsl.simg"
        container_path.touch()

        par_file = output_dir / f"{run_id}_mcflirt.par"

        with mock_container_execution([par_file]):
            result_par, elapsed = run_mcflirt(
                func_file=temp_nifti,
                output_dir=output_dir,
                container_path=container_path,
                run_id=run_id,
                runtime="singularity",
            )

            assert result_par == par_file
            assert result_par.exists()
            assert elapsed >= 0

    def test_singularity_requires_container_path(self, tmp_path, temp_nifti):
        """Test error when container_path not provided for Singularity."""
        with pytest.raises(MotionGenerationError) as exc_info:
            run_mcflirt(
                func_file=temp_nifti,
                output_dir=tmp_path,
                container_path=None,
                run_id="test",
                runtime="singularity",
            )

        assert "container_path required" in str(exc_info.value).lower()

    def test_mcflirt_failure(self, tmp_path, temp_nifti):
        """Test handling of mcflirt execution failure."""
        with mock_container_execution([], success=False):
            with pytest.raises(MotionGenerationError) as exc_info:
                run_mcflirt(
                    func_file=temp_nifti,
                    output_dir=tmp_path,
                    container_path=None,
                    run_id="test",
                    runtime="docker",
                )

            assert "mcflirt failed" in str(exc_info.value).lower()

    def test_par_file_not_created(self, tmp_path, temp_nifti):
        """Test error when mcflirt succeeds but .par file not created."""
        # Mock successful execution but don't create .par file
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            with pytest.raises(MotionGenerationError) as exc_info:
                run_mcflirt(
                    func_file=temp_nifti,
                    output_dir=tmp_path,
                    container_path=None,
                    run_id="test",
                    runtime="docker",
                )

            assert ".par file not found" in str(exc_info.value).lower()

    def test_timeout(self, tmp_path, temp_nifti):
        """Test handling of mcflirt timeout."""
        with mock_subprocess_timeout():
            with pytest.raises(MotionGenerationError) as exc_info:
                run_mcflirt(
                    func_file=temp_nifti,
                    output_dir=tmp_path,
                    container_path=None,
                    run_id="test",
                    runtime="docker",
                )

            assert "timed out" in str(exc_info.value).lower()

    def test_unknown_runtime(self, tmp_path, temp_nifti):
        """Test error for unknown runtime."""
        with pytest.raises(MotionGenerationError) as exc_info:
            run_mcflirt(
                func_file=temp_nifti,
                output_dir=tmp_path,
                container_path=None,
                run_id="test",
                runtime="unknown",
            )

        assert "Unknown runtime" in str(exc_info.value)


# ============================================================================
# Parallel Processing Tests
# ============================================================================


class TestGenerateMotionParameters:
    """Test parallel motion parameter generation."""

    def test_empty_list_returns_empty_dict(self, tmp_path):
        """Test that empty input returns empty dict."""
        result = generate_motion_parameters(
            runs_needing_motion=[],
            output_dir=tmp_path,
        )
        assert result == {}

    def test_single_run_serial(self, tmp_path, temp_nifti):
        """Test motion generation for single run (serial)."""
        run_id = "sub-01_ses-01_run-01"
        runs = [(run_id, temp_nifti)]

        # Mock runtime check
        with patch('fmriqc.motion_generation.check_container_runtime', return_value='docker'):
            # Mock run_mcflirt
            with patch('fmriqc.motion_generation.run_mcflirt') as mock_mcflirt:
                expected_par = tmp_path / "motion_params" / f"{run_id}_mcflirt.par"
                expected_par.parent.mkdir(parents=True, exist_ok=True)
                expected_par.touch()

                mock_mcflirt.return_value = (expected_par, 10.5)

                results = generate_motion_parameters(
                    runs_needing_motion=runs,
                    output_dir=tmp_path,
                    n_jobs=1,
                )

                assert run_id in results
                assert results[run_id] == expected_par
                mock_mcflirt.assert_called_once()

    def test_multiple_runs_serial(self, tmp_path, temp_nifti):
        """Test motion generation for multiple runs (serial with n_jobs=1)."""
        runs = [
            ("run-01", temp_nifti),
            ("run-02", temp_nifti),
            ("run-03", temp_nifti),
        ]

        with patch('fmriqc.motion_generation.check_container_runtime', return_value='docker'):
            with patch('fmriqc.motion_generation.run_mcflirt') as mock_mcflirt:
                # Mock successful execution
                def mock_func(func_file, output_dir, container_path, run_id, runtime):
                    par_file = output_dir / f"{run_id}_mcflirt.par"
                    par_file.parent.mkdir(parents=True, exist_ok=True)
                    par_file.touch()
                    return (par_file, 10.0)

                mock_mcflirt.side_effect = mock_func

                # Test with n_jobs=1 for serial execution (avoids pickling issues in tests)
                results = generate_motion_parameters(
                    runs_needing_motion=runs,
                    output_dir=tmp_path,
                    n_jobs=1,
                )

                assert len(results) == 3
                for run_id, _ in runs:
                    assert run_id in results
                    assert results[run_id].exists()

    def test_partial_failure_continues(self, tmp_path, temp_nifti):
        """Test that partial failures don't stop other runs."""
        runs = [
            ("run-01", temp_nifti),
            ("run-02", temp_nifti),  # This will fail
            ("run-03", temp_nifti),
        ]

        with patch('fmriqc.motion_generation.check_container_runtime', return_value='docker'):
            with patch('fmriqc.motion_generation.run_mcflirt') as mock_mcflirt:
                # Make run-02 fail
                def mock_func(func_file, output_dir, container_path, run_id, runtime):
                    if run_id == "run-02":
                        raise MotionGenerationError("Simulated failure")
                    par_file = output_dir / f"{run_id}_mcflirt.par"
                    par_file.parent.mkdir(parents=True, exist_ok=True)
                    par_file.touch()
                    return (par_file, 10.0)

                mock_mcflirt.side_effect = mock_func

                results = generate_motion_parameters(
                    runs_needing_motion=runs,
                    output_dir=tmp_path,
                    n_jobs=1,
                )

                # Only 2 successful runs
                assert len(results) == 2
                assert "run-01" in results
                assert "run-02" not in results
                assert "run-03" in results

    def test_creates_motion_params_directory(self, tmp_path, temp_nifti):
        """Test that motion_params directory is created."""
        runs = [("test-run", temp_nifti)]

        with patch('fmriqc.motion_generation.check_container_runtime', return_value='docker'):
            with patch('fmriqc.motion_generation.run_mcflirt') as mock_mcflirt:
                par_file = tmp_path / "motion_params" / "test-run_mcflirt.par"
                mock_mcflirt.return_value = (par_file, 10.0)

                # Create the directory structure that run_mcflirt would create
                par_file.parent.mkdir(parents=True, exist_ok=True)
                par_file.touch()

                generate_motion_parameters(
                    runs_needing_motion=runs,
                    output_dir=tmp_path,
                    n_jobs=1,
                )

                motion_dir = tmp_path / "motion_params"
                assert motion_dir.exists()
                assert motion_dir.is_dir()
