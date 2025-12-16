"""File I/O operations, BIDS parsing, and caching."""

import hashlib
import io
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import nibabel as nib
import numpy as np

from .config import QAConfig
from .constants import IOConstants
from .structures import RunInfo, RunResult
from .utils import split_dict_arrays as _split_dict_arrays, coerce_scalar as _coerce_scalar


def extract_entities(file_name: str) -> Dict[str, Optional[str]]:
    """Extract BIDS entities from filename."""
    entities: Dict[str, Optional[str]] = {
        "sub": None,
        "ses": None,
        "task": None,
        "run": None,
        "echo": None,
        "part": None,
        "desc": None,
    }
    for part in file_name.split("_"):
        for key in entities:
            prefix = f"{key}-"
            if part.startswith(prefix):
                entities[key] = part[len(prefix) :]
                break
    return entities


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
    entities = extract_entities(run_path.stem)
    subject = entities["sub"] or resolve_subject_session(run_path)[0].split("-")[1]
    session = entities["ses"] or resolve_subject_session(run_path)[1].split("-")[1]
    run = entities["run"] or "00"

    return RunInfo(
        path=run_path,
        subject=subject,
        session=session,
        run=run,
        task=entities["task"],
        echo=entities["echo"],
        part=entities["part"],
        desc=entities["desc"],
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
    entities = extract_entities(bold_path.stem)

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
    )


def find_mask_path(run_path: Path, info: RunInfo) -> Optional[Path]:
    """Find mask path for a run."""
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


def locate_motion_params(
    derivatives_dir: Path, info: RunInfo, target_echo: int
) -> Optional[Path]:
    """Locate motion correction parameters."""
    try:
        mc_dir = derivatives_dir / f"sub-{info.subject}" / f"ses-{info.session}" / "mc"
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


def find_events_file(derivatives_dir: Path, info: RunInfo) -> Optional[Path]:
    """Find BIDS events.tsv file."""
    try:
        # Look in raw BIDS directory
        bids_dir = derivatives_dir.parent
        if "derivatives" in str(derivatives_dir):
            parts = derivatives_dir.parts
            if "derivatives" in parts:
                idx = parts.index("derivatives")
                bids_dir = Path(*parts[:idx])

        sub_ses_dir = bids_dir / f"sub-{info.subject}" / f"ses-{info.session}" / "func"
        if not sub_ses_dir.exists():
            return None

        pattern_parts = [f"sub-{info.subject}", f"ses-{info.session}"]
        if info.task:
            pattern_parts.append(f"task-{info.task}")
        pattern_parts.append(f"run-{info.run}")
        pattern = "_".join(pattern_parts) + "_events.tsv"

        candidates = list(sub_ses_dir.glob(pattern))
        if candidates:
            return candidates[0]
        return None
    except Exception:
        return None


def find_fieldmap_data(
    derivatives_dir: Path, info: RunInfo
) -> Optional[Dict[str, Path]]:
    """Find fieldmap-related files."""
    try:
        fmap_dir = (
            derivatives_dir / f"sub-{info.subject}" / f"ses-{info.session}" / "fmap"
        )
        if not fmap_dir.exists():
            return None

        search_terms = [f"sub-{info.subject}", f"ses-{info.session}"]

        fmap_files = {}
        # Phase difference
        for f in fmap_dir.glob("*phasediff.nii.gz"):
            if all(term in f.name for term in search_terms):
                fmap_files["phasediff"] = f
                break

        # Magnitude
        for f in fmap_dir.glob("*magnitude*.nii.gz"):
            if all(term in f.name for term in search_terms):
                fmap_files["magnitude"] = f
                break

        # EPI fieldmaps
        for direction in ["AP", "PA"]:
            for f in fmap_dir.glob(f"*dir-{direction}_epi.nii.gz"):
                if all(term in f.name for term in search_terms):
                    fmap_files[f"epi_{direction}"] = f

        return fmap_files if fmap_files else None
    except Exception:
        return None


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


