"""Pair run results across snapshots by canonical RunKey."""

from collections import defaultdict
from typing import Dict, List

from fmriqc.comparison.structures import PairingReport, RunPair
from fmriqc.io.structures import RunKey, RunResult


def _key(result: RunResult) -> RunKey:
    return (result.run_key or result.info.run_key).normalized()


def _index(results: List[RunResult]) -> Dict[str, List[RunResult]]:
    indexed: Dict[str, List[RunResult]] = defaultdict(list)
    for result in results:
        indexed[_key(result).to_string()].append(result)
    return indexed


def pair_results(left: List[RunResult], right: List[RunResult]) -> PairingReport:
    """Pair by normalized RunKey, reporting missing and duplicate keys."""
    left_index = _index(left)
    right_index = _index(right)
    duplicates_left = {key: value for key, value in left_index.items() if len(value) > 1}
    duplicates_right = {key: value for key, value in right_index.items() if len(value) > 1}

    paired = []
    left_only = []
    right_only = []
    warnings = []

    all_keys = sorted(set(left_index) | set(right_index))
    for key in all_keys:
        left_items = left_index.get(key, [])
        right_items = right_index.get(key, [])
        if len(left_items) > 1 or len(right_items) > 1:
            warnings.append(f"Duplicate run key not paired: {key}")
            continue
        if left_items and right_items:
            run_key = _key(left_items[0])
            paired.append(RunPair(run_key=run_key, left=left_items[0], right=right_items[0]))
        elif left_items:
            left_only.append(_key(left_items[0]))
        elif right_items:
            right_only.append(_key(right_items[0]))

    return PairingReport(
        paired=paired,
        left_only=left_only,
        right_only=right_only,
        duplicates_left=duplicates_left,
        duplicates_right=duplicates_right,
        warnings=warnings,
    )
