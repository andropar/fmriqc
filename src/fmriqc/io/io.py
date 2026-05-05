"""File I/O operations, BIDS parsing, and caching."""

import hashlib
import io
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import nibabel as nib
import numpy as np

from fmriqc.core.constants import IOConstants
from fmriqc.io.bids import parse_bids_entities, run_key_from_path
from fmriqc.utils import coerce_scalar as _coerce_scalar
from fmriqc.utils import split_dict_arrays as _split_dict_arrays

from .structures import (
    MaskInfo,
    MotionInfo,
    QAProvenance,
    RunInfo,
    RunKey,
    RunResult,
    SnapshotInfo,
)


def extract_entities(file_name: str) -> Dict[str, Optional[str]]:
    """Extract BIDS entities from filename."""
    parsed = parse_bids_entities(file_name)
    return {key: parsed.get(key) for key in ["sub", "ses", "task", "run", "echo", "part", "desc"]}


def resolve_subject_session(path: Path) -> Tuple[str, str]:
    """Resolve subject and session from path."""
    subject = None
    session = None
    for part in path.parts:
        if part.startswith("sub-"):
            subject = part
        if part.startswith("ses-"):
            session = part
    if subject is None or session is None:
        raise ValueError(f"Cannot resolve subject/session from {path}")
    return subject, session


def create_run_info(run_path: Path) -> RunInfo:
    """Create RunInfo from file path."""
    key = run_key_from_path(run_path)
    entities = parse_bids_entities(run_path)

    return RunInfo(
        path=run_path,
        subject=key.subject,
        session=key.session or "01",
        run=key.run or "01",
        task=key.task,
        echo=key.echo,
        part=key.part,
        desc=entities["desc"],
        acquisition=key.acquisition,
    )


def create_run_info_from_manifest(
    bold_path: Path,
    subject_id: str,
    session_id: str,
    run_label: str,
) -> RunInfo:
    """Create RunInfo from manifest entry.

    Parameters
    ----------
    bold_path : Path
        Path to the BOLD file
    subject_id : str
        Subject identifier from manifest
    session_id : str
        Session identifier from manifest
    run_label : str
        Run label from manifest (e.g., "run-01", "rest")

    Returns
    -------
    RunInfo
        Populated RunInfo structure
    """
    # Try to extract additional entities from filename
    entities = parse_bids_entities(bold_path)

    # Clean up IDs (remove prefixes if present)
    if subject_id.startswith("sub-"):
        subject_id = subject_id[4:]
    if session_id.startswith("ses-"):
        session_id = session_id[4:]

    # Extract run number from label
    run = entities["run"]
    if run is None and run_label:
        if run_label.startswith("run-"):
            run = run_label[4:]
        else:
            run = run_label
    run = run or "00"

    return RunInfo(
        path=bold_path,
        subject=subject_id,
        session=session_id,
        run=run,
        task=entities["task"],
        echo=entities["echo"],
        part=entities["part"],
        desc=entities["desc"],
        acquisition=entities["acq"],
    )


class BIDSPathResolver:
    """Resolve paths following BIDS conventions."""

    def __init__(self, derivatives_dir: Optional[Path] = None):
        """Initialize path resolver.

        Parameters
        ----------
        derivatives_dir : Optional[Path]
            Derivatives directory for locating motion parameters
        """
        self.derivatives_dir = derivatives_dir

    def find_mask(self, run_path: Path, info: RunInfo) -> Optional[Path]:
        """Find brain mask for functional image.

        Parameters
        ----------
        run_path : Path
            Path to the functional image
        info : RunInfo
            Run information structure

        Returns
        -------
        Optional[Path]
            Path to mask file if found
        """
        try:
            name = run_path.name
            parent = run_path.parent

            # Check for final mask
            if name.endswith("_final.nii.gz"):
                candidate = parent / name.replace("_final.nii.gz", "_final_mask.nii.gz")
                if candidate.exists():
                    return candidate

            # Tedana convention
            search_terms = [f"sub-{info.subject}", f"ses-{info.session}", f"run-{info.run}"]
            candidates = [
                p
                for p in parent.glob("*_mask*.nii.gz")
                if all(term in p.name for term in search_terms)
            ]
            if candidates:
                return sorted(candidates)[0]

            return None
        except Exception:
            return None

    def find_motion_params(self, info: RunInfo, target_echo: int) -> Optional[Path]:
        """Find motion correction parameters.

        Parameters
        ----------
        info : RunInfo
            Run information structure
        target_echo : int
            Target echo number

        Returns
        -------
        Optional[Path]
            Path to motion parameters file if found
        """
        if self.derivatives_dir is None:
            return None

        try:
            mc_dir = self.derivatives_dir / f"sub-{info.subject}" / f"ses-{info.session}" / "mc"
            if not mc_dir.exists():
                return None

            echo = info.echo or str(target_echo)
            pieces = [f"sub-{info.subject}", f"ses-{info.session}"]
            if info.task:
                pieces.append(f"task-{info.task}")
            else:
                # Task not in filename (e.g., tedana outputs) - use wildcard
                pieces.append("task-*")
            pieces.append(f"run-{info.run}")
            pieces.append(f"echo-{echo}")
            pieces.append(f"part-{info.part or '*'}")
            prefix = "_".join(pieces)
            pattern = f"{prefix}_bold_*mc.nii.gz.par"

            candidates = sorted(mc_dir.glob(pattern))
            if not candidates and info.part is None:
                backup_pattern = f"{prefix[:-1]}*_bold_*mc.nii.gz.par"
                candidates = sorted(mc_dir.glob(backup_pattern))

            if candidates:
                return candidates[0]
            return None
        except Exception:
            return None


