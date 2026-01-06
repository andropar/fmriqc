# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fmriqa is a quality assurance pipeline for fMRI preprocessing outputs. It processes 4D BOLD NIfTI files to compute QA metrics (tSNR, DVARS, FD, GCOR, smoothness, etc.), detects outliers, and generates interactive HTML reports.

## Development Commands

```bash
# Install in development mode
pip install -e ".[dev]"

# Run all tests with coverage
pytest tests/

# Run single test file
pytest tests/test_metrics.py

# Run single test function
pytest tests/test_metrics.py::test_compute_tsnr

# Run tests in parallel
pytest -n auto tests/

# Lint/format
ruff check src/
black src/ tests/

# Type check
mypy src/fmriqa
```

## Architecture

### Data Flow

1. **CLI Entry** (`cli.py` → `orchestration/core.py:main()`)
2. **Run Discovery** (`orchestration/orchestration.py`) - Finds runs from BIDS layout or manifest files
3. **Per-Run Processing** (`core/processing.py:process_single_run()`) - Loads NIfTI, computes metrics, generates figures
4. **Results Aggregation** (`orchestration/aggregation.py`) - Combines into hierarchical structure
5. **Outlier Detection** (`analysis/outliers.py`, `analysis/exclusions.py`)
6. **Report Generation** (`reporting/reporting.py`) - HTML reports via Jinja2 templates

### Key Data Structures (`io/structures.py`)

- `RunInfo` - Metadata about a single fMRI run (subject, session, task, paths)
- `RunResult` - Complete QA results for a run (metrics dict, flags dict, series, maps)
- `SessionResults` / `SubjectResults` / `StudyResults` - Hierarchical aggregation

### Module Layout

```
src/fmriqa/
├── orchestration/     # Pipeline coordination
│   ├── core.py        # Main entry point (run_qa)
│   ├── orchestration.py # Run discovery and processing
│   ├── config.py      # QAConfig dataclass
│   └── aggregation.py # Results organization
├── core/              # QA computation
│   ├── processing.py  # process_single_run()
│   ├── metrics.py     # tSNR, DVARS, FD, etc.
│   └── constants.py   # Thresholds
├── analysis/          # Quality analysis
│   ├── outliers.py    # Statistical outlier detection
│   └── exclusions.py  # Exclusion recommendations
├── reporting/         # HTML generation
│   ├── reporting.py   # Main report generation
│   └── report_components/  # Jinja2 helpers
├── io/                # I/O operations
│   ├── io.py          # File operations, caching
│   ├── manifest.py    # Manifest file parsing
│   └── structures.py  # Data classes
└── visualization/     # Figure generation
```

### Configuration

`QAConfig` (in `orchestration/config.py`) is the central configuration dataclass. It can be loaded from YAML or constructed from CLI args.

### Testing

Tests use synthetic data via pytest fixtures in `conftest.py`:
- `synthetic_bold_data` - 4D numpy array (10x10x10x20)
- `brain_mask` - 3D boolean mask
- `motion_params` - 6-column motion parameters
- `temp_nifti` / `temp_mask` - Temporary NIfTI files

## Key Conventions

- NumPy-style docstrings
- Type hints on function signatures
- `snake_case` for functions/variables, `PascalCase` for classes
- Line length: 100 chars (black with `--line-length 100`)
- Python 3.8+ compatibility
