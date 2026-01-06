# fmriqa

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

> **Disclaimer:** Large portions of this codebase were AI-generated and have not been fully manually reviewed. Please verify correctness before using in production or for published research.

**fmriqc** is a comprehensive quality assurance pipeline for fMRI preprocessing outputs. It generates interactive HTML reports with detailed metrics, visualizations, and automated outlier detection to help you assess and improve data quality.

## ✨ Key Features

- 📊 **Comprehensive Metrics** - tSNR, DVARS, FD, GCOR, smoothness, and more
- 🎨 **Interactive Reports** - Hierarchical HTML reports with keyboard navigation
- 📈 **Longitudinal Tracking** - Timeline visualizations showing metric evolution across sessions
- 🔍 **Outlier Detection** - Automated identification of problematic runs
- ⚡ **Parallel Processing** - Multi-core support for fast processing
- 📝 **Flexible Input** - BIDS-compliant or custom manifest files
- 🧠 **Motion Generation** - Automatic FSL mcflirt integration via Docker/Singularity
- 💾 **Smart Caching** - Incremental processing with result reuse

## 📖 Documentation

- **[Installation Guide](docs/INSTALL.md)** - Detailed installation instructions
- **[Usage Guide](docs/USAGE.md)** - Comprehensive usage examples
- **[Manifest Files](docs/MANIFEST.md)** - Custom data organization
- **[Metrics Reference](docs/METRICS.md)** - Detailed metric descriptions
- **[Configuration Options](docs/CONFIGURATION.md)** - All CLI and config options
- **[Motion Generation](docs/MOTION_GENERATION.md)** - Generating motion parameters
- **[Python API](docs/API.md)** - Programmatic usage
- **[Contributing](CONTRIBUTING.md)** - Development guidelines

## 🚀 Quick Start

### Installation

```bash
pip install fmriqa
```

### Basic Usage

```bash
# Run QA on preprocessed data
fmriqa --derivatives-dir /path/to/derivatives --data-source tedana --n-jobs 4

# Using a manifest for custom directory structures
fmriqa --manifest manifest.yaml --n-jobs 4

# Generate motion parameters if missing (requires Docker or Singularity)
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 2
```

### Python API

```python
from pathlib import Path
from fmriqa.orchestration.config import QAConfig
from fmriqa.orchestration.orchestration import run_qa

config = QAConfig.from_yaml("qa_config.yaml")
results = run_qa(config)
```

## 📋 What You Need

**Required:**
- 4D BOLD NIfTI files (`.nii.gz`) - preprocessed fMRI timeseries

**Optional (but recommended):**
- Brain masks (`.nii.gz`) - auto-generated if missing
- Motion parameters (`.par` or `.txt`) - can be generated with `--generate-motion`

## 📊 Example Output

The pipeline generates a hierarchical report structure:

```
QA/YYYYMMDD_HHMMSS/
├── index.html              # Main study report
├── qa_config.yaml          # Configuration used
├── study_summary.json      # Overall metrics
├── outlier_report.json     # Outlier detection results
├── exclusions/
│   ├── excluded_runs.tsv   # Recommended exclusions
│   └── censor_files/       # Volume-level censoring
├── aggregate_maps/         # Average maps across runs
├── group_plots/            # Cross-subject comparisons
└── sub-*/
    ├── subject_report.html # Per-subject report
    └── ses-*/
        ├── session_report.html
        └── run-*/
            ├── figures/
            └── metrics.json
```

## 🎮 Interactive Features

The HTML reports include:

- **Keyboard Navigation**:
  - `j`/`k` - Next/previous run
  - `Space` - Toggle run quality (good/bad)
  - `f` - Jump to next flagged run
  - `/` - Search
  - `e`/`c` - Expand/collapse all

- **Longitudinal Timeline**: Track metric evolution across sessions
- **Quality Badges**: Color-coded quality indicators
- **Export Options**: Save decisions to JSON
- **Responsive Design**: Works on desktop and tablets

## 🧪 Computed Metrics

| Metric | Description | Good Values |
|--------|-------------|-------------|
| **tSNR** | Temporal signal-to-noise ratio | > 50 |
| **DVARS** | Frame-to-frame signal change | < 1.5 |
| **FD** | Framewise displacement (head motion) | < 0.3 mm |
| **GCOR** | Global correlation | < 0.2 |
| **Smoothness** | Spatial smoothness (FWHM) | Data-dependent |
| **AR(1)** | Temporal autocorrelation | 0.2 - 0.6 |
| **Coverage** | Brain coverage percentage | > 85% |

See [docs/METRICS.md](docs/METRICS.md) for detailed descriptions and references.

## 🔧 Advanced Features

### Motion Parameter Generation

If motion parameters are not available from preprocessing:

```bash
fmriqa --manifest manifest.yaml --generate-motion --n-jobs 2
```

Requires Docker (macOS/Windows) or Singularity/Apptainer (HPC). See [docs/MOTION_GENERATION.md](docs/MOTION_GENERATION.md) for details.

### Custom Thresholds

```bash
fmriqa --derivatives-dir /path/to/data \
    --fd-threshold 0.5 \
    --dvars-z-threshold 3.0 \
    --tsnr-drop-threshold 0.25 \
    --exclusion-stringency conservative
```

### Manifest Files for Non-Standard Layouts

```yaml
subjects:
  - id: "sub-01"
    sessions:
      - id: "ses-01"
        runs:
          - bold: "path/to/bold.nii.gz"
            mask: "path/to/mask.nii.gz"  # optional
            motion: "path/to/motion.par"  # optional
            run: "run-01"
```

See [docs/MANIFEST.md](docs/MANIFEST.md) for complete format specification.

## 📦 Module Structure

```
src/fmriqa/
├── orchestration/          # Pipeline orchestration
│   ├── orchestration.py    # Run discovery and processing
│   ├── config.py           # Configuration management
│   └── cli_parser.py       # CLI argument parsing
├── core/                   # Core QA computation
│   ├── processing.py       # Per-run QA processing
│   ├── metrics.py          # Metric computation functions
│   └── constants.py        # Threshold and constant definitions
├── reporting/              # Report generation
│   ├── reporting.py        # HTML report generation
│   ├── static/             # CSS, JS assets
│   └── templates/          # Jinja2 HTML templates
├── visualization/          # Figure creation
│   └── visualization.py    # Plots and spatial maps
├── analysis/               # Quality analysis
│   ├── outliers.py         # Outlier detection
│   ├── exclusions.py       # Exclusion recommendations
│   └── consistency.py      # Intra-subject consistency
├── io/                     # I/O operations
│   ├── io.py               # File I/O and caching
│   ├── manifest.py         # Manifest handling
│   └── structures.py       # Data structures
└── motion_generation.py    # Motion parameter generation
```

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Key areas for contribution:
- Additional QA metrics
- New visualization types
- Performance optimizations
- Documentation improvements
- Bug fixes and testing

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- [fMRIPrep](https://fmriprep.org/) - Robust preprocessing pipeline
- [MRIQC](https://mriqc.readthedocs.io/) - Image quality metrics
- [tedana](https://tedana.readthedocs.io/) - Multi-echo denoising
- [GLMsingle](https://github.com/cvnlab/GLMsingle) - Single-trial GLM estimation

---

Made with ❤️ for the neuroimaging community
