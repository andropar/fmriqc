# Contributing to fmriqa

Thank you for your interest in contributing to fmriqa! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Project Structure](#project-structure)

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming environment for all contributors.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR-USERNAME/fmriqa.git
   cd fmriqa
   ```

3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/andropar/fmriqa.git
   ```

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- For motion generation testing: Docker or Singularity

### Install Development Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

This installs:
- Main dependencies (nibabel, numpy, scipy, etc.)
- Development tools (pytest, black, ruff, mypy)
- Testing utilities (pytest-cov, pytest-xdist)

### Verify Installation

```bash
# Run tests
pytest tests/

# Check code style
ruff check src/

# Type checking
mypy src/fmriqa
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions/improvements

### 2. Make Your Changes

Follow the [Code Style](#code-style) guidelines below.

### 3. Write Tests

Add tests for new functionality:

```python
# tests/test_your_feature.py
import pytest
from fmriqa.your_module import your_function

def test_your_function():
    """Test your_function with typical input."""
    result = your_function(input_data)
    assert result == expected_output

def test_your_function_edge_case():
    """Test your_function with edge case."""
    with pytest.raises(ValueError):
        your_function(invalid_input)
```

### 4. Update Documentation

- Update docstrings for new/modified functions
- Update relevant `.md` files in `docs/`
- Add examples if introducing new features

## Testing

### Run All Tests

```bash
pytest tests/
```

### Run Specific Tests

```bash
# Single test file
pytest tests/test_metrics.py

# Single test function
pytest tests/test_metrics.py::test_compute_tsnr

# With coverage
pytest --cov=fmriqa tests/
```

### Run Tests in Parallel

```bash
pytest -n auto tests/
```

### Integration Tests

For tests requiring real fMRI data:

```bash
# Download test dataset
python tests/download_test_data.py

# Run integration tests
pytest tests/test_integration.py
```

## Documentation

### Docstring Style

Use NumPy-style docstrings:

```python
def compute_metric(data, mask, threshold=0.5):
    """Compute quality metric from fMRI data.

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data (x, y, z, time).
    mask : np.ndarray
        3D brain mask (x, y, z).
    threshold : float, optional
        Threshold value for metric computation (default: 0.5).

    Returns
    -------
    float
        Computed metric value.

    Raises
    ------
    ValueError
        If data and mask have incompatible shapes.

    Examples
    --------
    >>> data = np.random.rand(64, 64, 32, 200)
    >>> mask = np.ones((64, 64, 32))
    >>> metric = compute_metric(data, mask)
    >>> print(f"Metric: {metric:.2f}")
    Metric: 0.75

    References
    ----------
    .. [1] Smith et al. (2020). "Quality Metrics for fMRI."
           NeuroImage, 200, 123-145.
    """
    if data.shape[:3] != mask.shape:
        raise ValueError("Data and mask shapes incompatible")

    # Implementation here
    return result
```

### Type Hints

Use type hints for function signatures:

```python
from typing import Optional, Tuple, List
import numpy as np
from pathlib import Path

def process_run(
    bold_path: Path,
    mask_path: Optional[Path] = None,
    threshold: float = 0.5
) -> Tuple[np.ndarray, List[float]]:
    """Process a single fMRI run."""
    pass
```

## Submitting Changes

### 1. Commit Your Changes

Write clear, concise commit messages:

```bash
git add .
git commit -m "Add feature: Longitudinal timeline visualization

- Implement inline metrics timeline
- Add Chart.js integration
- Update subject report template
- Add documentation in docs/USAGE.md

Closes #123"
```

Commit message guidelines:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed description (wrap at 72 characters)
- Reference issues: `Closes #123`, `Fixes #456`

### 2. Push to Your Fork

```bash
git push origin feature/your-feature-name
```

### 3. Create Pull Request

1. Go to https://github.com/andropar/fmriqa
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill in the PR template:
   - **Description**: What changes does this PR make?
   - **Motivation**: Why is this change needed?
   - **Testing**: How was this tested?
   - **Screenshots**: If applicable (for UI changes)

### 4. Code Review

- Address review comments
- Push additional commits to your branch
- CI tests must pass before merging

## Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 88 characters (Black default)
- **Import order**: stdlib, third-party, local (managed by ruff)
- **String quotes**: Double quotes preferred

### Automated Formatting

```bash
# Format code with Black
black src/ tests/

# Sort imports with ruff
ruff check --select I --fix src/ tests/

# Check for issues
ruff check src/ tests/
```

### Pre-commit Hooks

We recommend setting up pre-commit hooks:

```bash
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Naming Conventions

- **Functions/variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

Examples:
```python
# Good
def compute_temporal_snr(data: np.ndarray) -> float:
    pass

class QAConfig:
    pass

MAX_ITERATIONS = 1000

# Bad
def ComputeTemporalSNR(data):  # Should be snake_case
    pass

class qaconfig:  # Should be PascalCase
    pass
```

## Project Structure

```
fmriqa/
├── src/fmriqa/           # Main package
│   ├── orchestration/     # Pipeline orchestration
│   ├── core/              # Core QA computation
│   ├── reporting/         # Report generation
│   ├── analysis/          # Quality analysis
│   ├── io/                # I/O operations
│   └── motion_generation.py
│
├── tests/                 # Test suite
│   ├── test_metrics.py
│   ├── test_processing.py
│   └── ...
│
├── docs/                  # Documentation
│   ├── INSTALL.md
│   ├── USAGE.md
│   └── ...
│
├── README.md              # Main README
├── CONTRIBUTING.md        # This file
├── LICENSE                # MIT License
└── pyproject.toml         # Project configuration
```

### Adding New Modules

When adding new modules:

1. Create module in appropriate directory:
   - Core functionality → `src/fmriqa/core/`
   - Reporting → `src/fmriqa/reporting/`
   - Analysis → `src/fmriqa/analysis/`

2. Add corresponding tests in `tests/`

3. Update `__init__.py` to export public API

4. Document in appropriate `.md` file in `docs/`

### Module Guidelines

- **Single Responsibility**: Each module should have one clear purpose
- **Minimal Dependencies**: Avoid circular imports
- **Public API**: Use `__all__` to define public exports
- **Documentation**: Every public function needs docstrings

## Areas for Contribution

We especially welcome contributions in these areas:

### High Priority

- **Additional Metrics**: New QA metrics from the literature
- **Performance Optimization**: Faster processing for large datasets
- **Test Coverage**: More comprehensive test suite
- **Documentation**: Examples, tutorials, use cases

### Medium Priority

- **Visualization Improvements**: New plot types, interactive features
- **Configuration Options**: More flexible threshold settings
- **Export Formats**: Additional output formats (CSV, TSV, etc.)
- **Bug Fixes**: Any reported issues

### Ideas for Major Features

- **Real-time QA**: Monitor ongoing acquisitions
- **Machine Learning**: Automated quality classification
- **Multi-modal Support**: Integration with anatomical QA
- **Database Backend**: PostgreSQL/MySQL for large studies

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/andropar/fmriqa/discussions)
- **Bug Reports**: Open an [Issue](https://github.com/andropar/fmriqa/issues)
- **Feature Requests**: Open an [Issue](https://github.com/andropar/fmriqa/issues) with `enhancement` label

## Recognition

Contributors will be:
- Listed in `CONTRIBUTORS.md`
- Acknowledged in release notes
- Credited in relevant documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to fmriqa! 🎉
