"""Single source of truth for QA threshold profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

ThresholdProfileName = Literal["lenient", "default", "strict", "custom"]


@dataclass(frozen=True)
class ResolvedThresholds:
    """Resolved thresholds used for one reproducible QA run."""

    profile: ThresholdProfileName = "default"
    fd_volume: float = 0.3
    fd_median: float = 0.2
    fd_percent: float = 20.0
    dvars_std_volume: float = 2.5
    dvars_percent: float = 15.0
    outlier_fraction_volume: float = 0.02
    outlier_percent: float = 10.0
    tsnr_median_min: float = 30.0
    coverage_signal_fraction_min: float = 0.85
    mask_max_components: int = 3
    slice_outlier_max: float = 0.25
    hyperintense_slice_max: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILES: dict[str, ResolvedThresholds] = {
    "strict": ResolvedThresholds(
        profile="strict",
        fd_volume=0.3,
        fd_median=0.2,
        tsnr_median_min=40.0,
        coverage_signal_fraction_min=0.90,
    ),
    "default": ResolvedThresholds(profile="default"),
    "lenient": ResolvedThresholds(
        profile="lenient",
        fd_volume=0.5,
        fd_median=0.3,
        tsnr_median_min=20.0,
        coverage_signal_fraction_min=0.75,
    ),
}


def resolve_thresholds(profile: str = "default", **overrides: Any) -> ResolvedThresholds:
    """Resolve a profile plus optional field overrides."""
    base = PROFILES.get(profile, PROFILES["default"])
    clean_overrides = {
        key: value
        for key, value in overrides.items()
        if value is not None and key in ResolvedThresholds.__dataclass_fields__
    }
    if clean_overrides:
        clean_overrides["profile"] = "custom" if profile not in PROFILES else base.profile
        return replace(base, **clean_overrides)
    return base
