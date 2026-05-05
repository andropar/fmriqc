"""Motion parameter generation using FSL mcflirt via Neurodesk containers.

This module provides functionality to generate motion parameters for fMRI data
when they are not available from preprocessing pipelines. It uses FSL's mcflirt
tool running in either Docker or Singularity containers from the Neurodesk project.

Supports:
    - Docker (preferred on macOS - uses Rosetta 2 for x86_64 on Apple Silicon)
    - Singularity/Apptainer (for HPC environments)

References:
    - Neurodesk: https://www.neurodesk.org/
    - FSL MCFLIRT: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/MCFLIRT
"""

import shutil
import subprocess
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

# FSL container from Neurodesk
FSL_DOCKER_IMAGE = "vnmd/fsl_6.0.5.1:20221016"
FSL_CONTAINER_URL = "https://neurocontainers.neurodesk.org/fsl_6.0.5.1_20221016.simg"
FSL_CONTAINER_FILENAME = "fsl_6.0.5.1_20221016.simg"
DEFAULT_CONTAINER_DIR = Path.home() / ".fmriqc" / "containers"


class MotionGenerationError(Exception):
    """Exception raised when motion generation fails."""
    pass


class ContainerNotFoundError(Exception):
    """Exception raised when neither Docker nor Singularity is available."""
    pass


def check_container_runtime() -> str:
    """Check which container runtime is available.

    Prefers Docker on macOS (Rosetta 2 support), falls back to Singularity for HPC.

    Returns:
        str: "docker" or "singularity"

    Raises:
        ContainerNotFoundError: If neither runtime is found.
    """
    # Check for Docker first (preferred on macOS)
    if shutil.which("docker"):
        # Verify Docker daemon is running
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return "docker"
        except (subprocess.TimeoutExpired, Exception):
            pass

    # Fall back to Singularity
    if shutil.which("singularity"):
        return "singularity"

    # Neither found
    raise ContainerNotFoundError(
        "Neither Docker nor Singularity found for --generate-motion.\n"
        "\n"
        "Docker (recommended for macOS):\n"
        "  Install Docker Desktop: https://www.docker.com/products/docker-desktop/\n"
        "\n"
        "Singularity/Apptainer (for HPC):\n"
        "  Linux: https://docs.sylabs.io/guides/latest/user-guide/quick_start.html\n"
        "  HPC: Contact your system administrator\n"
        "\n"
        "Or, obtain motion parameters separately and provide via manifest."
    )


def get_container_path(custom_path: Optional[Path] = None) -> Path:
    """Get path to FSL container, downloading if necessary.

    Args:
        custom_path: Optional custom path to FSL container. If provided,
            skips auto-download and uses this path.

    Returns:
        Path to FSL container.

    Raises:
        FileNotFoundError: If custom_path is specified but doesn't exist.
    """
    # If custom path provided, validate and return it
    if custom_path is not None:
        if not custom_path.exists():
            raise FileNotFoundError(
                f"Custom FSL container not found: {custom_path}\n"
                f"Please check the path or omit --fsl-container to auto-download."
            )
        print(f"Using custom FSL container: {custom_path}")
        return custom_path

    # Check default location
    container_path = DEFAULT_CONTAINER_DIR / FSL_CONTAINER_FILENAME

    if container_path.exists():
        print(f"Using cached FSL container: {container_path}")
        return container_path

    # Need to download - ask for permission
    print("\n" + "=" * 70)
    print("FSL Container Download Required")
    print("=" * 70)
    print("\nMotion correction requires downloading:")
    print("  - FSL 6.0.5.1 Singularity container")
    print("  - Size: ~1.2 GB")
    print("  - From: neurocontainers.neurodesk.org")
    print(f"  - Will be cached at: {container_path}")
    print("\nThis is a one-time download. Future runs will use the cached container.")
    print("=" * 70)

    response = input("\nDownload now? [y/N]: ").strip().lower()

    if response not in ['y', 'yes']:
        raise MotionGenerationError(
            "FSL container download declined. Cannot proceed with --generate-motion.\n"
            "To skip this prompt, download the container manually and use --fsl-container."
        )

    # Download container
    print("\nDownloading FSL container...")
    print(f"URL: {FSL_CONTAINER_URL}")
    print(f"Destination: {container_path}")

    # Create directory if needed
    container_path.parent.mkdir(parents=True, exist_ok=True)

    # Download with progress
    try:
        def _progress_hook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if total_size > 0:
                percent = min(100, downloaded * 100 / total_size)
                mb_downloaded = downloaded / (1024 * 1024)
                mb_total = total_size / (1024 * 1024)
                print(f"\rProgress: {percent:.1f}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)", end="")

        urllib.request.urlretrieve(
            FSL_CONTAINER_URL,
            container_path,
            reporthook=_progress_hook
        )
        print("\n✓ Download complete!")

    except Exception as e:
        # Clean up partial download
        if container_path.exists():
            container_path.unlink()
        raise MotionGenerationError(f"Failed to download FSL container: {e}") from e

    return container_path


