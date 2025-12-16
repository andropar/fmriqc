"""fMRI Quality Assurance Package.

The QA pipeline provides comprehensive quality assessment for fMRI data.
It supports BIDS derivatives, tedana outputs, and custom datasets via manifest files.

Basic usage:
    from fmriqa import QAConfig, run_qa

    config = QAConfig(
        derivatives_dir=Path("/path/to/derivatives"),
        data_source="tedana",
    )
    run_qa(config)

For non-BIDS data, use a manifest:
    from fmriqa.manifest import generate_manifest_from_globs

    manifest = generate_manifest_from_globs(
        bold_pattern="data/**/func/*bold.nii.gz",
    )
    manifest.to_file("manifest.yaml")

    config = QAConfig(manifest_path=Path("manifest.yaml"))
    run_qa(config)
"""

# Lazy imports to avoid loading heavy dependencies when not needed
# The manifest module has minimal dependencies and can be imported directly
__version__ = "0.1.0"


def __getattr__(name):
    """Lazy import of QA modules to avoid loading heavy dependencies."""
    if name == "QAConfig":
        from .config import QAConfig
        return QAConfig
    elif name == "run_qa":
        from .core import run_qa
        return run_qa
    elif name in ("RunInfo", "RunResult", "SessionResults", "StudyResults", "SubjectResults"):
        from . import structures
        return getattr(structures, name)
    elif name in ("QAManifest", "generate_manifest_from_globs"):
        from . import manifest
        return getattr(manifest, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "QAConfig",
    "RunInfo",
    "RunResult",
    "SessionResults",
    "SubjectResults",
    "StudyResults",
    "run_qa",
    "QAManifest",
    "generate_manifest_from_globs",
]
