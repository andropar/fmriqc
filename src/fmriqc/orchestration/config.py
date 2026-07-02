"""Configuration management for fmriqc snapshot QA.

This module provides a hierarchical configuration system for the QA pipeline,
organizing settings into logical groups for better maintainability.

Configuration Hierarchy
-----------------------
- PathConfig: File paths and directories
- ThresholdConfig: Quality thresholds
- ProcessingConfig: Processing options
- VisualizationConfig: Visualization settings
- AnalysisConfig: Analysis options
- ReportingConfig: Report generation

Usage
-----
Create default config:

>>> config = QAConfig()

Create custom config:

>>> config = QAConfig(
...     paths=PathConfig(bids_root=Path("/data")),
...     processing=ProcessingConfig(n_jobs=4),
...     thresholds=ThresholdConfig(fd_threshold=0.3)
... )

Load from dictionary:

>>> config = QAConfig.from_dict(config_dict)

Access nested settings:

>>> config.paths.bids_root
>>> config.thresholds.fd_threshold
>>> config.processing.n_jobs

Backward compatibility (flat access):

>>> config.bids_root  # Same as config.paths.bids_root
>>> config.n_jobs     # Same as config.processing.n_jobs
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import yaml

from fmriqc.core.thresholds import ResolvedThresholds
from fmriqc.io.structures import SnapshotInfo

if TYPE_CHECKING:
    from fmriqc.io.manifest import QAManifest


class DataSourcePreset(Enum):
    """Data source presets for QA pipeline.

    Each preset defines which type of preprocessed data to analyze.
    """
    FINALINTERP = "finalinterp"  # Final interpolated BOLD (default)
    TEDANA = "tedana"            # Tedana optimally combined outputs
    FMRIPREP = "fmriprep"        # fMRIPrep preprocessed BOLD derivatives


# Glob patterns for each preset
PRESET_PATTERNS = {
    DataSourcePreset.FINALINTERP: "sub-*/ses-*/finalinterp_func/sub-*_bold_final.nii.gz",
    DataSourcePreset.TEDANA: "sub-*/ses-*/tedana/run-*/sub-*_desc-optcom_bold.nii.gz",
    DataSourcePreset.FMRIPREP: "sub-*/**/func/*_desc-preproc_bold.nii.gz",
}

# Mask patterns for each preset
MASK_PATTERNS = {
    DataSourcePreset.FINALINTERP: "sub-*/ses-*/finalinterp_func/sub-*_mask.nii.gz",
    DataSourcePreset.TEDANA: "sub-*/ses-*/tedana/run-*/sub-*_desc-brain_mask.nii.gz",
    DataSourcePreset.FMRIPREP: "sub-*/**/func/*_desc-brain_mask.nii.gz",
}


def get_glob_pattern(preset: DataSourcePreset) -> str:
    """Get glob pattern for a data source preset.

    Parameters
    ----------
    preset : DataSourcePreset
        Data source preset
    str
        Glob pattern for file discovery.
    """
    return PRESET_PATTERNS[preset]


def _serialize_config_value(value: Any) -> Any:
    """Make dataclass/Path config values JSON/YAML serializable."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_serialize_config_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_config_value(item) for key, item in value.items()}
    return value