def run_mcflirt(
    func_file: Path,
    output_dir: Path,
    container_path: Optional[Path],
    run_id: str,
    runtime: str = "docker",
) -> Tuple[Path, float]:
    """Run FSL mcflirt on a single functional file.

    Args:
        func_file: Path to input functional NIfTI file.
        output_dir: Directory to save motion parameters.
        container_path: Path to FSL Singularity container (only for Singularity runtime).
        run_id: Run identifier for output filename.
        runtime: Container runtime to use ("docker" or "singularity").

    Returns:
        Tuple of (par_file_path, execution_time_seconds).

    Raises:
        MotionGenerationError: If mcflirt execution fails.
    """
    import platform
    import time

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output basename (mcflirt will add .par extension)
    output_basename = output_dir / f"{run_id}_mcflirt"
    par_file = output_dir / f"{run_id}_mcflirt.par"

    # Build command based on runtime
    func_parent = func_file.parent.resolve()
    output_parent = output_dir.resolve()

    if runtime == "docker":
        # Docker command with proper volume mounts
        # Docker Desktop on Apple Silicon uses Rosetta 2 for transparent x86_64 emulation
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{func_parent}:{func_parent}",
            "-v", f"{output_parent}:{output_parent}",
            "--platform", "linux/amd64",  # Force x86_64 platform (uses Rosetta 2 on ARM64)
            FSL_DOCKER_IMAGE,
            "mcflirt",
            "-in", str(func_file.resolve()),
            "-o", str(output_basename.resolve()),
            "-plots",  # Generate motion plots and .par file
        ]
        timeout = 900  # 15 minutes (Rosetta 2 is fast but fMRI data can be large)

    elif runtime == "singularity":
        # Singularity command with bind mounts
        if container_path is None:
            raise MotionGenerationError("container_path required for Singularity runtime")

        cmd = ["singularity", "exec"]

        # On ARM64 systems, add --unsquash to bypass architecture check
        # QEMU user-mode emulation will handle x86_64 binaries (much slower!)
        if platform.machine() in ("arm64", "aarch64"):
            cmd.append("--unsquash")
            timeout = 3600  # 1 hour for QEMU emulation
            print("  Note: Running on ARM64 with QEMU emulation - this may take 10-30 minutes per run")
        else:
            timeout = 300  # 5 minutes for native execution

        cmd.extend([
            "-B", f"{func_parent}:{func_parent}",
            "-B", f"{output_parent}:{output_parent}",
            str(container_path),
            "mcflirt",
            "-in", str(func_file.resolve()),
            "-o", str(output_basename.resolve()),
            "-plots",
        ])

    else:
        raise MotionGenerationError(f"Unknown runtime: {runtime}")

    # Run mcflirt
    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise MotionGenerationError(
                f"mcflirt failed with exit code {result.returncode}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Check that .par file was created
        if not par_file.exists():
            raise MotionGenerationError(
                f"mcflirt completed but .par file not found: {par_file}"
            )

        elapsed = time.time() - start_time

        return par_file, elapsed

    except subprocess.TimeoutExpired as e:
        raise MotionGenerationError(f"mcflirt timed out after {timeout} seconds") from e
    except Exception as e:
        raise MotionGenerationError(f"mcflirt execution failed: {e}") from e


def generate_motion_parameters(
    runs_needing_motion: List[Tuple[str, Path]],
    output_dir: Path,
    container_path: Optional[Path] = None,
    n_jobs: int = 1,
) -> dict:
    """Generate motion parameters for multiple runs in parallel.

    Args:
        runs_needing_motion: List of (run_id, func_file_path) tuples.
        output_dir: Directory to save motion parameters.
        container_path: Path to FSL Singularity container (only for Singularity runtime).
        n_jobs: Number of parallel jobs.

    Returns:
        Dictionary mapping run_id to par_file_path for successful runs.
    """
    if not runs_needing_motion:
        return {}

    # Detect container runtime
    runtime = check_container_runtime()
    print(f"\n{'=' * 70}")
    print(f"Generating motion parameters for {len(runs_needing_motion)} runs")
    print(f"Using {n_jobs} parallel jobs")
    print(f"Container runtime: {runtime}")
    if runtime == "docker":
        print(f"Docker image: {FSL_DOCKER_IMAGE}")
    elif runtime == "singularity" and container_path:
        print(f"Singularity container: {container_path}")
    print(f"{'=' * 70}\n")

    results = {}
    failed = []

    # Create motion_params subdirectory
    motion_dir = output_dir / "motion_params"
    motion_dir.mkdir(parents=True, exist_ok=True)

    if n_jobs == 1:
        # Serial execution
        for i, (run_id, func_file) in enumerate(runs_needing_motion, 1):
            print(f"[{i}/{len(runs_needing_motion)}] {run_id}: Running mcflirt...")
            try:
                par_file, elapsed = run_mcflirt(
                    func_file, motion_dir, container_path, run_id, runtime
                )
                results[run_id] = par_file
                print(f"  ✓ Complete ({elapsed:.1f}s)")
            except MotionGenerationError as e:
                failed.append((run_id, str(e)))
                print(f"  ✗ Failed: {e}")
    else:
        # Parallel execution
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            # Submit all jobs
            futures = {}
            for run_id, func_file in runs_needing_motion:
                future = executor.submit(
                    run_mcflirt, func_file, motion_dir, container_path, run_id, runtime
                )
                futures[future] = (run_id, func_file)

            # Process results as they complete
            completed = 0
            total = len(futures)

            for future in as_completed(futures):
                run_id, func_file = futures[future]
                completed += 1

                try:
                    par_file, elapsed = future.result()
                    results[run_id] = par_file
                    print(f"[{completed}/{total}] {run_id}: Complete ({elapsed:.1f}s)")
                except MotionGenerationError as e:
                    failed.append((run_id, str(e)))
                    print(f"[{completed}/{total}] {run_id}: Failed - {e}")

    # Summary
    print(f"\n{'=' * 70}")
    print("Motion generation complete")
    print(f"  Successful: {len(results)}/{len(runs_needing_motion)}")
    if failed:
        print(f"  Failed: {len(failed)}")
        print("\nFailed runs:")
        for run_id, error in failed:
            print(f"  - {run_id}: {error}")
    print(f"{'=' * 70}\n")

    return results
