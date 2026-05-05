"""Load existing snapshot QA outputs for comparison."""

import json
from pathlib import Path
from typing import List, Tuple

from fmriqc.io.io import RunResultSerializer
from fmriqc.io.structures import RunResult, SnapshotInfo


def load_snapshot_results(qa_dir: Path) -> Tuple[SnapshotInfo, List[RunResult]]:
    """Load snapshot metadata and all serialized run results from a QA output."""
    qa_dir = Path(qa_dir)
    snapshot_path = qa_dir / "snapshot.json"
    warnings = []
    if snapshot_path.exists():
        snapshot = SnapshotInfo.from_dict(json.loads(snapshot_path.read_text()))
    else:
        snapshot = SnapshotInfo(id=qa_dir.name)
        warnings.append("snapshot.json missing; using directory name as snapshot id")

    serializer = RunResultSerializer()
    results = []
    for metadata_path in sorted(qa_dir.glob("sub-*/ses-*/*/result.json")):
        metadata = json.loads(metadata_path.read_text())
        result = serializer.deserialize_from_disk(metadata, qa_dir, qa_dir)
        if result is None:
            continue
        if result.snapshot is None or result.snapshot.id == "legacy":
            result.snapshot = snapshot
        if warnings:
            result.warnings.extend(warnings)
        results.append(result)

    if not results:
        cache_path = qa_dir / "qa_cache.json"
        if cache_path.exists():
            cache_data = json.loads(cache_path.read_text())
            for metadata in cache_data.values():
                result = serializer.deserialize_from_disk(metadata, qa_dir, qa_dir)
                if result is not None:
                    result.snapshot = result.snapshot or snapshot
                    results.append(result)

    return snapshot, results
