"""Configuration for fMRI QA pipeline."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from .manifest import QAManifest


class DataSourcePreset(Enum):
    """Data source presets for QA pipeline.

    Each preset defines which type of preprocessed data to analyze.
    """
    FINALINTERP = "finalinterp"  # Final interpolated BOLD (default)
    TEDANA = "tedana"            # Tedana optimally combined outputs
    GLMSINGLE = "glmsingle"      # GLMsingle subject-level aggregates


# Glob patterns for each preset
PRESET_PATTERNS = {
    DataSourcePreset.FINALINTERP: "sub-*/ses-*/finalinterp_func/sub-*_bold_final.nii.gz",
    DataSourcePreset.TEDANA: "sub-*/ses-*/tedana/run-*/sub-*_desc-optcom_bold.nii.gz",
    DataSourcePreset.GLMSINGLE: "glmsingle/{source}/sub-*/aggregate/*.nii.gz",
}

# Mask patterns for each preset
MASK_PATTERNS = {
    DataSourcePreset.FINALINTERP: "sub-*/ses-*/finalinterp_func/sub-*_mask.nii.gz",
    DataSourcePreset.TEDANA: "sub-*/ses-*/tedana/run-*/sub-*_desc-brain_mask.nii.gz",
    DataSourcePreset.GLMSINGLE: None,  # Use mask from source data
}


def get_glob_pattern(
    preset: DataSourcePreset,
    glmsingle_source: str = "finalinterp",
) -> str:
    """Get glob pattern for a data source preset.

    Parameters
    ----------
    preset : DataSourcePreset
        Data source preset
    glmsingle_source : str
        For GLMSINGLE preset, which input source (finalinterp or tedana)

    Returns
    -------
    str
        Glob pattern for file discovery
    """
    pattern = PRESET_PATTERNS[preset]
    if preset == DataSourcePreset.GLMSINGLE:
        pattern = pattern.format(source=glmsingle_source)
    return pattern


@dataclass
class QAConfig:
    """Configuration parameters for QA analysis."""

    # Paths
    derivatives_dir: Optional[Path] = None
    bids_root: Optional[Path] = None  # Explicit BIDS root (recommended)
    output_dir_name: str = "QA"
    config_file: Optional[Path] = None
    reuse_run_dir: Optional[Path] = None
    reports_only: Optional[Path] = None  # Regenerate reports from existing QA dir

    # Manifest-based input (alternative to derivatives_dir + glob)
    manifest_path: Optional[Path] = None  # Path to manifest file
    manifest: Optional["QAManifest"] = field(default=None, repr=False)  # Or pass manifest directly

    # Data source preset
    data_source: str = "finalinterp"  # finalinterp, tedana, glmsingle, or manifest
    glmsingle_input_source: str = "finalinterp"  # For glmsingle: which input was used

    # Processing
    glob_pattern: str = ""  # Will be set from data_source if empty
    target_echo: int = 2
    n_jobs: int = 1

    # Thresholds
    dvars_z_threshold: float = 2.5
    fd_threshold: float = 0.3
    fd_median_threshold: float = 0.2
    outlier_threshold: float = 0.02
    tsnr_drop_threshold: float = 0.25
    slice_intensity_threshold: float = 3.0

    # Outlier detection
    outlier_metric_threshold: float = 3.0  # Mahalanobis distance threshold
    outlier_min_runs: int = 5  # Minimum runs needed for outlier detection

    # Exclusion recommendations
    exclusion_stringency: str = "moderate"  # liberal, moderate, or conservative

    # Report options
    organize_hierarchical: bool = True
    generate_carpetplots: bool = True

    # Incremental QA
    use_cache: bool = True
    force_reprocess: bool = False

    # Other
    dry_run: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "QAConfig":
        """Load configuration from YAML or JSON file.

        Supports both QA-specific config files and the standard preprocessing
        config (standard_config.json). When using preprocessing config, paths
        are extracted automatically.
        """
        import json

        path = Path(path)

        # Load file based on extension
        with open(path, "r") as f:
            if path.suffix == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)

        # Check if this is a preprocessing config (has 'paths' with 'raw_dir')
        if "paths" in data and "raw_dir" in data.get("paths", {}):
            # This is the preprocessing config format - extract relevant fields
            paths = data.get("paths", {})
            processing = data.get("processing", {})

            return cls(
                derivatives_dir=Path(paths["derivatives_dir"]).expanduser() if paths.get("derivatives_dir") else None,
                bids_root=Path(paths["raw_dir"]).expanduser() if paths.get("raw_dir") else None,
                target_echo=processing.get("target_echo", 2),
                data_source="tedana" if processing.get("tedana", {}).get("enabled", False) else "finalinterp",
            )

        # Otherwise, this is a QA-specific config - use existing logic
        # Convert nested structure to flat
        flat_data = {}
        for section, values in data.items():
            if isinstance(values, dict):
                flat_data.update(values)
            else:
                flat_data[section] = values

        # Convert string paths to Path objects
        if "derivatives_dir" in flat_data and flat_data["derivatives_dir"]:
            flat_data["derivatives_dir"] = Path(
                flat_data["derivatives_dir"]
            ).expanduser()
        if "bids_root" in flat_data and flat_data["bids_root"]:
            flat_data["bids_root"] = Path(flat_data["bids_root"]).expanduser()
        if "config_file" in flat_data and flat_data["config_file"]:
            flat_data["config_file"] = Path(flat_data["config_file"])
        if "reuse_run_dir" in flat_data and flat_data["reuse_run_dir"]:
            flat_data["reuse_run_dir"] = Path(flat_data["reuse_run_dir"]).expanduser()
        if "manifest_path" in flat_data and flat_data["manifest_path"]:
            flat_data["manifest_path"] = Path(flat_data["manifest_path"]).expanduser()

        # Remove private fields that shouldn't be passed to constructor
        flat_data.pop("_manifest", None)

        return cls(**flat_data)

    def to_yaml(self, path: Path) -> None:
        """Save configuration to YAML file."""
        data = {
            "paths": {
                "derivatives_dir": str(self.derivatives_dir)
                if self.derivatives_dir
                else None,
                "bids_root": str(self.bids_root)
                if self.bids_root
                else None,
                "output_dir_name": self.output_dir_name,
                "reuse_run_dir": str(self.reuse_run_dir)
                if self.reuse_run_dir
                else None,
                "manifest_path": str(self.manifest_path)
                if self.manifest_path
                else None,
            },
            "data_source": {
                "data_source": self.data_source,
                "glmsingle_input_source": self.glmsingle_input_source,
            },
            "processing": {
                "glob_pattern": self.glob_pattern,
                "target_echo": self.target_echo,
                "n_jobs": self.n_jobs,
            },
            "thresholds": {
                "dvars_z_threshold": self.dvars_z_threshold,
                "fd_threshold": self.fd_threshold,
                "fd_median_threshold": self.fd_median_threshold,
                "outlier_threshold": self.outlier_threshold,
                "tsnr_drop_threshold": self.tsnr_drop_threshold,
                "slice_intensity_threshold": self.slice_intensity_threshold,
                "outlier_metric_threshold": self.outlier_metric_threshold,
                "outlier_min_runs": self.outlier_min_runs,
            },
            "exclusions": {
                "exclusion_stringency": self.exclusion_stringency,
            },
            "reports": {
                "organize_hierarchical": self.organize_hierarchical,
                "generate_carpetplots": self.generate_carpetplots,
            },
            "caching": {
                "use_cache": self.use_cache,
                "force_reprocess": self.force_reprocess,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_threshold_dict(self) -> Dict[str, float]:
        """Get threshold values as dictionary."""
        return {
            "dvars_z": self.dvars_z_threshold,
            "fd": self.fd_threshold,
            "fd_median": self.fd_median_threshold,
            "outlier": self.outlier_threshold,
            "tsnr_drop": self.tsnr_drop_threshold,
            "slice_intensity": self.slice_intensity_threshold,
        }

    def get_data_source_preset(self) -> DataSourcePreset:
        """Get data source as enum."""
        preset_map = {
            "finalinterp": DataSourcePreset.FINALINTERP,
            "tedana": DataSourcePreset.TEDANA,
            "glmsingle": DataSourcePreset.GLMSINGLE,
        }
        return preset_map.get(self.data_source.lower(), DataSourcePreset.FINALINTERP)

    def get_effective_glob_pattern(self) -> str:
        """Get glob pattern, using preset default if not specified."""
        if self.glob_pattern:
            return self.glob_pattern
        return get_glob_pattern(
            self.get_data_source_preset(),
            self.glmsingle_input_source,
        )

    def is_timeseries_data(self) -> bool:
        """Check if data source has temporal dimension.

        Returns False for GLMsingle (subject-level aggregates).
        """
        return self.get_data_source_preset() != DataSourcePreset.GLMSINGLE

    def is_manifest_mode(self) -> bool:
        """Check if using manifest-based input."""
        return self.manifest is not None or self.manifest_path is not None or self.data_source == "manifest"

    def get_manifest(self) -> Optional["QAManifest"]:
        """Load and return manifest if in manifest mode."""
        # Return directly passed manifest
        if self.manifest is not None:
            return self.manifest

        # Load from file
        if self.manifest_path is None:
            return None

        from .manifest import QAManifest

        self.manifest = QAManifest.from_file(self.manifest_path)
        return self.manifest