def find_mask_path(run_path: Path, info: RunInfo) -> Optional[Path]:
    """Find mask path for a run.

    Backward compatibility wrapper for BIDSPathResolver.find_mask().
    """
    resolver = BIDSPathResolver()
    return resolver.find_mask(run_path, info)


def locate_motion_params(
    derivatives_dir: Path, info: RunInfo, target_echo: int
) -> Optional[Path]:
    """Locate motion correction parameters.

    Backward compatibility wrapper for BIDSPathResolver.find_motion_params().
    """
    resolver = BIDSPathResolver(derivatives_dir)
    return resolver.find_motion_params(info, target_echo)


def _relative_path(path: Path, base: Path) -> Path:
    try:
        return path.relative_to(base)
    except ValueError:
        return path


def _copy_asset(source: Optional[Path], destination: Path) -> Optional[Path]:
    """Copy a file asset from source to destination."""
    if source is None:
        return None
    try:
        if not source.exists() or not source.is_file():
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        return destination
    except Exception as exc:
        print(f"Warning: Could not copy asset {source} -> {destination}: {exc}")
        return None


class RunResultSerializer:
    """Handle serialization/deserialization of RunResult objects."""

    def serialize_to_disk(self, result: RunResult, output_root: Path) -> Dict[str, Path]:
        """Serialize RunResult to disk (arrays.npz + result.json).

        Parameters
        ----------
        result : RunResult
            Run result to serialize
        output_root : Path
            Root directory for output

        Returns
        -------
        Dict[str, Path]
            Dictionary of asset paths (relative to output_root)
        """
        subject_dir = output_root / f"sub-{result.info.subject}" / f"ses-{result.info.session}"
        run_dir = subject_dir / result.info.get_identifier()
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save arrays
        arrays_path = run_dir / "arrays.npz"
        self._save_arrays(result, arrays_path)

        # Save web-friendly series JSON for report visualization
        series_path = run_dir / "series.json"
        self._save_series_json(result, series_path)

        # Copy all file assets from asset_paths (asset-agnostic approach)
        copied_assets: Dict[str, Path] = {}
        for key, path in result.asset_paths.items():
            if path is None:
                continue
            path_obj = Path(path) if not isinstance(path, Path) else path
            if path_obj.exists() and path_obj.is_file():
                dest = _copy_asset(path_obj, run_dir / path_obj.name)
                if dest is not None:
                    copied_assets[key] = dest

        # Update legacy path attributes for backward compatibility
        result.figure_path = copied_assets.get('figure')
        result.carpetplot_path = copied_assets.get('carpetplot')
        result.thumbnail_path = copied_assets.get('thumbnail')
        result.series_path = series_path

        # Build asset_paths with structural entries + all copied file assets
        asset_paths: Dict[str, Path] = {
            "run_dir": _relative_path(run_dir, output_root),
            "arrays": _relative_path(arrays_path, output_root),
            "metadata": _relative_path(run_dir / "result.json", output_root),
            "series": _relative_path(series_path, output_root),
        }
        for key, path in copied_assets.items():
            asset_paths[key] = _relative_path(path, output_root)

        result.asset_paths = asset_paths

        # Save metadata
        self._save_metadata(result, run_dir / "result.json", output_root)

        return result.asset_paths

    def deserialize_from_disk(
        self, metadata: Dict, source_root: Path, output_root: Path
    ) -> Optional[RunResult]:
        """Reconstruct RunResult from cached metadata and arrays.

        Parameters
        ----------
        metadata : Dict
            Cached metadata dictionary
        source_root : Path
            Root directory where cached data is stored
        output_root : Path
            Root directory for output (may be same as source_root)

        Returns
        -------
        Optional[RunResult]
            Reconstructed RunResult, or None if loading fails
        """
        asset_paths = metadata.get("asset_paths", {})
        arrays_rel = asset_paths.get("arrays")
        if arrays_rel is None:
            return None

        arrays_path = source_root / arrays_rel
        if not arrays_path.exists():
            return None

        # Load arrays
        try:
            arrays_data = self._load_arrays(arrays_path, metadata)
            if arrays_data is None:
                return None
            maps, series_arrays, slice_arrays, mask, mean_vector, affine, header = arrays_data
        except Exception as exc:
            print(f"Warning: Could not load arrays: {exc}")
            return None

        # Reconstruct series and slice_qc
        series_scalars = metadata.get("series_scalars", {})
        series = {**series_arrays, **series_scalars}

        slice_scalars = metadata.get("slice_qc_scalars", {})
        slice_qc = {**slice_arrays, **slice_scalars} if (slice_arrays or slice_scalars) else None

        # Reconstruct info
        info_data = metadata.get("info")
        if not info_data:
            return None
        info = RunInfo.from_dict(info_data)
        snapshot = SnapshotInfo.from_dict(metadata.get("snapshot"))
        run_key = RunKey.from_dict(metadata.get("run_key")) or info.run_key
        provenance = QAProvenance.from_dict(metadata.get("provenance"))
        mask_info = MaskInfo.from_dict(metadata.get("mask_info"))
        motion_info = MotionInfo.from_dict(metadata.get("motion_info"))

        # Resolve asset paths
        figure_rel = asset_paths.get("figure")
        figure_path = source_root / figure_rel if figure_rel else None
        carpet_rel = asset_paths.get("carpetplot")
        carpet_path = source_root / carpet_rel if carpet_rel else None
        thumb_rel = asset_paths.get("thumbnail")
        thumb_path = source_root / thumb_rel if thumb_rel else None

        # Discover series.json path (may exist even if not in metadata)
        series_rel = asset_paths.get("series")
        if series_rel:
            series_path = source_root / series_rel
        else:
            # Try to discover series.json in run directory
            run_dir_rel = asset_paths.get("run_dir")
            if run_dir_rel:
                potential_series = source_root / run_dir_rel / "series.json"
                series_path = potential_series if potential_series.exists() else None
            else:
                series_path = None

        # Resolve spatial map paths and build asset_paths dict for result
        resolved_asset_paths: Dict[str, Path] = {}
        for key, rel_path in asset_paths.items():
            if rel_path is not None:
                resolved_asset_paths[key] = source_root / rel_path

        # Create RunResult
        result = RunResult(
            info=info,
            metrics=metadata.get("metrics", {}),
            flags=metadata.get("flags", {}),
            series=series,
            maps=maps,
            mask=mask,
            affine=affine,
            header=header,
            figure_path=figure_path,
            carpetplot_path=carpet_path,
            thumbnail_path=thumb_path,
            mean_vector=mean_vector,
            warnings=metadata.get("warnings", []),
            slice_qc=slice_qc,
            file_mtime=metadata.get("file_mtime", 0.0),
            processing_time=metadata.get("processing_time", 0.0),
            series_path=series_path,
            asset_paths=resolved_asset_paths,
            snapshot=snapshot,
            run_key=run_key,
            provenance=provenance,
            mask_info=mask_info,
            motion_info=motion_info,
        )

        return result

    def _save_arrays(self, result: RunResult, arrays_path: Path) -> None:
        """Save all numpy arrays to compressed npz file."""
        maps = result.maps or {}
        series_arrays, series_scalars = _split_dict_arrays(result.series)
        slice_arrays, slice_scalars = _split_dict_arrays(result.slice_qc or {})

        arrays_payload: Dict[str, np.ndarray] = {}
        for name, data in maps.items():
            arrays_payload[f"{IOConstants.NAMESPACE_MAPS}{name}"] = data
        for name, data in series_arrays.items():
            arrays_payload[f"{IOConstants.NAMESPACE_SERIES}{name}"] = data
        for name, data in slice_arrays.items():
            arrays_payload[f"{IOConstants.NAMESPACE_SLICE_QC}{name}"] = data

        arrays_payload["mask"] = result.mask.astype(np.uint8)
        arrays_payload["mean_vector"] = result.mean_vector
        arrays_payload["affine"] = result.affine

        header_bytes = getattr(result.header, "binaryblock", None)
        if header_bytes is None:
            header_bytes = result.header.tobytes() if hasattr(result.header, "tobytes") else b""
        arrays_payload["header"] = np.frombuffer(header_bytes, dtype=np.uint8)

        np.savez_compressed(arrays_path, **arrays_payload)

    def _save_series_json(self, result: RunResult, series_path: Path) -> None:
        """Save time series data as web-friendly JSON for report visualization.

        Exports FD, DVARS, global signal and other temporal metrics as JSON
        arrays that can be loaded by the HTML report's JavaScript.
        """
        series_arrays, _ = _split_dict_arrays(result.series)

        # Build JSON-serializable output
        series_data = {
            "run_id": result.info.get_identifier(),
            "n_volumes": int(result.metrics.get("n_volumes", 0)) or None,
            "tr": (
                float(result.metrics.get("tr"))
                if result.metrics.get("tr") is not None
                else None
            ),
            "series": {},
        }

        # Keys to export for web visualization
        export_keys = ["fd", "dvars", "dvars_std", "global_signal", "outlier_fraction"]

        for key in export_keys:
            if key in series_arrays:
                arr = series_arrays[key]
                # Convert to list, round to reasonable precision
                series_data["series"][key] = [
                    round(float(v), 4) if np.isfinite(v) else None
                    for v in arr
                ]
                # Set n_volumes from first series
                if series_data["n_volumes"] is None:
                    series_data["n_volumes"] = len(arr)

        # Add any threshold values from series (scalars)
        for key in ["dvars_threshold", "fd_threshold"]:
            if key in result.series:
                series_data[key] = float(result.series[key])

        # Only write if we have data
        if series_data["series"]:
            with series_path.open("w", encoding="utf-8") as fp:
                json.dump(series_data, fp)

    def _load_arrays(
        self, arrays_path: Path, metadata: Dict
    ) -> Optional[Tuple[Dict, Dict, Dict, np.ndarray, np.ndarray, np.ndarray, Any]]:
        """Load arrays from npz file using metadata.

        Returns
        -------
        Optional[Tuple]
            Tuple of (maps, series_arrays, slice_arrays, mask, mean_vector, affine, header)
            or None if loading fails
        """
        with np.load(arrays_path, allow_pickle=False) as data:
            maps = {}
            for name in metadata.get("maps", []):
                key = f"{IOConstants.NAMESPACE_MAPS}{name}"
                if key in data:
                    maps[name] = data[key]

            series_arrays = {}
            for name in metadata.get("series_arrays", []):
                key = f"{IOConstants.NAMESPACE_SERIES}{name}"
                if key in data:
                    series_arrays[name] = data[key]

            slice_arrays = {}
            for name in metadata.get("slice_qc_arrays", []):
                key = f"{IOConstants.NAMESPACE_SLICE_QC}{name}"
                if key in data:
                    slice_arrays[name] = data[key]

            mask = data.get("mask")
            if mask is None:
                return None
            mask = mask.astype(bool)

            mean_vector = data.get("mean_vector")
            affine = data.get("affine")
            header_arr = data.get("header")

        if mean_vector is None or affine is None or header_arr is None:
            return None

        header_bytes = header_arr.astype(np.uint8).tobytes()
        header = nib.Nifti1Header.from_fileobj(io.BytesIO(header_bytes))

        return maps, series_arrays, slice_arrays, mask, mean_vector, affine, header

    def _save_metadata(self, result: RunResult, metadata_path: Path, output_root: Path) -> None:
        """Save metadata JSON file."""
        maps = result.maps or {}
        series_arrays, series_scalars = _split_dict_arrays(result.series)
        slice_arrays, slice_scalars = _split_dict_arrays(result.slice_qc or {})

        metadata = {
            "schema_version": 2,
            "info": result.info.to_dict(),
            "snapshot": result.snapshot.to_dict() if result.snapshot else None,
            "run_key": result.run_key.to_dict() if result.run_key else result.info.run_key.to_dict(),
            "provenance": result.provenance.to_dict() if result.provenance else None,
            "mask_info": result.mask_info.to_dict() if result.mask_info else None,
            "motion_info": result.motion_info.to_dict() if result.motion_info else None,
            "metrics": result.metrics,
            "flags": result.flags,
            "warnings": result.warnings,
            "file_mtime": result.file_mtime,
            "processing_time": result.processing_time,
            "maps": list(maps.keys()),
            "series_arrays": list(series_arrays.keys()),
            "series_scalars": {k: _coerce_scalar(v) for k, v in series_scalars.items()},
            "slice_qc_arrays": list(slice_arrays.keys()),
            "slice_qc_scalars": {k: _coerce_scalar(v) for k, v in slice_scalars.items()},
            "asset_paths": {
                key: str(value) if value is not None else None
                for key, value in result.asset_paths.items()
            },
        }

        with metadata_path.open("w", encoding="utf-8") as fp:
            json.dump(metadata, fp, indent=2)


