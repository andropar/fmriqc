"""Data structures for snapshot QA inputs and results."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import numpy as np

from fmriqc.utils import coerce_scalar, split_dict_arrays

SnapshotSourceType = Literal["raw", "preprocessed", "denoised", "smoothed", "custom"]
MotionSourceType = Literal[
    "provided_confounds",
    "provided_fsl_par",
    "generated_from_snapshot_mcflirt",
    "generated_from_raw_mcflirt",
    "copied_from_pair",
    "residual_generated_from_snapshot_mcflirt",
    "missing",
]
MaskSourceType = Literal["manifest", "bids_derivative", "reference", "auto_threshold", "missing"]


@dataclass(frozen=True)
class SnapshotInfo:
    """Identity and provenance for one concrete dataset snapshot."""

    id: str
    label: str = ""
    source_type: SnapshotSourceType = "custom"
    description: str = ""
    root: Optional[Path] = None
    pipeline_name: Optional[str] = None
    pipeline_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["root"] = str(self.root) if self.root else None
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SnapshotInfo":
        if not data:
            return cls(id="legacy")
        payload = dict(data)
        if payload.get("root"):
            payload["root"] = Path(payload["root"])
        return cls(**payload)


@dataclass(frozen=True)
class RunKey:
    """Canonical logical run identity, independent of snapshot and file path."""

    subject: str
    session: Optional[str] = None
    task: Optional[str] = None
    run: Optional[str] = None
    echo: Optional[str] = None
    acquisition: Optional[str] = None
    part: Optional[str] = None

    @staticmethod
    def _strip(value: Optional[str], prefix: str) -> Optional[str]:
        if value is None:
            return None
        return value[len(prefix):] if value.startswith(prefix) else value

    def normalized(self) -> "RunKey":
        return RunKey(
            subject=self._strip(self.subject, "sub-") or self.subject,
            session=self._strip(self.session, "ses-"),
            task=self._strip(self.task, "task-"),
            run=self._strip(self.run, "run-"),
            echo=self._strip(self.echo, "echo-"),
            acquisition=self._strip(self.acquisition, "acq-"),
            part=self._strip(self.part, "part-"),
        )

    def to_string(self) -> str:
        key = self.normalized()
        parts = [f"sub-{key.subject}"]
        if key.session:
            parts.append(f"ses-{key.session}")
        if key.task:
            parts.append(f"task-{key.task}")
        if key.run:
            parts.append(f"run-{key.run}")
        if key.echo:
            parts.append(f"echo-{key.echo}")
        if key.acquisition:
            parts.append(f"acq-{key.acquisition}")
        if key.part:
            parts.append(f"part-{key.part}")
        return "_".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["RunKey"]:
        if not data:
            return None
        return cls(**data)


@dataclass
class MotionInfo:
    """Motion-input provenance for a run."""

    path: Optional[Path] = None
    source: MotionSourceType = "missing"
    fd_source: str = "none"
    generated: bool = False
    diagnostic_only: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path) if self.path else None
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "MotionInfo":
        if not data:
            return cls()
        payload = dict(data)
        if payload.get("path"):
            payload["path"] = Path(payload["path"])
        return cls(**payload)


@dataclass
class MaskInfo:
    """Mask-input provenance and grid relationship for a run."""

    path: Optional[Path] = None
    source: MaskSourceType = "missing"
    resampled: bool = False
    same_shape: bool = False
    same_affine: bool = False
    voxel_count: Optional[int] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path) if self.path else None
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "MaskInfo":
        if not data:
            return cls()
        payload = dict(data)
        if payload.get("path"):
            payload["path"] = Path(payload["path"])
        return cls(**payload)


@dataclass
class InputRun:
    """Resolved inputs needed to assess one run in one snapshot."""

    snapshot: SnapshotInfo
    run_key: RunKey
    bold_path: Path
    mask_path: Optional[Path] = None
    motion_path: Optional[Path] = None
    confounds_path: Optional[Path] = None
    label: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_identifier(self) -> str:
        return self.run_key.to_string()


@dataclass
class QAProvenance:
    """Fully resolved provenance for one processed QA result."""

    snapshot: SnapshotInfo
    run_key: RunKey
    bold_path: Path
    mask_info: MaskInfo
    motion_info: MotionInfo
    config_hash: str
    software_version: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "run_key": asdict(self.run_key),
            "bold_path": str(self.bold_path),
            "mask_info": self.mask_info.to_dict(),
            "motion_info": self.motion_info.to_dict(),
            "config_hash": self.config_hash,
            "software_version": self.software_version,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["QAProvenance"]:
        if not data:
            return None
        return cls(
            snapshot=SnapshotInfo.from_dict(data.get("snapshot")),
            run_key=RunKey.from_dict(data.get("run_key")) or RunKey(subject="unknown"),
            bold_path=Path(data.get("bold_path", "")),
            mask_info=MaskInfo.from_dict(data.get("mask_info")),
            motion_info=MotionInfo.from_dict(data.get("motion_info")),
            config_hash=data.get("config_hash", ""),
            software_version=data.get("software_version", ""),
            warnings=list(data.get("warnings", [])),
        )


@dataclass
class RunInfo:
    """Information about a single fMRI run."""

    path: Path
    subject: str
    session: str = "01"
    run: str = "01"
    task: Optional[str] = None
    echo: Optional[str] = None
    part: Optional[str] = None
    desc: Optional[str] = None
    acquisition: Optional[str] = None
    snapshot_id: str = "snapshot"

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
        return self.run_key.to_string()

    @property
    def run_key(self) -> RunKey:
        """Return canonical run identity."""
        return RunKey(
            subject=self.subject,
            session=self.session,
            task=self.task,
            run=self.run,
            echo=self.echo,
            acquisition=self.acquisition,
            part=self.part,
        )


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
    file_mtime: float = 0.0  # File modification time
    processing_time: float = 0.0  # Time to process in seconds
    asset_paths: Dict[str, Path] = field(default_factory=dict)
    series_path: Optional[Path] = None  # Path to series.json for web visualization
    snapshot: Optional[SnapshotInfo] = None
    run_key: Optional[RunKey] = None
    provenance: Optional[QAProvenance] = None
    mask_info: Optional[MaskInfo] = None
    motion_info: Optional[MotionInfo] = None

    def to_cache(self) -> Dict:
        """
        Convert to cacheable dictionary (without large arrays).
        Only stores metrics, flags, warnings, and metadata.
        """
        series_arrays, series_scalars = split_dict_arrays(self.series)
        slice_arrays, slice_scalars = split_dict_arrays(self.slice_qc or {})

        return {
            "schema_version": 2,
            "info": self.info.to_dict(),
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "run_key": asdict(self.run_key) if self.run_key else asdict(self.info.run_key),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "mask_info": self.mask_info.to_dict() if self.mask_info else None,
            "motion_info": self.motion_info.to_dict() if self.motion_info else None,
            "metrics": self.metrics,
            "flags": self.flags,
            "warnings": self.warnings,
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
