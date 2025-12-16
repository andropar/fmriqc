"""Automatic exclusion recommendations for QA results (CIR-212).

This module generates exclusion recommendations at both run and volume levels,
with configurable stringency profiles and export to common formats.
"""

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from .structures import RunResult, SessionResults, StudyResults
from .constants import STRINGENCY_PROFILES, QualityThresholds


class ExclusionStringency(Enum):
    """Exclusion stringency levels."""
    LIBERAL = "liberal"      # Exclude only clearly bad runs
    MODERATE = "moderate"    # Balance between inclusion and quality
    CONSERVATIVE = "conservative"  # Prioritize quality over retention


@dataclass
class ExclusionCriteria:
    """Criteria for run-level exclusion.

    All thresholds can be None to disable that criterion.
    A run is excluded if ANY enabled criterion is met.
    """
    # Motion criteria
    fd_median_max: Optional[float] = None  # Max median FD (mm)
    fd_percent_max: Optional[float] = None  # Max % volumes above FD threshold

    # Signal quality criteria
    tsnr_min: Optional[float] = None  # Min tSNR (absolute)
    tsnr_percentile_min: Optional[float] = None  # Min tSNR percentile within study

    # DVARS criteria
    dvars_percent_max: Optional[float] = None  # Max % volumes with high DVARS

    # Outlier criteria
    outlier_percent_max: Optional[float] = None  # Max % outlier volumes

    # Multivariate
    mahalanobis_max: Optional[float] = None  # Max Mahalanobis distance

    # Coverage
    coverage_min: Optional[float] = None  # Min brain coverage fraction


@dataclass
class ExclusionReason:
    """Reason for excluding a run."""
    criterion: str
    value: float
    threshold: float
    description: str


# Mapping from old enum to new string keys
_STRINGENCY_MAP = {
    ExclusionStringency.LIBERAL: 'lenient',
    ExclusionStringency.MODERATE: 'moderate',
    ExclusionStringency.CONSERVATIVE: 'strict',
}


def _build_criteria_from_profile(stringency: ExclusionStringency) -> ExclusionCriteria:
    """Build ExclusionCriteria from a stringency profile.

    Converts the simplified ExclusionProfile from constants.py into
    the more detailed ExclusionCriteria used for run-level exclusion.
    """
    profile_key = _STRINGENCY_MAP[stringency]
    profile = STRINGENCY_PROFILES[profile_key]

    # Map ExclusionProfile fields to ExclusionCriteria fields
    # Some fields are set based on the profile, others use None (not enforced)
    return ExclusionCriteria(
        fd_median_max=profile.fd_threshold,
        tsnr_min=profile.tsnr_threshold,
        coverage_min=profile.coverage_threshold,
        # Note: dvars_threshold in profile is for volume-level DVARS values,
        # while dvars_percent_max is percentage of volumes exceeding a threshold
        # We'll leave this as None since they measure different things
        dvars_percent_max=None,
        # Other criteria not in the simplified profile
        fd_percent_max=None,
        tsnr_percentile_min=None,
        outlier_percent_max=None,
        mahalanobis_max=None,
    )


@dataclass
class RunExclusion:
    """Exclusion recommendation for a single run."""
    run_id: str
    subject: str
    session: str
    run: str
    excluded: bool
    reasons: List[ExclusionReason] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "subject": self.subject,
            "session": self.session,
            "run": self.run,
            "excluded": self.excluded,
            "reasons": [
                {
                    "criterion": r.criterion,
                    "value": r.value,
                    "threshold": r.threshold,
                    "description": r.description,
                }
                for r in self.reasons
            ],
        }


