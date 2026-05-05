# Installation Guide

## Quick Install

```bash
pip install fmriqc
```

## Development Install

```bash
git clone https://github.com/andropar/fmriqc.git
cd fmriqc
pip install -e ".[dev]"
```

## Requirements

- Python 3.9 or higher
- Dependencies automatically installed:
  - `nibabel` - NIfTI file I/O
  - `numpy` - Numerical computations
  - `scipy` - Statistical functions
  - `matplotlib` - Visualization
  - `jinja2` - HTML report templating
  - `pyyaml` - Configuration files
  - `joblib` - Parallel processing
  - `scikit-learn` - Outlier detection
  - `tqdm` - Progress bars

## Optional Runtime Tools

### Motion Generation

For `--generate-motion`:

**macOS/Windows:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Linux/HPC:**
- Singularity or Apptainer

See [Motion Generation](MOTION_GENERATION.md) for details.

## Platform-Specific Notes

### macOS

```bash
# Install via pip (recommended)
pip install fmriqc

# Or via Homebrew (if available)
# brew install fmriqc  # Not yet available
```

### Linux

```bash
# Ubuntu/Debian
sudo apt-get install python3-pip
pip3 install fmriqc

# RHEL/CentOS
sudo yum install python3-pip
pip3 install fmriqc
```

### Windows

```bash
# Install Python 3.9+ from python.org
# Then use pip
pip install fmriqc
```

### HPC Clusters

```bash
# Load Python module
module load python/3.9

# Install in user directory
pip install --user fmriqc

# Or use virtual environment
python -m venv ~/venvs/fmriqc
source ~/venvs/fmriqc/bin/activate
pip install fmriqc
```

## Verifying Installation

```bash
# Check installation
fmriqc --help

# Run test
python -c "import fmriqc; print(fmriqc.__version__)"
```

## Upgrading

```bash
pip install --upgrade fmriqc
```

## Uninstalling

```bash
pip uninstall fmriqc
```

## Troubleshooting

### ImportError: No module named 'nibabel'

```bash
pip install nibabel
```

### Permission Denied

```bash
# Install for user only
pip install --user fmriqc
```

### Command not found: fmriqc

```bash
# Add to PATH (macOS/Linux)
export PATH="$HOME/.local/bin:$PATH"

# Or invoke the installed console script from its full path
python -c "import fmriqc; print(fmriqc.__version__)"
```

For more help, see [GitHub Issues](https://github.com/andropar/fmriqc/issues).