def persist_run_assets(result: RunResult, output_root: Path) -> Dict[str, Path]:
    """Persist run result assets (metadata, arrays, figures) for caching.

    Backward compatibility wrapper for RunResultSerializer.serialize_to_disk().
    """
    serializer = RunResultSerializer()
    return serializer.serialize_to_disk(result, output_root)


class QACache:
    """Manages caching of QA results for incremental processing."""

    def __init__(
        self,
        cache_dir: Path,
        reuse_dir: Optional[Path] = None,
        config_hash: Optional[str] = None,
        input_runs: Optional[List[Any]] = None,
    ):
        """Initialize cache manager."""
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "qa_cache.json"
        self.cache_data: Dict[str, Dict] = {}
        self.reuse_dir = reuse_dir
        self.config_hash = config_hash
        self.input_fingerprints = self._build_input_fingerprints(input_runs or [])
        self.reuse_cache_file = (
            reuse_dir / "qa_cache.json" if reuse_dir is not None else None
        )
        self.reuse_cache_data: Dict[str, Dict] = {}
        self.load()

    def _build_input_fingerprints(self, input_runs: List[Any]) -> Dict[str, Dict[str, Any]]:
        fingerprints = {}
        for input_run in input_runs:
            try:
                bold_path = Path(input_run.bold_path)
                key = str(bold_path.resolve())
                motion_path = input_run.confounds_path or input_run.motion_path
                fingerprints[key] = {
                    "snapshot_id": input_run.snapshot.id,
                    "run_key": input_run.run_key.to_string(),
                    "mask": self.file_fingerprint(input_run.mask_path),
                    "motion": self.file_fingerprint(motion_path),
                }
            except Exception:
                continue
        return fingerprints

    def load(self) -> None:
        """Load cache from disk."""
        self.cache_data = self._load_cache_file(self.cache_file)
        if self.reuse_cache_file is not None:
            self.reuse_cache_data = self._load_cache_file(self.reuse_cache_file)

    def _load_cache_file(self, path: Path) -> Dict[str, Dict]:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load cache: {e}")
        return {}

    def save(self) -> None:
        """Save cache to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    @staticmethod
    def file_fingerprint(path: Optional[Path]) -> Dict[str, Any]:
        """Return a lightweight file fingerprint for cache identity."""
        if path is None:
            return {"path": None, "exists": False}
        try:
            resolved = path.resolve()
            stat = resolved.stat()
            return {
                "path": str(resolved),
                "exists": True,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            }
        except OSError:
            return {"path": str(path), "exists": False}

    def get_cache_key(self, run_path: Path) -> str:
        """Generate cache key for a run."""
        try:
            input_key = str(run_path.resolve())
        except OSError:
            input_key = str(run_path)
        payload = {
            "cache_version": IOConstants.CACHE_VERSION,
            "bold": self.file_fingerprint(run_path),
            "input": self.input_fingerprints.get(input_key),
            "config_hash": self.config_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def get(self, run_path: Path) -> Optional[Dict]:
        """Get cached result for a run."""
        entry, _ = self._get_metadata_with_source(run_path)
        return entry

    def set(self, run_path: Path, result: RunResult) -> None:
        """Cache result for a run."""
        key = self.get_cache_key(run_path)
        if not result.asset_paths:
            try:
                persist_run_assets(result, self.cache_dir)
            except Exception as exc:
                print(f"Warning: Could not persist run assets for cache: {exc}")
        self.cache_data[key] = result.to_cache()

    def needs_reprocessing(self, run_path: Path) -> bool:
        """Check if run needs reprocessing."""
        cached, _ = self._get_metadata_with_source(run_path)
        if cached is None:
            return True

        try:
            current_mtime = run_path.stat().st_mtime
            return RunResult.needs_reprocessing(cached, current_mtime)
        except Exception:
            return True

    def clear(self) -> None:
        """Clear all cache data."""
        self.cache_data = {}
        if self.cache_file.exists():
            self.cache_file.unlink()

    def _get_metadata_with_source(self, run_path: Path) -> Tuple[Optional[Dict], Optional[Path]]:
        key = self.get_cache_key(run_path)
        if key in self.cache_data:
            return self.cache_data[key], self.cache_dir
        if key in self.reuse_cache_data:
            return self.reuse_cache_data[key], self.reuse_dir
        return None, None

    def load_run_result(self, run_path: Path, output_root: Path) -> Optional[RunResult]:
        """Load a cached run result, materializing assets into the new output directory."""

        metadata, source_root = self._get_metadata_with_source(run_path)
        if metadata is None or source_root is None:
            return None

        # Delegate deserialization to serializer
        serializer = RunResultSerializer()
        result = serializer.deserialize_from_disk(metadata, source_root, output_root)
        if result is None:
            print(f"Warning: Could not deserialize cached result for {run_path}; skipping reuse")
            return None

        # Handle asset copying if output directory differs from source
        if source_root.resolve() != output_root.resolve():
            try:
                result.asset_paths = serializer.serialize_to_disk(result, output_root)
            except Exception as exc:
                print(f"Warning: Could not materialize cached assets for {run_path}: {exc}")
                return None
        else:
            # When loading from same directory, preserve asset_paths from metadata
            asset_paths = metadata.get("asset_paths", {})
            result.asset_paths = asset_paths

        return result


def load_all_results_from_previous_run(previous_run_dir: Path, output_dir: Path) -> List[RunResult]:
    """Load all RunResult objects from a previous QA run directory.

    Parameters
    ----------
    previous_run_dir : Path
        Path to the previous QA run directory containing qa_cache.json
    output_dir : Path
        Output directory where results should be loaded (can be same as previous_run_dir)

    Returns
    -------
    List[RunResult]
        List of all loaded run results
    """
    cache_file = previous_run_dir / "qa_cache.json"
    if not cache_file.exists():
        raise ValueError(f"Cache file not found in previous run directory: {cache_file}")

    cache_data = {}
    try:
        with open(cache_file, encoding="utf-8") as f:
            cache_data = json.load(f)
    except Exception as e:
        raise ValueError(f"Could not load cache file: {e}") from e

    if not cache_data:
        print("Warning: Cache file is empty")
        return []

    # Create a temporary cache instance to use its loading logic
    temp_cache = QACache(output_dir, reuse_dir=previous_run_dir)

    results = []
    for cache_key, metadata in cache_data.items():
        # Extract run path from metadata
        info_data = metadata.get("info")
        if not info_data:
            print(f"Warning: Cache entry {cache_key} missing info; skipping")
            continue

        run_path_str = info_data.get("path")
        if not run_path_str:
            print(f"Warning: Cache entry {cache_key} missing path; skipping")
            continue
        run_path = Path(run_path_str)

        # Load the result
        result = temp_cache.load_run_result(run_path, output_dir)
        if result is None:
            print(f"Warning: Could not load result for {run_path}; skipping")
            continue

        results.append(result)

    return results


def load_default_derivatives(config_path: Path) -> Optional[Path]:
    """Load default derivatives directory from config file."""
    try:
        with config_path.open("r", encoding="utf-8") as fp:
            cfg = json.load(fp)
        return Path(cfg["paths"]["derivatives_dir"]).expanduser()
    except Exception:
        return None


def images_same_grid(
    data_img: nib.Nifti1Image,
    mask_img: nib.Nifti1Image,
    affine_tol: float = 1e-3,
) -> bool:
    """Return true if shape and affine match."""
    return (
        data_img.shape[:3] == mask_img.shape[:3]
        and np.allclose(data_img.affine, mask_img.affine, atol=affine_tol)
    )


def ensure_mask_aligned(
    data_img: nib.Nifti1Image,
    mask_img: nib.Nifti1Image,
    *,
    allow_resample: bool = True,
) -> Tuple[nib.Nifti1Image, bool]:
    """Ensure mask is on the same grid as data, returning resample status."""
    from nilearn import image as nilearn_image

    if images_same_grid(data_img, mask_img):
        return mask_img, False

    if not allow_resample:
        raise ValueError("Mask grid/affine does not match BOLD image")

    return nilearn_image.resample_to_img(mask_img, data_img, interpolation="nearest"), True