@dataclass
class VolumeScrubbing:
    """Volume-level scrubbing recommendations for a run."""
    run_id: str
    n_volumes: int
    flagged_volumes: List[int]  # 0-indexed volume numbers
    fd_flagged: List[int]
    dvars_flagged: List[int]
    data_loss_percent: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "n_volumes": int(self.n_volumes),
            "flagged_volumes": [int(v) for v in self.flagged_volumes],
            "fd_flagged": [int(v) for v in self.fd_flagged],
            "dvars_flagged": [int(v) for v in self.dvars_flagged],
            "data_loss_percent": float(self.data_loss_percent),
        }


@dataclass
class ExclusionReport:
    """Complete exclusion report for a study."""
    stringency: str
    criteria: Dict[str, Any]
    run_exclusions: List[RunExclusion]
    volume_scrubbing: List[VolumeScrubbing]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stringency": self.stringency,
            "criteria": self.criteria,
            "run_exclusions": [e.to_dict() for e in self.run_exclusions],
            "volume_scrubbing": [v.to_dict() for v in self.volume_scrubbing],
            "summary": self.summary,
        }


def evaluate_run_exclusion(
    result: RunResult,
    criteria: ExclusionCriteria,
    tsnr_values: Optional[List[float]] = None,
    mahalanobis_distance: Optional[float] = None,
) -> RunExclusion:
    """
    Evaluate whether a run should be excluded based on criteria.

    Parameters
    ----------
    result : RunResult
        QA results for the run
    criteria : ExclusionCriteria
        Exclusion criteria to apply
    tsnr_values : list, optional
        All tSNR values in study (for percentile calculation)
    mahalanobis_distance : float, optional
        Mahalanobis distance for this run

    Returns
    -------
    RunExclusion
        Exclusion recommendation with reasons
    """
    reasons = []
    metrics = result.metrics

    # Check FD median
    if criteria.fd_median_max is not None:
        fd_median = metrics.get("fd_median", 0)
        if fd_median > criteria.fd_median_max:
            reasons.append(ExclusionReason(
                criterion="fd_median",
                value=fd_median,
                threshold=criteria.fd_median_max,
                description=f"Median FD ({fd_median:.3f}mm) exceeds threshold ({criteria.fd_median_max}mm)",
            ))

    # Check FD percent
    if criteria.fd_percent_max is not None:
        fd_percent = metrics.get("fd_percent_above", 0)
        if fd_percent > criteria.fd_percent_max:
            reasons.append(ExclusionReason(
                criterion="fd_percent",
                value=fd_percent,
                threshold=criteria.fd_percent_max,
                description=f"High-motion volumes ({fd_percent:.1f}%) exceed threshold ({criteria.fd_percent_max}%)",
            ))

    # Check absolute tSNR
    if criteria.tsnr_min is not None:
        tsnr = metrics.get("tsnr_median", float("inf"))
        if tsnr < criteria.tsnr_min:
            reasons.append(ExclusionReason(
                criterion="tsnr_min",
                value=tsnr,
                threshold=criteria.tsnr_min,
                description=f"tSNR ({tsnr:.1f}) below minimum threshold ({criteria.tsnr_min})",
            ))

    # Check tSNR percentile
    if criteria.tsnr_percentile_min is not None and tsnr_values:
        tsnr = metrics.get("tsnr_median", 0)
        percentile = 100 * np.mean(np.array(tsnr_values) < tsnr)
        if percentile < criteria.tsnr_percentile_min:
            reasons.append(ExclusionReason(
                criterion="tsnr_percentile",
                value=percentile,
                threshold=criteria.tsnr_percentile_min,
                description=f"tSNR percentile ({percentile:.1f}%) below threshold ({criteria.tsnr_percentile_min}%)",
            ))

    # Check DVARS
    if criteria.dvars_percent_max is not None:
        dvars_percent = metrics.get("dvars_percent_above", 0)
        if dvars_percent > criteria.dvars_percent_max:
            reasons.append(ExclusionReason(
                criterion="dvars_percent",
                value=dvars_percent,
                threshold=criteria.dvars_percent_max,
                description=f"High-DVARS volumes ({dvars_percent:.1f}%) exceed threshold ({criteria.dvars_percent_max}%)",
            ))

    # Check outlier percent
    if criteria.outlier_percent_max is not None:
        outlier_percent = metrics.get("outlier_percent_above", 0)
        if outlier_percent > criteria.outlier_percent_max:
            reasons.append(ExclusionReason(
                criterion="outlier_percent",
                value=outlier_percent,
                threshold=criteria.outlier_percent_max,
                description=f"Outlier volumes ({outlier_percent:.1f}%) exceed threshold ({criteria.outlier_percent_max}%)",
            ))

    # Check Mahalanobis distance
    if criteria.mahalanobis_max is not None and mahalanobis_distance is not None:
        if mahalanobis_distance > criteria.mahalanobis_max:
            reasons.append(ExclusionReason(
                criterion="mahalanobis",
                value=mahalanobis_distance,
                threshold=criteria.mahalanobis_max,
                description=f"Mahalanobis distance ({mahalanobis_distance:.2f}) exceeds threshold ({criteria.mahalanobis_max})",
            ))

    # Check coverage
    if criteria.coverage_min is not None:
        coverage = metrics.get("coverage", 1.0)
        if coverage < criteria.coverage_min:
            reasons.append(ExclusionReason(
                criterion="coverage",
                value=coverage,
                threshold=criteria.coverage_min,
                description=f"Brain coverage ({coverage:.1%}) below threshold ({criteria.coverage_min:.1%})",
            ))

    return RunExclusion(
        run_id=result.info.get_identifier(),
        subject=result.info.subject,
        session=result.info.session,
        run=result.info.run,
        excluded=len(reasons) > 0,
        reasons=reasons,
    )