def _filter_dataclass_kwargs(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {field.name for field in fields(cls)}
    return {key: value for key, value in data.items() if key in allowed}


@dataclass
class PathConfig:
    """Path-related configuration.

    Attributes
    ----------
    bids_root : Optional[Path]
        BIDS root directory (recommended)
    derivatives_dir : Optional[Path]
        Derivatives directory to analyze
    output_dir_name : str
        Name of output directory (created within derivatives_dir)
    config_file : Optional[Path]
        Path to configuration file
    reuse_run_dir : Optional[Path]
        Existing QA directory to reuse
    manifest_path : Optional[Path]
        Path to manifest file for manifest-based input
    cache_dir : Optional[Path]
        Directory for caching intermediate results
    reference_mask : Optional[Path]
        Reference mask for quality metrics
    """

    bids_root: Optional[Path] = None
    derivatives_dir: Optional[Path] = None
    output_dir_name: str = "QA"
    config_file: Optional[Path] = None
    reuse_run_dir: Optional[Path] = None
    manifest_path: Optional[Path] = None
    cache_dir: Optional[Path] = None
    reference_mask: Optional[Path] = None

    def __post_init__(self):
        """Convert strings to Path objects."""
        if isinstance(self.bids_root, str):
            self.bids_root = Path(self.bids_root)
        if isinstance(self.derivatives_dir, str):
            self.derivatives_dir = Path(self.derivatives_dir)
        if isinstance(self.config_file, str):
            self.config_file = Path(self.config_file)
        if isinstance(self.reuse_run_dir, str):
            self.reuse_run_dir = Path(self.reuse_run_dir)
        if isinstance(self.manifest_path, str):
            self.manifest_path = Path(self.manifest_path)
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        if isinstance(self.reference_mask, str):
            self.reference_mask = Path(self.reference_mask)


@dataclass
class ThresholdConfig:
    """Quality thresholds for flagging runs.

    Attributes
    ----------
    fd_threshold : float
        Framewise displacement threshold (mm)
    fd_median_threshold : float
        Median FD threshold (mm)
    dvars_z_threshold : float
        DVARS z-score threshold
    outlier_threshold : float
        Outlier fraction threshold
    slice_intensity_threshold : float
        Slice intensity z-score threshold
    outlier_metric_threshold : float
        Mahalanobis distance threshold for outlier detection
    outlier_min_runs : int
        Minimum runs needed for outlier detection
    tsnr_threshold : float
        Minimum acceptable tSNR value
    coverage_threshold : float
        Minimum brain coverage fraction
    """

    profile: str = "default"
    fd_threshold: float = 0.3
    fd_median_threshold: float = 0.2
    dvars_z_threshold: float = 2.5
    outlier_threshold: float = 0.02
    slice_intensity_threshold: float = 3.0
    outlier_metric_threshold: float = 3.0
    outlier_min_runs: int = 5
    tsnr_threshold: float = 30.0
    coverage_threshold: float = 0.85

    def __post_init__(self):
        """Validate thresholds."""
        if self.fd_threshold <= 0:
            raise ValueError("fd_threshold must be positive")
        if self.fd_median_threshold <= 0:
            raise ValueError("fd_median_threshold must be positive")
        if self.tsnr_threshold <= 0:
            raise ValueError("tsnr_threshold must be positive")
        if not 0 < self.coverage_threshold <= 1:
            raise ValueError("coverage_threshold must be between 0 and 1")
        if self.outlier_min_runs < 1:
            raise ValueError("outlier_min_runs must be >= 1")

    def resolve(self) -> ResolvedThresholds:
        """Resolve legacy config fields into the canonical threshold object."""
        return ResolvedThresholds(
            profile=self.profile if self.profile in {"lenient", "default", "strict"} else "custom",
            fd_volume=self.fd_threshold,
            fd_median=self.fd_median_threshold,
            dvars_std_volume=self.dvars_z_threshold,
            outlier_fraction_volume=self.outlier_threshold,
            tsnr_median_min=self.tsnr_threshold,
            coverage_signal_fraction_min=self.coverage_threshold,
        )


@dataclass
class SnapshotConfig:
    """Identity for the dataset snapshot being assessed."""

    id: str = "snapshot"
    label: str = ""
    source_type: str = "custom"
    description: str = ""
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[str] = None

    def to_snapshot_info(self, root: Optional[Path] = None) -> SnapshotInfo:
        return SnapshotInfo(
            id=self.id,
            label=self.label,
            source_type=self.source_type,  # type: ignore[arg-type]
            description=self.description,
            root=root,
            pipeline_name=self.pipeline_name,
            pipeline_version=self.pipeline_version,
        )


@dataclass
class MotionConfig:
    """Motion-loading and optional generation strategy."""

    strategy: str = "prefer_provided"
    generation_tool: str = "mcflirt"
    fsl_container_path: Optional[Path] = None
    download_policy: str = "ask"
    diagnostic_only_for_preprocessed: bool = True

    def __post_init__(self):
        if isinstance(self.fsl_container_path, str):
            self.fsl_container_path = Path(self.fsl_container_path)
        valid = {"prefer_provided", "generate_if_missing", "none"}
        if self.strategy not in valid:
            raise ValueError(f"motion strategy must be one of {sorted(valid)}")


@dataclass
class ProcessingConfig:
    """Processing options and parallelization.

    Attributes
    ----------
    n_jobs : int
        Number of parallel jobs
    target_echo : int
        Target echo for multi-echo data
    use_cache : bool
        Use cached results when available
    force_reprocess : bool
        Force reprocessing of all data
    dry_run : bool
        Perform dry run without processing
    use_multiecho : bool
        Enable multi-echo processing
    data_source : str
        Data source preset (finalinterp, tedana, manifest)
    glob_pattern : str
        Custom glob pattern for file discovery
    generate_motion : bool
        Generate motion parameters using FSL mcflirt when missing
    fsl_container_path : Optional[Path]
        Path to FSL Singularity container (auto-downloads if not specified)
    """

    n_jobs: int = 1
    target_echo: int = 2
    use_cache: bool = True
    force_reprocess: bool = False
    dry_run: bool = False
    use_multiecho: bool = True
    data_source: str = "finalinterp"
    glob_pattern: str = ""

    def __post_init__(self):
        """Validate processing settings."""
        if self.n_jobs < 1:
            raise ValueError("n_jobs must be >= 1")
        if self.target_echo < 1:
            raise ValueError("target_echo must be >= 1")
        if self.data_source == "glmsingle":
            raise ValueError(
                "GLM beta-map QA is out of scope for the time-series snapshot QA pipeline"
            )


@dataclass
class VisualizationConfig:
    """Visualization generation options.

    Attributes
    ----------
    generate_figures : bool
        Generate quality metric figures
    generate_carpetplots : bool
        Generate carpetplot visualizations
    generate_thumbnails : bool
        Generate thumbnail images
    generate_mosaics : bool
        Generate mosaic visualizations
    figure_dpi : int
        DPI for saved figures
    thumbnail_size : Tuple[int, int]
        Size of thumbnail images (width, height)
    """

    generate_figures: bool = True
    generate_carpetplots: bool = True
    generate_thumbnails: bool = True
    generate_mosaics: bool = True
    figure_dpi: int = 100
    thumbnail_size: Tuple[int, int] = (150, 150)

    def __post_init__(self):
        """Validate visualization settings."""
        if self.figure_dpi < 50 or self.figure_dpi > 600:
            raise ValueError("figure_dpi must be between 50 and 600")
        if len(self.thumbnail_size) != 2:
            raise ValueError("thumbnail_size must be a tuple of (width, height)")


@dataclass
class AnalysisConfig:
    """Analysis options (outliers, exclusions, etc.).

    Attributes
    ----------
    detect_outliers : bool
        Enable outlier detection
    generate_exclusions : bool
        Generate candidate review recommendations
    exclusion_stringency : str
        Exclusion stringency level (liberal, moderate, conservative)
    outlier_method : str
        Outlier detection method (mahalanobis, zscore, iqr)
    consistency_analysis : bool
        Enable consistency analysis across sessions
    """

    detect_outliers: bool = True
    generate_exclusions: bool = False
    exclusion_stringency: str = "moderate"
    outlier_method: str = "mahalanobis"
    consistency_analysis: bool = False

    def __post_init__(self):
        """Validate analysis settings."""
        valid_stringencies = ["liberal", "moderate", "conservative"]
        if self.exclusion_stringency not in valid_stringencies:
            raise ValueError(
                f"exclusion_stringency must be one of {valid_stringencies}"
            )

        valid_methods = ["mahalanobis", "zscore", "iqr"]
        if self.outlier_method not in valid_methods:
            raise ValueError(
                f"outlier_method must be one of {valid_methods}"
            )


@dataclass
class ReportingConfig:
    """Report generation options.

    Attributes
    ----------
    generate_reports : bool
        Enable report generation
    generate_group_plots : bool
        Generate group-level plots
    include_subject_reports : bool
        Include subject-level reports
    include_session_reports : bool
        Include session-level reports
    include_study_report : bool
        Include study-level report
    Reports are HTML-only and always use the snapshot report structure.
    """

    generate_reports: bool = True
    generate_group_plots: bool = True
    include_subject_reports: bool = True
    include_session_reports: bool = True
    include_study_report: bool = True

    def __post_init__(self):
        """Validate reporting settings."""


@dataclass
class QAConfig:
    """Main QA configuration with hierarchical structure.

    This is the main configuration class that contains all settings for the
    fMRI QA pipeline, organized into logical groups.

    Attributes
    ----------
    paths : PathConfig
        File paths and directories
    thresholds : ThresholdConfig
        Quality thresholds for flagging
    processing : ProcessingConfig
        Processing and parallelization options
    visualization : VisualizationConfig
        Visualization generation options
    analysis : AnalysisConfig
        Analysis options (outliers, exclusions)
    reporting : ReportingConfig
        Report generation options
    manifest : Optional[QAManifest]
        QA manifest object for manifest-based input

    Examples
    --------
    Create config with defaults:

    >>> config = QAConfig()

    Create config with custom paths:

    >>> config = QAConfig(
    ...     paths=PathConfig(
    ...         bids_root=Path("/data/study"),
    ...         output_dir_name="qa_output"
    ...     )
    ... )

    Create config from dict:

    >>> config_dict = {
    ...     'paths': {'bids_root': '/data/study'},
    ...     'processing': {'n_jobs': 4},
    ...     'thresholds': {'fd_threshold': 0.3}
    ... }
    >>> config = QAConfig.from_dict(config_dict)
    """

    paths: PathConfig = field(default_factory=PathConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    motion: MotionConfig = field(default_factory=MotionConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)
    manifest: Optional["QAManifest"] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, config_dict: dict) -> "QAConfig":
        """Create QAConfig from dictionary.

        Parameters
        ----------
        config_dict : dict
            Configuration dictionary with nested structure

        Returns
        -------
        QAConfig
            Configuration object
        """
        sections = {'paths', 'snapshot', 'thresholds', 'processing', 'motion', 'visualization', 'analysis', 'reporting'}
        if not any(section in config_dict for section in sections):
            return cls._from_flat_dict(dict(config_dict))

        paths = PathConfig(**_filter_dataclass_kwargs(PathConfig, config_dict.get('paths', {})))
        snapshot = SnapshotConfig(**_filter_dataclass_kwargs(SnapshotConfig, config_dict.get('snapshot', {})))
        thresholds = ThresholdConfig(**_filter_dataclass_kwargs(ThresholdConfig, config_dict.get('thresholds', {})))
        processing = ProcessingConfig(**_filter_dataclass_kwargs(ProcessingConfig, config_dict.get('processing', {})))
        motion = MotionConfig(**_filter_dataclass_kwargs(MotionConfig, config_dict.get('motion', {})))
        visualization = VisualizationConfig(**_filter_dataclass_kwargs(VisualizationConfig, config_dict.get('visualization', {})))
        analysis = AnalysisConfig(**_filter_dataclass_kwargs(AnalysisConfig, config_dict.get('analysis', {})))
        reporting = ReportingConfig(**_filter_dataclass_kwargs(ReportingConfig, config_dict.get('reporting', {})))
        manifest = config_dict.get('manifest')

        return cls(
            paths=paths,
            snapshot=snapshot,
            thresholds=thresholds,
            processing=processing,
            motion=motion,
            visualization=visualization,
            analysis=analysis,
            reporting=reporting,
            manifest=manifest,
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary.

        Returns
        -------
        dict
            Configuration as nested dictionary
        """
        result = asdict(self)
        # Remove manifest from dict (not serializable)
        result.pop('manifest', None)
        return _serialize_config_value(result)

    @classmethod
    def from_yaml(cls, path: Path) -> "QAConfig":
        """Load configuration from YAML or JSON file.

        Supports both QA-specific config files and the standard preprocessing
        config (standard_config.json). When using preprocessing config, paths
        are extracted automatically.

        Parameters
        ----------
        path : Path
            Path to configuration file

        Returns
        -------
        QAConfig
            Configuration object
        """
        import json

        path = Path(path)

        # Load file based on extension
        with open(path) as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)

        # Check if this is a preprocessing config (has 'paths' with 'raw_dir')
        if "paths" in data and "raw_dir" in data.get("paths", {}):
            # This is the preprocessing config format - extract relevant fields
            paths_data = data.get("paths", {})
            processing_data = data.get("processing", {})

            return cls(
                paths=PathConfig(
                    derivatives_dir=Path(paths_data["derivatives_dir"]).expanduser() if paths_data.get("derivatives_dir") else None,
                    bids_root=Path(paths_data["raw_dir"]).expanduser() if paths_data.get("raw_dir") else None,
                ),
                processing=ProcessingConfig(
                    target_echo=processing_data.get("target_echo", 2),
                    data_source="tedana" if processing_data.get("tedana", {}).get("enabled", False) else "finalinterp",
                ),
            )

        # Otherwise, this is a QA-specific config
        # Check if it's already hierarchical
        if any(key in data for key in ['paths', 'snapshot', 'thresholds', 'processing', 'motion', 'visualization', 'analysis', 'reporting']):
            # Hierarchical format - convert Path strings
            if 'paths' in data:
                for key in ['bids_root', 'derivatives_dir', 'config_file', 'reuse_run_dir', 'manifest_path', 'cache_dir', 'reference_mask']:
                    if key in data['paths'] and data['paths'][key]:
                        data['paths'][key] = Path(data['paths'][key]).expanduser()
            if 'motion' in data and data['motion'].get('fsl_container_path'):
                data['motion']['fsl_container_path'] = Path(data['motion']['fsl_container_path']).expanduser()
            return cls.from_dict(data)

        # Flat format - convert to hierarchical
        flat_data = {}
        for section, values in data.items():
            if isinstance(values, dict):
                flat_data.update(values)
            else:
                flat_data[section] = values

        # Convert string paths to Path objects
        path_fields = ['derivatives_dir', 'bids_root', 'config_file', 'reuse_run_dir', 'manifest_path', 'cache_dir', 'reference_mask']
        for key in path_fields:
            if key in flat_data and flat_data[key]:
                flat_data[key] = Path(flat_data[key]).expanduser()

        # Remove private fields
        flat_data.pop("_manifest", None)
        flat_data.pop("manifest", None)

        # Map flat fields to hierarchical structure
        return cls._from_flat_dict(flat_data)

    @classmethod
    def _from_flat_dict(cls, flat_data: dict) -> "QAConfig":
        """Create QAConfig from flat dictionary (backward compatibility).

        Parameters
        ----------
        flat_data : dict
            Flat configuration dictionary

        Returns
        -------
        QAConfig
            Configuration object
        """
        # Path fields
        path_kwargs = {
            'bids_root': flat_data.get('bids_root'),
            'derivatives_dir': flat_data.get('derivatives_dir'),
            'output_dir_name': flat_data.get('output_dir_name', 'QA'),
            'config_file': flat_data.get('config_file'),
            'reuse_run_dir': flat_data.get('reuse_run_dir'),
            'manifest_path': flat_data.get('manifest_path'),
            'cache_dir': flat_data.get('cache_dir'),
            'reference_mask': flat_data.get('reference_mask'),
        }

        # Threshold fields
        threshold_kwargs = {
            'profile': flat_data.get('threshold_profile', flat_data.get('profile', 'default')),
            'fd_threshold': flat_data.get('fd_threshold', 0.3),
            'fd_median_threshold': flat_data.get('fd_median_threshold', 0.2),
            'dvars_z_threshold': flat_data.get('dvars_z_threshold', 2.5),
            'outlier_threshold': flat_data.get('outlier_threshold', 0.02),
            'slice_intensity_threshold': flat_data.get('slice_intensity_threshold', 3.0),
            'outlier_metric_threshold': flat_data.get('outlier_metric_threshold', 3.0),
            'outlier_min_runs': flat_data.get('outlier_min_runs', 5),
            'tsnr_threshold': flat_data.get('tsnr_threshold', 30.0),
            'coverage_threshold': flat_data.get('coverage_threshold', 0.85),
        }

        # Processing fields
        processing_kwargs = {
            'n_jobs': flat_data.get('n_jobs', 1),
            'target_echo': flat_data.get('target_echo', 2),
            'use_cache': flat_data.get('use_cache', True),
            'force_reprocess': flat_data.get('force_reprocess', False),
            'dry_run': flat_data.get('dry_run', False),
            'use_multiecho': flat_data.get('use_multiecho', True),
            'data_source': flat_data.get('data_source', 'finalinterp'),
            'glob_pattern': flat_data.get('glob_pattern', ''),
        }

        snapshot_kwargs = {
            'id': flat_data.get('snapshot_id', 'snapshot'),
            'label': flat_data.get('snapshot_label', ''),
            'source_type': flat_data.get('snapshot_source_type', 'custom'),
            'description': flat_data.get('snapshot_description', ''),
            'pipeline_name': flat_data.get('pipeline_name'),
            'pipeline_version': flat_data.get('pipeline_version'),
        }

        motion_kwargs = {
            'strategy': (
                'generate_if_missing'
                if flat_data.get('generate_motion')
                else flat_data.get('motion_strategy', 'prefer_provided')
            ),
            'fsl_container_path': flat_data.get('fsl_container_path'),
            'download_policy': flat_data.get('container_download', 'ask'),
        }

        # Visualization fields
        visualization_kwargs = {
            'generate_figures': flat_data.get('generate_figures', True),
            'generate_carpetplots': flat_data.get('generate_carpetplots', True),
            'generate_thumbnails': flat_data.get('generate_thumbnails', True),
            'generate_mosaics': flat_data.get('generate_mosaics', True),
            'figure_dpi': flat_data.get('figure_dpi', 100),
            'thumbnail_size': flat_data.get('thumbnail_size', (150, 150)),
        }

        # Analysis fields
        analysis_kwargs = {
            'detect_outliers': flat_data.get('detect_outliers', True),
            'generate_exclusions': flat_data.get('generate_exclusions', False),
            'exclusion_stringency': flat_data.get('exclusion_stringency', 'moderate'),
            'outlier_method': flat_data.get('outlier_method', 'mahalanobis'),
            'consistency_analysis': flat_data.get('consistency_analysis', False),
        }

        # Reporting fields
        reporting_kwargs = {
            'generate_reports': flat_data.get('generate_reports', True),
            'generate_group_plots': flat_data.get('generate_group_plots', True),
            'include_subject_reports': flat_data.get('include_subject_reports', True),
            'include_session_reports': flat_data.get('include_session_reports', True),
            'include_study_report': flat_data.get('include_study_report', True),
        }

        return cls(
            paths=PathConfig(**path_kwargs),
            snapshot=SnapshotConfig(**snapshot_kwargs),
            thresholds=ThresholdConfig(**threshold_kwargs),
            processing=ProcessingConfig(**processing_kwargs),
            motion=MotionConfig(**motion_kwargs),
            visualization=VisualizationConfig(**visualization_kwargs),
            analysis=AnalysisConfig(**analysis_kwargs),
            reporting=ReportingConfig(**reporting_kwargs),
        )

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file.

        Parameters
        ----------
        path : Path
            Path to save configuration file
        """
        data = {
            "paths": {
                "bids_root": str(self.paths.bids_root) if self.paths.bids_root else None,
                "derivatives_dir": str(self.paths.derivatives_dir) if self.paths.derivatives_dir else None,
                "output_dir_name": self.paths.output_dir_name,
                "config_file": str(self.paths.config_file) if self.paths.config_file else None,
                "reuse_run_dir": str(self.paths.reuse_run_dir) if self.paths.reuse_run_dir else None,
                "manifest_path": str(self.paths.manifest_path) if self.paths.manifest_path else None,
                "cache_dir": str(self.paths.cache_dir) if self.paths.cache_dir else None,
                "reference_mask": str(self.paths.reference_mask) if self.paths.reference_mask else None,
            },
            "snapshot": {
                "id": self.snapshot.id,
                "label": self.snapshot.label,
                "source_type": self.snapshot.source_type,
                "description": self.snapshot.description,
                "pipeline_name": self.snapshot.pipeline_name,
                "pipeline_version": self.snapshot.pipeline_version,
            },
            "thresholds": {
                "profile": self.thresholds.profile,
                "fd_threshold": self.thresholds.fd_threshold,
                "fd_median_threshold": self.thresholds.fd_median_threshold,
                "dvars_z_threshold": self.thresholds.dvars_z_threshold,
                "outlier_threshold": self.thresholds.outlier_threshold,
                "slice_intensity_threshold": self.thresholds.slice_intensity_threshold,
                "outlier_metric_threshold": self.thresholds.outlier_metric_threshold,
                "outlier_min_runs": self.thresholds.outlier_min_runs,
                "tsnr_threshold": self.thresholds.tsnr_threshold,
                "coverage_threshold": self.thresholds.coverage_threshold,
            },
            "processing": {
                "n_jobs": self.processing.n_jobs,
                "target_echo": self.processing.target_echo,
                "use_cache": self.processing.use_cache,
                "force_reprocess": self.processing.force_reprocess,
                "dry_run": self.processing.dry_run,
                "use_multiecho": self.processing.use_multiecho,
                "data_source": self.processing.data_source,
                "glob_pattern": self.processing.glob_pattern,
            },
            "motion": {
                "strategy": self.motion.strategy,
                "generation_tool": self.motion.generation_tool,
                "fsl_container_path": str(self.motion.fsl_container_path) if self.motion.fsl_container_path else None,
                "download_policy": self.motion.download_policy,
                "diagnostic_only_for_preprocessed": self.motion.diagnostic_only_for_preprocessed,
            },
            "visualization": {
                "generate_figures": self.visualization.generate_figures,
                "generate_carpetplots": self.visualization.generate_carpetplots,
                "generate_thumbnails": self.visualization.generate_thumbnails,
                "generate_mosaics": self.visualization.generate_mosaics,
                "figure_dpi": self.visualization.figure_dpi,
                "thumbnail_size": list(self.visualization.thumbnail_size),
            },
            "analysis": {
                "detect_outliers": self.analysis.detect_outliers,
                "generate_exclusions": self.analysis.generate_exclusions,
                "exclusion_stringency": self.analysis.exclusion_stringency,
                "outlier_method": self.analysis.outlier_method,
                "consistency_analysis": self.analysis.consistency_analysis,
            },
            "reporting": {
                "generate_reports": self.reporting.generate_reports,
                "generate_group_plots": self.reporting.generate_group_plots,
                "include_subject_reports": self.reporting.include_subject_reports,
                "include_session_reports": self.reporting.include_session_reports,
                "include_study_report": self.reporting.include_study_report,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_threshold_dict(self) -> Dict[str, float]:
        """Get threshold values as dictionary.

        Returns
        -------
        dict
            Dictionary of threshold names and values
        """
        thresholds = self.thresholds.resolve()
        return {
            "dvars_z": thresholds.dvars_std_volume,
            "fd": thresholds.fd_volume,
            "fd_median": thresholds.fd_median,
            "fd_percent": thresholds.fd_percent,
            "dvars_percent": thresholds.dvars_percent,
            "outlier": thresholds.outlier_fraction_volume,
            "outlier_percent": thresholds.outlier_percent,
            "tsnr": thresholds.tsnr_median_min,
            "coverage": thresholds.coverage_signal_fraction_min,
            "slice_intensity": self.thresholds.slice_intensity_threshold,
        }

    def get_snapshot_info(self) -> SnapshotInfo:
        """Return resolved snapshot metadata."""
        root = self.paths.derivatives_dir or self.paths.bids_root
        return self.snapshot.to_snapshot_info(root=root)

    def compute_hash(self) -> str:
        """Compute a stable hash for reproducibility/cache identity."""
        payload = self.to_dict()
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

    def get_data_source_preset(self) -> DataSourcePreset:
        """Get data source as enum.

        Returns
        -------
        DataSourcePreset
            Data source preset enum value
        """
        preset_map = {
            "finalinterp": DataSourcePreset.FINALINTERP,
            "tedana": DataSourcePreset.TEDANA,
            "fmriprep": DataSourcePreset.FMRIPREP,
        }
        return preset_map.get(self.processing.data_source.lower(), DataSourcePreset.FINALINTERP)

    def get_effective_glob_pattern(self) -> str:
        """Get glob pattern, using preset default if not specified.

        Returns
        -------
        str
            Glob pattern for file discovery
        """
        if self.processing.glob_pattern:
            return self.processing.glob_pattern
        return get_glob_pattern(self.get_data_source_preset())

    def is_timeseries_data(self) -> bool:
        """Check if data source has temporal dimension.

        Returns
        -------
        bool
            True if data has temporal dimension
        """
        return True

    def is_manifest_mode(self) -> bool:
        """Check if using manifest-based input.

        Returns
        -------
        bool
            True if using manifest-based input
        """
        return (
            self.manifest is not None
            or self.paths.manifest_path is not None
            or self.processing.data_source == "manifest"
        )

    def get_manifest(self) -> Optional["QAManifest"]:
        """Load and return manifest if in manifest mode.

        Returns
        -------
        Optional[QAManifest]
            Manifest object or None
        """
        # Return directly passed manifest
        if self.manifest is not None:
            return self.manifest

        # Load from file
        if self.paths.manifest_path is None:
            return None

        from fmriqc.io.manifest import QAManifest

        self.manifest = QAManifest.from_file(self.paths.manifest_path)
        return self.manifest

    # ========================================================================
    # Backward compatibility: Property accessors for flat structure
    # ========================================================================

    # Path properties
    @property
    def bids_root(self) -> Optional[Path]:
        """Backward compatibility for paths.bids_root."""
        return self.paths.bids_root

    @bids_root.setter
    def bids_root(self, value: Optional[Path]):
        self.paths.bids_root = value

    @property
    def derivatives_dir(self) -> Optional[Path]:
        """Backward compatibility for paths.derivatives_dir."""
        return self.paths.derivatives_dir

    @derivatives_dir.setter
    def derivatives_dir(self, value: Optional[Path]):
        self.paths.derivatives_dir = value

    @property
    def output_dir_name(self) -> str:
        """Backward compatibility for paths.output_dir_name."""
        return self.paths.output_dir_name

    @output_dir_name.setter
    def output_dir_name(self, value: str):
        self.paths.output_dir_name = value

    @property
    def config_file(self) -> Optional[Path]:
        """Backward compatibility for paths.config_file."""
        return self.paths.config_file

    @config_file.setter
    def config_file(self, value: Optional[Path]):
        self.paths.config_file = value

    @property
    def reuse_run_dir(self) -> Optional[Path]:
        """Backward compatibility for paths.reuse_run_dir."""
        return self.paths.reuse_run_dir

    @reuse_run_dir.setter
    def reuse_run_dir(self, value: Optional[Path]):
        self.paths.reuse_run_dir = value

    @property
    def manifest_path(self) -> Optional[Path]:
        """Backward compatibility for paths.manifest_path."""
        return self.paths.manifest_path

    @manifest_path.setter
    def manifest_path(self, value: Optional[Path]):
        self.paths.manifest_path = value

    # Threshold properties
    @property
    def fd_threshold(self) -> float:
        """Backward compatibility for thresholds.fd_threshold."""
        return self.thresholds.fd_threshold

    @fd_threshold.setter
    def fd_threshold(self, value: float):
        self.thresholds.fd_threshold = value

    @property
    def fd_median_threshold(self) -> float:
        """Backward compatibility for thresholds.fd_median_threshold."""
        return self.thresholds.fd_median_threshold

    @fd_median_threshold.setter
    def fd_median_threshold(self, value: float):
        self.thresholds.fd_median_threshold = value

    @property
    def dvars_z_threshold(self) -> float:
        """Backward compatibility for thresholds.dvars_z_threshold."""
        return self.thresholds.dvars_z_threshold

    @dvars_z_threshold.setter
    def dvars_z_threshold(self, value: float):
        self.thresholds.dvars_z_threshold = value

    @property
    def outlier_threshold(self) -> float:
        """Backward compatibility for thresholds.outlier_threshold."""
        return self.thresholds.outlier_threshold

    @outlier_threshold.setter
    def outlier_threshold(self, value: float):
        self.thresholds.outlier_threshold = value

    @property
    def slice_intensity_threshold(self) -> float:
        """Backward compatibility for thresholds.slice_intensity_threshold."""
        return self.thresholds.slice_intensity_threshold

    @slice_intensity_threshold.setter
    def slice_intensity_threshold(self, value: float):
        self.thresholds.slice_intensity_threshold = value

    @property
    def outlier_metric_threshold(self) -> float:
        """Backward compatibility for thresholds.outlier_metric_threshold."""
        return self.thresholds.outlier_metric_threshold

    @outlier_metric_threshold.setter
    def outlier_metric_threshold(self, value: float):
        self.thresholds.outlier_metric_threshold = value

    @property
    def outlier_min_runs(self) -> int:
        """Backward compatibility for thresholds.outlier_min_runs."""
        return self.thresholds.outlier_min_runs

    @outlier_min_runs.setter
    def outlier_min_runs(self, value: int):
        self.thresholds.outlier_min_runs = value

    # Processing properties
    @property
    def n_jobs(self) -> int:
        """Backward compatibility for processing.n_jobs."""
        return self.processing.n_jobs

    @n_jobs.setter
    def n_jobs(self, value: int):
        self.processing.n_jobs = value

    @property
    def target_echo(self) -> int:
        """Backward compatibility for processing.target_echo."""
        return self.processing.target_echo

    @target_echo.setter
    def target_echo(self, value: int):
        self.processing.target_echo = value

    @property
    def use_cache(self) -> bool:
        """Backward compatibility for processing.use_cache."""
        return self.processing.use_cache

    @use_cache.setter
    def use_cache(self, value: bool):
        self.processing.use_cache = value

    @property
    def force_reprocess(self) -> bool:
        """Backward compatibility for processing.force_reprocess."""
        return self.processing.force_reprocess

    @force_reprocess.setter
    def force_reprocess(self, value: bool):
        self.processing.force_reprocess = value

    @property
    def dry_run(self) -> bool:
        """Backward compatibility for processing.dry_run."""
        return self.processing.dry_run

    @dry_run.setter
    def dry_run(self, value: bool):
        self.processing.dry_run = value

    @property
    def data_source(self) -> str:
        """Backward compatibility for processing.data_source."""
        return self.processing.data_source

    @data_source.setter
    def data_source(self, value: str):
        self.processing.data_source = value

    @property
    def glob_pattern(self) -> str:
        """Backward compatibility for processing.glob_pattern."""
        return self.processing.glob_pattern

    @glob_pattern.setter
    def glob_pattern(self, value: str):
        self.processing.glob_pattern = value

    # Visualization properties
    @property
    def generate_carpetplots(self) -> bool:
        """Backward compatibility for visualization.generate_carpetplots."""
        return self.visualization.generate_carpetplots

    @generate_carpetplots.setter
    def generate_carpetplots(self, value: bool):
        self.visualization.generate_carpetplots = value

    # Analysis properties
    @property
    def exclusion_stringency(self) -> str:
        """Backward compatibility for analysis.exclusion_stringency."""
        return self.analysis.exclusion_stringency

    @exclusion_stringency.setter
    def exclusion_stringency(self, value: str):
        self.analysis.exclusion_stringency = value

    @property
    def generate_motion(self) -> bool:
        """Backward compatibility for old --generate-motion flag."""
        return self.motion.strategy == "generate_if_missing"

    @generate_motion.setter
    def generate_motion(self, value: bool):
        self.motion.strategy = "generate_if_missing" if value else "prefer_provided"

    @property
    def fsl_container_path(self) -> Optional[Path]:
        """Backward compatibility for old processing.fsl_container_path."""
        return self.motion.fsl_container_path

    @fsl_container_path.setter
    def fsl_container_path(self, value: Optional[Path]):
        self.motion.fsl_container_path = value
