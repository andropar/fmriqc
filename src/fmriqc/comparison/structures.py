"""Data structures for snapshot comparison."""

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from fmriqc.io.structures import RunKey, RunResult


@dataclass
class RunPair:
    run_key: RunKey
    left: RunResult
    right: RunResult
    warnings: List[str] = field(default_factory=list)


@dataclass
class PairingReport:
    paired: List[RunPair]
    left_only: List[RunKey]
    right_only: List[RunKey]
    duplicates_left: Dict[str, List[RunResult]]
    duplicates_right: Dict[str, List[RunResult]]
    warnings: List[str] = field(default_factory=list)


@dataclass
class MetricDelta:
    metric: str
    left: Optional[float]
    right: Optional[float]
    delta: Optional[float]
    percent_delta: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunComparison:
    run_key: RunKey
    left_snapshot_id: str
    right_snapshot_id: str
    metric_deltas: Dict[str, MetricDelta]
    warnings: List[str] = field(default_factory=list)
    status: str = "incomplete"
    series: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_key": self.run_key.to_dict(),
            "run_id": self.run_key.to_string(),
            "left_snapshot_id": self.left_snapshot_id,
            "right_snapshot_id": self.right_snapshot_id,
            "metric_deltas": {key: value.to_dict() for key, value in self.metric_deltas.items()},
            "warnings": list(self.warnings),
            "status": self.status,
            "series": self.series,
        }