def compute_volume_scrubbing(
    result: RunResult,
    fd_threshold: float = QualityThresholds.FD_THRESHOLD_DEFAULT,
    dvars_threshold: float = 2.5,  # More lenient than QualityThresholds.DVARS_THRESHOLD for volume scrubbing
) -> VolumeScrubbing:
    """
    Compute volume-level scrubbing recommendations.

    Parameters
    ----------
    result : RunResult
        QA results for the run
    fd_threshold : float
        FD threshold for flagging volumes (mm)
    dvars_threshold : float
        Standardized DVARS threshold for flagging volumes

    Returns
    -------
    VolumeScrubbing
        Volume scrubbing recommendations
    """
    fd_flagged = []
    dvars_flagged = []

    # Get FD series if available
    if "fd" in result.series:
        fd = result.series["fd"]
        fd_flagged = list(np.where(fd > fd_threshold)[0])

    # Get DVARS series if available
    if "dvars_std" in result.series:
        dvars = result.series["dvars_std"]
        # DVARS has NaN at first position
        dvars_clean = np.nan_to_num(dvars, nan=0)
        dvars_flagged = list(np.where(dvars_clean > dvars_threshold)[0])

    # Combine flagged volumes (also flag volume after high FD)
    flagged = set(fd_flagged)
    flagged.update(dvars_flagged)
    # Add volumes immediately after high FD (spin history effects)
    for v in list(fd_flagged):
        if v + 1 < len(result.series.get("fd", [])):
            flagged.add(v + 1)

    flagged_sorted = sorted(flagged)

    # Estimate number of volumes
    n_volumes = len(result.series.get("fd", result.series.get("dvars_std", [])))
    if n_volumes == 0:
        n_volumes = result.metrics.get("n_volumes", 0)

    data_loss = 100 * len(flagged_sorted) / n_volumes if n_volumes > 0 else 0

    return VolumeScrubbing(
        run_id=result.info.get_identifier(),
        n_volumes=n_volumes,
        flagged_volumes=flagged_sorted,
        fd_flagged=fd_flagged,
        dvars_flagged=dvars_flagged,
        data_loss_percent=data_loss,
    )


