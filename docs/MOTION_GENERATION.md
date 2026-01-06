# Motion Parameter Generation

fmriqa can automatically generate motion parameters using FSL's mcflirt tool when they are not available from your preprocessing pipeline. This feature uses containerized FSL via Docker (macOS/Windows) or Singularity/Apptainer (HPC environments).

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Platform-Specific Setup](#platform-specific-setup)
- [Usage Examples](#usage-examples)
- [Performance Considerations](#performance-considerations)
- [Troubleshooting](#troubleshooting)

## Overview

Motion parameters (6-parameter rigid body transformation) are essential for computing framewise displacement (FD) and other motion-related metrics. If your preprocessing pipeline doesn't output motion parameters, fmriqa can generate them using:

- **FSL mcflirt** - Motion correction tool from FSL neuroimaging suite
- **Neurodesk containers** - Pre-built container images (vnmd/fsl_6.0.5.1:20221016)
- **Docker or Singularity** - Container runtimes for cross-platform support

### What Gets Generated

For each run, fmriqa generates:
- `.par` file - 6-parameter motion correction file (required for FD computation)
- `.nii.gz` file - Motion-corrected BOLD volume (optional output)

The `.par` file contains one row per timepoint with 6 columns:
```
rotation_x  rotation_y  rotation_z  translation_x  translation_y  translation_z
```

## Requirements

### Docker (Recommended for macOS/Windows)

**macOS:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.0+
- On Apple Silicon (M1/M2/M3): Rosetta 2 provides fast x86_64 emulation
- Docker Desktop handles image pulling automatically

**Windows:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with WSL 2 backend
- Sufficient disk space (~1.5 GB for FSL image)

### Singularity/Apptainer (For HPC/Linux)

**Linux (root access):**
```bash
# Ubuntu/Debian
sudo apt-get install -y apptainer

# RHEL/CentOS
sudo yum install -y apptainer
```

**HPC (no root access):**
Contact your system administrator. Most HPC systems have Singularity/Apptainer available via module system:
```bash
module load singularity
# or
module load apptainer
```

## Quick Start

### 1. Enable motion generation

Add to your manifest file:
```yaml
subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "path/to/bold.nii.gz"
            mask: "path/to/mask.nii.gz"  # optional
            # motion: omitted - will be generated
            run: "run-01"

qa_config:
  processing:
    generate_motion: true
    n_jobs: 2  # Parallel motion generation
```

### 2. Run QA

```bash
fmriqa --manifest manifest.yaml
```

The pipeline will:
1. Detect available container runtime (Docker or Singularity)
2. Download FSL container if needed (one-time, ~1.2 GB for Singularity; auto-pulled by Docker)
3. Generate motion parameters for runs that don't have them
4. Compute QA metrics including FD from generated parameters

## Platform-Specific Setup

### macOS (Apple Silicon - M1/M2/M3)

**Recommended: Docker Desktop**

1. Install Docker Desktop:
   ```bash
   # Download from https://www.docker.com/products/docker-desktop/
   # or install via Homebrew
   brew install --cask docker
   ```

2. Start Docker Desktop (first time only)

3. Run fmriqa with `--generate-motion`:
   ```bash
   fmriqa --manifest manifest.yaml --generate-motion --n-jobs 2
   ```

**Performance:** Docker Desktop uses Rosetta 2 for transparent x86_64 emulation:
- **~12 minutes per run** for typical 4D fMRI data
- Parallel processing with `--n-jobs 2` processes 2 runs simultaneously
- Example: 6 runs take ~36 minutes instead of 72 minutes

### macOS (Intel)

Same as Apple Silicon, but slightly faster since no emulation is needed (~8-10 minutes per run).

### Linux

**Option 1: Docker (if you have docker installed)**
```bash
sudo apt-get install docker.io
sudo usermod -aG docker $USER  # Log out and back in
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 4
```

**Option 2: Singularity/Apptainer (preferred for HPC)**
```bash
# Install (requires root)
sudo apt-get install -y apptainer

# Run
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 4
```

**Performance:** Native x86_64 execution, ~5-8 minutes per run.

### HPC Clusters

Most HPC systems use Singularity/Apptainer:

```bash
#!/bin/bash
#SBATCH --job-name=fmriqa
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=4:00:00

module load singularity  # or: module load apptainer

fmriqa --manifest manifest.yaml \
    --generate-motion \
    --n-jobs 8
```

**First-time setup:**
The FSL container (~1.2 GB) will be downloaded to `~/.fmriqa/containers/` and reused for future runs.

**Custom container location:**
```bash
fmriqa --manifest manifest.yaml \
    --generate-motion \
    --fsl-container /path/to/fsl_container.simg
```

## Usage Examples

### Example 1: Basic Usage

```bash
fmriqa --manifest manifest.yaml --generate-motion
```

Generates motion parameters for all runs without motion files.

### Example 2: Parallel Processing

```bash
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 4
```

Process 4 runs in parallel (4 Docker containers or Singularity processes running simultaneously).

### Example 3: Mixed - Some Runs Have Motion

```yaml
subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "run1.nii.gz"
            motion: "run1_motion.par"  # Already have motion
            run: "run-01"
          - bold: "run2.nii.gz"
            # motion: omitted - will be generated
            run: "run-02"
          - bold: "run3.nii.gz"
            motion: "run3_motion.par"  # Already have motion
            run: "run-03"
```

Only `run-02` will have motion parameters generated. Existing motion files are used as-is.

### Example 4: Custom FSL Container

```bash
fmriqa --manifest manifest.yaml \
    --generate-motion \
    --fsl-container /shared/containers/fsl_6.0.5.1.simg
```

Skip auto-download and use a specific FSL container.

### Example 5: Embedded Config in Manifest

```yaml
subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "bold.nii.gz"
            run: "run-01"

qa_config:
  processing:
    generate_motion: true
    n_jobs: 2
  thresholds:
    fd_threshold: 0.5
  reporting:
    generate_reports: true
```

## Performance Considerations

### Execution Times

Typical execution time per run (200 volumes, 3mm isotropic):

| Platform | Runtime | Time per Run | Parallel (n_jobs=2) |
|----------|---------|--------------|---------------------|
| **macOS (M1/M2)** | Docker + Rosetta 2 | ~12 min | 2 runs in ~12 min |
| **macOS (Intel)** | Docker native | ~8 min | 2 runs in ~8 min |
| **Linux** | Docker native | ~5-8 min | 2 runs in ~8 min |
| **Linux** | Singularity native | ~5-8 min | 2 runs in ~8 min |
| **Linux (ARM64)** | Singularity + QEMU | ~20-30 min | 2 runs in ~30 min |

### Optimization Tips

1. **Use parallel processing:**
   ```bash
   fmriqa --manifest manifest.yaml --generate-motion --n-jobs 4
   ```

   Recommended values:
   - macOS: `--n-jobs 2` (balance speed and system responsiveness)
   - Linux/HPC: `--n-jobs 4-8` (depending on available cores)

2. **Reuse containers:**
   - First run downloads container (~1.2 GB for Singularity)
   - Subsequent runs use cached container (instant)
   - Cache location: `~/.fmriqa/containers/`

3. **Resource allocation:**
   Each mcflirt process uses:
   - CPU: ~1 core at 100%
   - Memory: ~2-4 GB
   - Disk: minimal (just .par file output)

## Troubleshooting

### Docker Issues

**Problem:** `Cannot connect to Docker daemon`
```bash
# Check Docker is running
docker info

# Start Docker Desktop (macOS/Windows)
open -a Docker  # macOS

# Start Docker service (Linux)
sudo systemctl start docker
```

**Problem:** `Image pull timeout`
```bash
# Manually pull image first
docker pull vnmd/fsl_6.0.5.1:20221016

# Then run fmriqa
fmriqa --manifest manifest.yaml --generate-motion
```

**Problem:** `Permission denied` (Linux)
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then verify
groups
docker ps
```

### Singularity Issues

**Problem:** `Container not found` error
```bash
# Check Singularity is available
singularity --version

# On HPC, load module first
module load singularity
```

**Problem:** `FATAL: image targets 'amd64', cannot run on 'arm64'`

This occurs on ARM64 systems (like Raspberry Pi). The container is x86_64 only.

**Solutions:**
1. Use Docker instead (better emulation with Rosetta 2 on macOS)
2. On Linux ARM64: Install QEMU and use `--unsquash` (automatically done by fmriqa)
3. On HPC: Use x86_64 compute nodes

**Problem:** Download fails or is very slow

```bash
# Download manually first
mkdir -p ~/.fmriqa/containers
cd ~/.fmriqa/containers
wget https://neurocontainers.neurodesk.org/fsl_6.0.5.1_20221016.simg

# Then use custom path
fmriqa --manifest manifest.yaml \
    --generate-motion \
    --fsl-container ~/.fmriqa/containers/fsl_6.0.5.1_20221016.simg
```

### Timeout Issues

**Problem:** `mcflirt timed out after 900 seconds`

Default timeout is 15 minutes (Docker) or 5 minutes (Singularity on x86_64).

**Causes:**
- Very large BOLD files (>500 volumes)
- Slow disk I/O
- ARM64 system with QEMU emulation (automatically gets 60 min timeout)

**Solution:** Contact the developers if you consistently hit timeouts with normal-sized data.

### Motion Parameter Format Issues

**Problem:** Generated `.par` file not loading

Check the file format:
```bash
head motion.par

# Expected format (6 columns, one row per volume):
# rot_x  rot_y  rot_z  trans_x  trans_y  trans_z
# -0.001 0.002  -0.0005  0.5    -0.3     0.1
```

FSL mcflirt always generates standard 6-parameter format that fmriqa can read.

## Technical Details

### Container Information

**FSL Container:**
- **Image:** `vnmd/fsl_6.0.5.1:20221016` (Docker) or `fsl_6.0.5.1_20221016.simg` (Singularity)
- **Source:** Neurodesk project (https://neurodesk.org)
- **Size:** ~1.2 GB (compressed)
- **FSL Version:** 6.0.5.1
- **Architecture:** x86_64 (amd64)

**Volume Mounts:**
- Docker: `-v <host_path>:<host_path>` (preserves absolute paths)
- Singularity: `-B <host_path>:<host_path>` (bind mount)

### mcflirt Command

fmriqa runs mcflirt with these options:
```bash
mcflirt \
    -in /path/to/bold.nii.gz \
    -o /path/to/output_basename \
    -plots  # Generates .par file
```

The `-plots` flag is essential - it generates the `.par` file with motion parameters.

### Output Files

After successful motion generation:
```
QA/YYYYMMDD_HHMMSS/
└── motion_params/
    ├── sub-01_ses-01_run-01_mcflirt.par       # Motion parameters (18 KB)
    └── sub-01_ses-01_run-01_mcflirt.nii.gz    # Motion-corrected volume (26 MB)
```

Only the `.par` file is used by fmriqa for FD computation. The `.nii.gz` is generated by mcflirt but not used.

## FAQ

**Q: Can I use my own FSL installation instead of containers?**

A: Not currently. The feature requires containerized FSL for reproducibility and cross-platform support. If you have your own FSL, you can run mcflirt separately and provide the .par files via manifest.

**Q: Does motion generation modify my original BOLD files?**

A: No. Motion correction runs on copies inside containers. Only `.par` files are saved to the QA output directory.

**Q: Can I use this for multi-echo data?**

A: Yes, but motion parameters should typically come from your multi-echo preprocessing pipeline (tedana, etc.). Generate motion parameters only if they're not available from preprocessing.

**Q: What if I already have some .par files?**

A: fmriqa only generates motion for runs without existing motion files. Specify existing motion files in your manifest and omit the `motion:` field for runs that need generation.

**Q: Is the motion correction from mcflirt used in QA?**

A: No. fmriqa only uses the `.par` file (motion parameters) for FD computation. The motion-corrected volume is generated by mcflirt but not used. Your original preprocessing (which should include motion correction) is what's being assessed.

**Q: Can I delete the motion_params/ directory after QA?**

A: Only if you don't plan to use `--reports-only` later. The `.par` files are needed if you want to regenerate reports from cached results.

## Related Documentation

- [Manifest Files](MANIFEST.md) - How to specify motion files in manifests
- [Metrics Reference](METRICS.md) - Details on FD and motion metrics
- [Configuration Options](CONFIGURATION.md) - All motion generation settings

## References

- FSL mcflirt: https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/MCFLIRT
- Neurodesk: https://neurodesk.org
- Power et al. (2012): Framewise displacement definition
- Jenkinson et al. (2002): MCFLIRT motion correction algorithm
