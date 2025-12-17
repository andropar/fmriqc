"""Data structures for QA results."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from fmriqa.utils import split_dict_arrays, coerce_scalar


@dataclass
class RunInfo:
    """Information about a single fMRI run."""

    path: Path
    subject: str
    session: str
    run: str
    task: Optional[str]
    echo: Optional[str]
    part: Optional[str]
    desc: Optional[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary with path as string."""
        d = asdict(self)
        d["path"] = str(self.path)
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "RunInfo":
        """Create from dictionary."""
        data = data.copy()
        data["path"] = Path(data["path"])
        return cls(**data)

    def get_identifier(self) -> str:
        """Get unique identifier for this run."""
        parts = [f"sub-{self.subject}", f"ses-{self.session}", f"run-{self.run}"]
        if self.task:
            parts.append(f"task-{self.task}")
        if self.echo:
            parts.append(f"echo-{self.echo}")
        return "_".join(parts)


@dataclass
class RunResult:
    """Results from QA analysis of a single run."""

    info: RunInfo
    metrics: Dict[str, float]
    flags: Dict[str, bool]
    series: Dict[str, np.ndarray]
    maps: Dict[str, np.ndarray]
    mask: np.ndarray
    affine: np.ndarray
    header: object  # nib.Nifti1Header
    figure_path: Path
    carpetplot_path: Optional[Path]
    thumbnail_path: Optional[Path]
    mean_vector: np.ndarray
    warnings: List[str] = field(default_factory=list)
    slice_qc: Optional[Dict[str, np.ndarray]] = None
    sdc_assessed: bool = False
    events_validated: bool = False
    file_mtime: float = 0.0  # File modification time
    processing_time: float = 0.0  # Time to process in seconds
    asset_paths: Dict[str, Path] = field(default_factory=dict)

    def to_cache(self) -> Dict:
        """
        Convert to cacheable dictionary (without large arrays).
        Only stores metrics, flags, warnings, and metadata.
        """
        series_arrays, series_scalars = split_dict_arrays(self.series)
        slice_arrays, slice_scalars = split_dict_arrays(self.slice_qc or {})

        return {
            "info": self.info.to_dict(),
            "metrics": self.metrics,
            "flags": self.flags,
            "warnings": self.warnings,
            "sdc_assessed": self.sdc_assessed,
            "events_validated": self.events_validated,
            "file_mtime": self.file_mtime,
            "processing_time": self.processing_time,
            "maps": list(self.maps.keys()),
            "series_arrays": list(series_arrays.keys()),
            "series_scalars": {
                key: coerce_scalar(value) for key, value in series_scalars.items()
            },
            "slice_qc_arrays": list(slice_arrays.keys()),
            "slice_qc_scalars": {
                key: coerce_scalar(value) for key, value in slice_scalars.items()
            },
            "asset_paths": {
                key: str(value) if value is not None else None
                for key, value in self.asset_paths.items()
            },
        }

    @classmethod
    def needs_reprocessing(cls, cached_data: Dict, current_mtime: float) -> bool:
        """Check if run needs reprocessing based on modification time."""
        return cached_data.get("file_mtime", 0) < current_mtime


@dataclass
class SessionResults:
    """Aggregated results for a session."""

    subject: str
    session: str
    runs: List[RunResult]
    aggregate_metrics: Dict[str, float] = field(default_factory=dict)
    consistency_metrics: Dict[str, float] = field(default_factory=dict)
    outlier_runs: List[str] = field(default_factory=list)
    aggregate_figure_path: Optional[Path] = None
    aggregate_map_paths: Dict[str, Path] = field(default_factory=dict)

    def get_identifier(self) -> str:
        """Get session identifier."""
        return f"sub-{self.subject}_ses-{self.session}"


@dataclass
class SubjectResults:
    """Aggregated results for a subject."""

    subject: str
    sessions: List[SessionResults]
    aggregate_map_paths: Dict[str, Path] = field(default_factory=dict)
    aggregate_figure_path: Optional[Path] = None

    def get_identifier(self) -> str:
        """Get subject identifier."""
        return f"sub-{self.subject}"


@dataclass
class StudyResults:
    """Overall study results."""

    subjects: List[SubjectResults]
    overall_metrics: Dict[str, float] = field(default_factory=dict)
    overall_outliers: List[str] = field(default_factory=list)
    outlier_report: Dict[str, Any] = field(default_factory=dict)  # Full outlier analysis
    exclusion_report: Optional[Any] = None  # ExclusionReport for automatic recommendations
    processing_summary: Dict[str, int] = field(default_factory=dict)
    aggregate_map_paths: Dict[str, Path] = field(default_factory=dict)
    aggregate_figure_path: Optional[Path] = None
    group_plots: Dict[str, Path] = field(default_factory=dict)

    # Analysis metadata for provenance and reproducibility
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)  # Config, versions, timestamps