def generate_exclusion_report(
    results: List[RunResult],
    stringency: ExclusionStringency = ExclusionStringency.MODERATE,
    custom_criteria: Optional[ExclusionCriteria] = None,
    mahalanobis_distances: Optional[Dict[str, float]] = None,
    fd_threshold: float = QualityThresholds.FD_THRESHOLD_DEFAULT,
    dvars_threshold: float = 2.5,  # More lenient than QualityThresholds.DVARS_THRESHOLD for volume scrubbing
) -> ExclusionReport:
    """
    Generate comprehensive exclusion report for all runs.

    Parameters
    ----------
    results : list
        List of RunResult objects
    stringency : ExclusionStringency
        Predefined stringency level
    custom_criteria : ExclusionCriteria, optional
        Custom criteria (overrides stringency profile)
    mahalanobis_distances : dict, optional
        Pre-computed Mahalanobis distances
    fd_threshold : float
        FD threshold for volume scrubbing
    dvars_threshold : float
        DVARS threshold for volume scrubbing

    Returns
    -------
    ExclusionReport
        Complete exclusion report
    """
    # Get criteria
    if custom_criteria is not None:
        criteria = custom_criteria
    else:
        criteria = _build_criteria_from_profile(stringency)

    # Collect all tSNR values for percentile calculation
    tsnr_values = [
        r.metrics.get("tsnr_median", 0)
        for r in results
        if "tsnr_median" in r.metrics
    ]

    # Evaluate each run
    run_exclusions = []
    volume_scrubbing = []

    for result in results:
        # Get Mahalanobis distance if available
        run_id = result.info.get_identifier()
        maha_dist = None
        if mahalanobis_distances:
            maha_dist = mahalanobis_distances.get(run_id)

        # Evaluate exclusion
        exclusion = evaluate_run_exclusion(
            result, criteria, tsnr_values, maha_dist
        )
        run_exclusions.append(exclusion)

        # Compute volume scrubbing
        scrubbing = compute_volume_scrubbing(result, fd_threshold, dvars_threshold)
        volume_scrubbing.append(scrubbing)

    # Generate summary
    n_excluded = sum(1 for e in run_exclusions if e.excluded)
    total_volumes = sum(v.n_volumes for v in volume_scrubbing)
    total_flagged = sum(len(v.flagged_volumes) for v in volume_scrubbing)

    # Count exclusion reasons
    reason_counts: Dict[str, int] = {}
    for excl in run_exclusions:
        for reason in excl.reasons:
            reason_counts[reason.criterion] = reason_counts.get(reason.criterion, 0) + 1

    summary = {
        "total_runs": int(len(results)),
        "excluded_runs": int(n_excluded),
        "retained_runs": int(len(results) - n_excluded),
        "exclusion_rate_percent": float(100 * n_excluded / len(results)) if results else 0.0,
        "total_volumes": int(total_volumes),
        "flagged_volumes": int(total_flagged),
        "volume_data_loss_percent": float(100 * total_flagged / total_volumes) if total_volumes > 0 else 0.0,
        "exclusion_reason_counts": {k: int(v) for k, v in reason_counts.items()},
    }

    # Convert criteria to dict for serialization
    criteria_dict = {
        k: v for k, v in asdict(criteria).items() if v is not None
    }

    return ExclusionReport(
        stringency=stringency.value,
        criteria=criteria_dict,
        run_exclusions=run_exclusions,
        volume_scrubbing=volume_scrubbing,
        summary=summary,
    )


