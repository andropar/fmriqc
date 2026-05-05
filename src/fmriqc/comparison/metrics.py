"""Comparison metrics for paired snapshot QA results."""

from __future__ import annotations

import numpy as np

from fmriqc.comparison.structures import MetricDelta, RunComparison, RunPair

METRIC_DIRECTIONS = {
    "tsnr_median": "higher_better",
    "coverage_signal_fraction": "higher_better",
    "fd_median": "lower_better",
    "fd_percent_above": "lower_better",
    "dvars_std_median": "lower_better",
    "dvars_percent_above": "lower_better",
    "outlier_percent_above": "lower_better",
    "gcor": "contextual",
    "apparent_smoothness_fwhm": "contextual",
    "ar1_median": "contextual",
    "mask_voxel_count": "contextual",
}


def _float_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def scalar_delta(metric: str, left_value, right_value) -> MetricDelta:
    left = _float_or_none(left_value)
    right = _float_or_none(right_value)
    if left is None or right is None:
        return MetricDelta(metric, left, right, None, None)
    delta = right - left
    percent = (delta / abs(left) * 100.0) if left != 0 else None
    return MetricDelta(metric, left, right, delta, percent)


def compare_series(left, right) -> dict:
    """Compare series with length-mismatch warnings."""
    out = {}
    warnings = []
    for key in ["fd", "dvars_std", "global_signal", "outlier_fraction"]:
        if key not in left.series or key not in right.series:
            continue
        l_arr = np.asarray(left.series[key], dtype=float)
        r_arr = np.asarray(right.series[key], dtype=float)
        n_overlap = min(len(l_arr), len(r_arr))
        length_match = len(l_arr) == len(r_arr)
        if not length_match:
            warnings.append(f"{key} length mismatch: {len(l_arr)} vs {len(r_arr)}")
        if n_overlap < 2:
            corr = None
        else:
            left_values = l_arr[:n_overlap]
            right_values = r_arr[:n_overlap]
            valid = np.isfinite(left_values) & np.isfinite(right_values)
            corr = (
                float(np.corrcoef(left_values[valid], right_values[valid])[0, 1])
                if valid.sum() > 1
                else None
            )
        out[key] = {
            "n_left": int(len(l_arr)),
            "n_right": int(len(r_arr)),
            "n_overlap": int(n_overlap),
            "length_match": length_match,
            "correlation": corr,
        }
    out["warnings"] = warnings
    return out


def dice(a: np.ndarray, b: np.ndarray) -> float:
    denom = a.sum() + b.sum()
    return float(2 * np.logical_and(a, b).sum() / denom) if denom else float("nan")


def compare_pair(pair: RunPair) -> RunComparison:
    """Compute scalar and series summaries for one paired run."""
    deltas = {
        metric: scalar_delta(metric, pair.left.metrics.get(metric), pair.right.metrics.get(metric))
        for metric in METRIC_DIRECTIONS
    }

    better_votes = 0
    worse_votes = 0
    for metric, direction in METRIC_DIRECTIONS.items():
        delta = deltas[metric].delta
        if delta is None or direction == "contextual" or abs(delta) < 1e-9:
            continue
        if (direction == "higher_better" and delta > 0) or (direction == "lower_better" and delta < 0):
            better_votes += 1
        else:
            worse_votes += 1

    if better_votes and not worse_votes:
        status = "mostly_better"
    elif worse_votes and not better_votes:
        status = "mostly_worse"
    elif better_votes or worse_votes:
        status = "mixed"
    else:
        status = "unchanged"

    warnings = list(pair.warnings)
    series = compare_series(pair.left, pair.right)
    warnings.extend(series.get("warnings", []))

    if pair.left.mask.shape == pair.right.mask.shape and np.allclose(pair.left.affine, pair.right.affine, atol=1e-3):
        deltas["mask_dice"] = MetricDelta("mask_dice", None, dice(pair.left.mask, pair.right.mask), None, None)
    else:
        warnings.append("Spatial grid differs; spatial deltas disabled")

    return RunComparison(
        run_key=pair.run_key,
        left_snapshot_id=(pair.left.snapshot.id if pair.left.snapshot else "left"),
        right_snapshot_id=(pair.right.snapshot.id if pair.right.snapshot else "right"),
        metric_deltas=deltas,
        warnings=warnings,
        status=status,
        series=series,
    )