def persist_run_assets(result: RunResult, output_root: Path) -> Dict[str, Path]:
    """Persist run result assets (metadata, arrays, figures) for caching."""

    subject_dir = output_root / f"sub-{result.info.subject}" / f"ses-{result.info.session}"
    run_dir = subject_dir / result.info.get_identifier()
    run_dir.mkdir(parents=True, exist_ok=True)

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
        header_bytes = result.header.tobytes() if hasattr(result.header, "tobytes") else bytes()
    arrays_payload["header"] = np.frombuffer(header_bytes, dtype=np.uint8)

    arrays_path = run_dir / "arrays.npz"
    np.savez_compressed(arrays_path, **arrays_payload)

    metadata_path = run_dir / "result.json"

    figure_dest = None
    if result.figure_path is not None:
        figure_dest = _copy_asset(result.figure_path, run_dir / result.figure_path.name)
    carpet_dest = None
    if result.carpetplot_path is not None:
        carpet_dest = _copy_asset(result.carpetplot_path, run_dir / result.carpetplot_path.name)
    thumb_dest = None
    if result.thumbnail_path is not None:
        thumb_dest = _copy_asset(result.thumbnail_path, run_dir / result.thumbnail_path.name)

    if figure_dest is not None:
        result.figure_path = figure_dest
    if carpet_dest is not None:
        result.carpetplot_path = carpet_dest
    if thumb_dest is not None:
        result.thumbnail_path = thumb_dest

    asset_paths: Dict[str, Path] = {
        "run_dir": _relative_path(run_dir, output_root),
        "arrays": _relative_path(arrays_path, output_root),
        "metadata": _relative_path(metadata_path, output_root),
    }
    if figure_dest is not None:
        asset_paths["figure"] = _relative_path(figure_dest, output_root)
    if carpet_dest is not None:
        asset_paths["carpetplot"] = _relative_path(carpet_dest, output_root)
    if thumb_dest is not None:
        asset_paths["thumbnail"] = _relative_path(thumb_dest, output_root)

    result.asset_paths = asset_paths

    metadata = {
        "info": result.info.to_dict(),
        "metrics": result.metrics,
        "flags": result.flags,
        "warnings": result.warnings,
        "sdc_assessed": result.sdc_assessed,
        "events_validated": result.events_validated,
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

    return result.asset_paths


class QACache:
    """Manages caching of QA results for incremental processing."""

    def __init__(self, cache_dir: Path, reuse_dir: Optional[Path] = None):
        """Initialize cache manager."""
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "qa_cache.json"
        self.cache_data: Dict[str, Dict] = {}
        self.reuse_dir = reuse_dir
        self.reuse_cache_file = (
            reuse_dir / "qa_cache.json" if reuse_dir is not None else None
        )
        self.reuse_cache_data: Dict[str, Dict] = {}
        self.load()

    def load(self) -> None:
        """Load cache from disk."""
        self.cache_data = self._load_cache_file(self.cache_file)
        if self.reuse_cache_file is not None:
            self.reuse_cache_data = self._load_cache_file(self.reuse_cache_file)

    def _load_cache_file(self, path: Path) -> Dict[str, Dict]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
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

    def get_cache_key(self, run_path: Path) -> str:
        """Generate cache key for a run."""
        # Use relative path and hash for key
        return hashlib.md5(str(run_path).encode()).hexdigest()

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

        asset_paths = metadata.get("asset_paths", {})
        arrays_rel = asset_paths.get("arrays")
        if arrays_rel is None:
            print(f"Warning: Cached entry for {run_path} lacks arrays path; skipping reuse")
            return None

        arrays_path = source_root / arrays_rel
        if not arrays_path.exists():
            print(f"Warning: Cached arrays not found for {run_path}; skipping reuse")
            return None

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
                print(f"Warning: Cached mask missing for {run_path}; skipping reuse")
                return None
            mask = mask.astype(bool)
            mean_vector = data.get("mean_vector")
            affine = data.get("affine")
            header_arr = data.get("header")

        if mean_vector is None or affine is None or header_arr is None:
            print(f"Warning: Cached arrays incomplete for {run_path}; skipping reuse")
            return None

        header_bytes = header_arr.astype(np.uint8).tobytes()
        header = nib.Nifti1Header.from_fileobj(io.BytesIO(header_bytes))

        series_scalars = metadata.get("series_scalars", {})
        series = {**series_arrays, **series_scalars}

        slice_scalars = metadata.get("slice_qc_scalars", {})
        slice_qc = {**slice_arrays, **slice_scalars} if (slice_arrays or slice_scalars) else None

        info_data = metadata.get("info")
        info = RunInfo.from_dict(info_data) if info_data else create_run_info(run_path)

        figure_rel = asset_paths.get("figure")
        figure_path = source_root / figure_rel if figure_rel else None
        carpet_rel = asset_paths.get("carpetplot")
        carpet_path = source_root / carpet_rel if carpet_rel else None
        thumb_rel = asset_paths.get("thumbnail")
        thumb_path = source_root / thumb_rel if thumb_rel else None

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
            sdc_assessed=metadata.get("sdc_assessed", False),
            events_validated=metadata.get("events_validated", False),
            file_mtime=metadata.get("file_mtime", 0.0),
            processing_time=metadata.get("processing_time", 0.0),
        )

        # Only copy assets if output_root is different from source_root
        # (i.e., when regenerating reports in the same directory, skip copying)
        if source_root.resolve() != output_root.resolve():
            try:
                persist_run_assets(result, output_root)
            except Exception as exc:
                print(f"Warning: Could not materialize cached assets for {run_path}: {exc}")
                return None
        else:
            # When loading from same directory, set asset_paths from metadata
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
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
    except Exception as e:
        raise ValueError(f"Could not load cache file: {e}")
    
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


def ensure_mask_aligned(
    data_img: nib.Nifti1Image, mask_img: nib.Nifti1Image
) -> nib.Nifti1Image:
    """Ensure mask is aligned with data."""
    from nilearn import image as nilearn_image

    if data_img.shape[:3] == mask_img.shape:
        return mask_img
    return nilearn_image.resample_to_img(mask_img, data_img, interpolation="nearest")