def export_exclusion_list(
    report: ExclusionReport,
    output_path: Path,
    format: str = "tsv",
) -> Path:
    """
    Export run exclusion list to file.

    Parameters
    ----------
    report : ExclusionReport
        Exclusion report
    output_path : Path
        Output file path
    format : str
        Output format: "tsv", "json", or "txt"

    Returns
    -------
    Path
        Path to exported file
    """
    excluded = [e for e in report.run_exclusions if e.excluded]

    if format == "tsv":
        lines = ["subject\tsession\trun\treasons"]
        for e in excluded:
            reasons_str = "; ".join(r.description for r in e.reasons)
            lines.append(f"{e.subject}\t{e.session}\t{e.run}\t{reasons_str}")
        output_path.write_text("\n".join(lines))

    elif format == "json":
        data = {
            "excluded_runs": [e.to_dict() for e in excluded],
            "summary": report.summary,
        }
        output_path.write_text(json.dumps(data, indent=2))

    elif format == "txt":
        # Simple list of run IDs
        lines = [e.run_id for e in excluded]
        output_path.write_text("\n".join(lines))

    return output_path


def export_censor_files(
    report: ExclusionReport,
    output_dir: Path,
    format: str = "fsl",
) -> Dict[str, Path]:
    """
    Export volume-level censor files for each run.

    Parameters
    ----------
    report : ExclusionReport
        Exclusion report
    output_dir : Path
        Output directory
    format : str
        Output format: "fsl" (1=good, 0=bad) or "afni" (0=good, 1=bad)

    Returns
    -------
    dict
        Mapping of run IDs to censor file paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}

    for scrub in report.volume_scrubbing:
        if scrub.n_volumes == 0:
            continue

        # Create censor vector
        if format == "fsl":
            # FSL confound format: 1 = keep, 0 = censor
            censor = np.ones(scrub.n_volumes, dtype=int)
            censor[scrub.flagged_volumes] = 0
        else:  # AFNI
            # AFNI censor format: 0 = keep, 1 = censor
            censor = np.zeros(scrub.n_volumes, dtype=int)
            censor[scrub.flagged_volumes] = 1

        # Write file
        filename = f"{scrub.run_id}_censor.1D"
        filepath = output_dir / filename
        np.savetxt(filepath, censor, fmt="%d")
        paths[scrub.run_id] = filepath

    return paths


def generate_methods_text(report: ExclusionReport) -> str:
    """
    Generate methods section text describing exclusion criteria.

    Parameters
    ----------
    report : ExclusionReport
        Exclusion report

    Returns
    -------
    str
        Methods text
    """
    criteria = report.criteria
    summary = report.summary

    text_parts = [
        f"Quality-based exclusion was performed using {report.stringency} criteria. "
    ]

    # Describe criteria
    criteria_descriptions = []
    if "fd_median_max" in criteria:
        criteria_descriptions.append(f"median framewise displacement > {criteria['fd_median_max']}mm")
    if "fd_percent_max" in criteria:
        criteria_descriptions.append(f">{criteria['fd_percent_max']}% high-motion volumes")
    if "tsnr_min" in criteria:
        criteria_descriptions.append(f"tSNR < {criteria['tsnr_min']}")
    if "tsnr_percentile_min" in criteria:
        criteria_descriptions.append(f"tSNR in bottom {criteria['tsnr_percentile_min']}th percentile")
    if "dvars_percent_max" in criteria:
        criteria_descriptions.append(f">{criteria['dvars_percent_max']}% high-DVARS volumes")
    if "mahalanobis_max" in criteria:
        criteria_descriptions.append(f"Mahalanobis distance > {criteria['mahalanobis_max']}")

    if criteria_descriptions:
        text_parts.append("Runs were excluded if they met any of the following criteria: ")
        text_parts.append(", ".join(criteria_descriptions))
        text_parts.append(". ")

    # Describe results
    text_parts.append(
        f"Of {summary['total_runs']} runs, {summary['excluded_runs']} "
        f"({summary['exclusion_rate_percent']:.1f}%) were excluded. "
    )

    if summary['total_volumes'] > 0:
        text_parts.append(
            f"Volume-level scrubbing flagged {summary['flagged_volumes']} of "
            f"{summary['total_volumes']} volumes ({summary['volume_data_loss_percent']:.1f}%) "
            f"for censoring in remaining runs."
        )

    return "".join(text_parts)
