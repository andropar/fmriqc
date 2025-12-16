# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-12-16

### Added
- Initial public release as standalone package
- Comprehensive fMRI QA pipeline with metric computation
- Interactive HTML report generation with keyboard shortcuts
- Support for BIDS derivatives and custom datasets via manifests
- Parallel processing support with joblib
- Outlier detection and exclusion recommendations
- Carpetplot visualization
- Session and subject-level aggregation
- Command-line interface (`fmriqa`)
- Python API for programmatic use

### Features
- **Metrics**: tSNR, DVARS, FD, GCOR, smoothness
- **Outputs**: Interactive HTML reports, exclusion lists, censor files
- **Data Sources**: tedana, finalinterp, glmsingle, custom manifests
- **Configurability**: Extensive CLI options and YAML config support

[Unreleased]: https://github.com/andropar/fmriqa/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/andropar/fmriqa/releases/tag/v0.1.0
