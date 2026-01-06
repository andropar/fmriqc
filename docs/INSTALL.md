# Installation Guide

## Quick Install

```bash
pip install fmriqa
```

## Development Install

```bash
git clone https://github.com/andropar/fmriqa.git
cd fmriqa
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

## Optional Dependencies

### Motion Parameter Generation

For `--generate-motion` feature:

**macOS/Windows:**
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Linux/HPC:**
- Singularity or Apptainer

See [Motion Generation Guide](MOTION_GENERATION.md) for details.

## Platform-Specific Notes

### macOS

```bash
# Install via pip (recommended)
pip install fmriqa

# Or via Homebrew (if available)
# brew install fmriqa  # Not yet available
```

### Linux

```bash
# Ubuntu/Debian
sudo apt-get install python3-pip
pip3 install fmriqa

# RHEL/CentOS
sudo yum install python3-pip
pip3 install fmriqa
```

### Windows

```bash
# Install Python 3.9+ from python.org
# Then use pip
pip install fmriqa
```

### HPC Clusters

```bash
# Load Python module
module load python/3.9

# Install in user directory
pip install --user fmriqa

# Or use virtual environment
python -m venv ~/venvs/fmriqa
source ~/venvs/fmriqa/bin/activate
pip install fmriqa
```

## Verifying Installation

```bash
# Check installation
fmriqa --help

# Run test
python -c "import fmriqa; print(fmriqa.__version__)"
```

## Upgrading

```bash
pip install --upgrade fmriqa
```

## Uninstalling

```bash
pip uninstall fmriqa
```

## Troubleshooting

### ImportError: No module named 'nibabel'

```bash
pip install nibabel
```

### Permission Denied

```bash
# Install for user only
pip install --user fmriqa
```

### Command not found: fmriqa

```bash
# Add to PATH (macOS/Linux)
export PATH="$HOME/.local/bin:$PATH"

# Or run via python
python -m fmriqa --help
```

For more help, see [GitHub Issues](https://github.com/andropar/fmriqa/issues).
