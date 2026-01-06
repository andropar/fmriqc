"""Manifest-based input for QA pipeline.

This module provides flexible input handling for the QA pipeline, allowing
it to work with any dataset structure (not just BIDS).

A manifest is a JSON/YAML file that explicitly lists all input files and
their organization into subjects/sessions/runs.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import yaml


class BIDSEntityExtractor:
    """Extract BIDS entities from file paths and names."""

    # BIDS entity patterns
    ENTITY_PATTERNS = {
        'sub': r'sub-([a-zA-Z0-9]+)',
        'ses': r'ses-([a-zA-Z0-9]+)',
        'task': r'task-([a-zA-Z0-9]+)',
        'run': r'run-([a-zA-Z0-9]+)',
        'echo': r'echo-([0-9]+)',
        'part': r'part-(mag|phase|real|imag)',
        'desc': r'desc-([a-zA-Z0-9]+)',
    }

    @classmethod
    def extract_from_path(cls, path: Path) -> Dict[str, Optional[str]]:
        """Extract all BIDS entities from file path.

        Parameters
        ----------
        path : Path
            File path to extract from

        Returns
        -------
        dict
            Dictionary of entity name to value (None if not found)
        """
        path_str = str(path)
        entities = {}

        for entity, pattern in cls.ENTITY_PATTERNS.items():
            match = re.search(pattern, path_str)
            entities[entity] = match.group(1) if match else None

        return entities

    @classmethod
    def extract_subject_session(cls, path: Path) -> Tuple[Optional[str], Optional[str]]:
        """Extract subject and session from path.

        Parameters
        ----------
        path : Path
            File path to extract from

        Returns
        -------
        tuple
            (subject, session) - both can be None
        """
        entities = cls.extract_from_path(path)
        return entities.get('sub'), entities.get('ses')

    @staticmethod
    def normalize_entity(entity: str, value: str) -> Optional[str]:
        """Normalize entity value to standard format.

        Parameters
        ----------
        entity : str
            Entity name (e.g., 'sub', 'ses')
        value : str
            Entity value

        Returns
        -------
        str or None
            Normalized value with entity prefix, or None if value is empty
        """
        if not value:
            return None

        # Remove prefix if already present
        prefix = f"{entity}-"
        if value.startswith(prefix):
            value = value[len(prefix):]

        # Return with prefix
        return f"{prefix}{value}"


@dataclass
class ManifestRun:
    """A single run entry in the manifest."""

    bold: Path  # Required: path to 4D BOLD NIfTI
    mask: Optional[Path] = None  # Optional: brain mask
    motion: Optional[Path] = None  # Optional: motion parameters file
    label: str = ""  # Optional: run label (e.g., "run-01", "rest", "task-foo")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "bold": str(self.bold),
            "mask": str(self.mask) if self.mask else None,
            "motion": str(self.motion) if self.motion else None,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Dict, base_path: Optional[Path] = None) -> "ManifestRun":
        """Create from dictionary."""

        def resolve_path(p: Optional[str]) -> Optional[Path]:
            if p is None:
                return None
            path = Path(p)
            if base_path and not path.is_absolute():
                path = base_path / path
            return path

        return cls(
            bold=resolve_path(data["bold"]),  # type: ignore
            mask=resolve_path(data.get("mask")),
            motion=resolve_path(data.get("motion")),
            label=data.get("label", ""),
        )


@dataclass
class ManifestSession:
    """A session entry in the manifest."""

    id: str  # Session identifier (e.g., "ses-01", "visit1")
    runs: List[ManifestRun] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "runs": [r.to_dict() for r in self.runs],
        }

    @classmethod
    def from_dict(
        cls, data: Dict, base_path: Optional[Path] = None
    ) -> "ManifestSession":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            runs=[ManifestRun.from_dict(r, base_path) for r in data.get("runs", [])],
        )


@dataclass
class ManifestSubject:
    """A subject entry in the manifest."""

    id: str  # Subject identifier (e.g., "sub-01", "participant1")
    sessions: List[ManifestSession] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(
        cls, data: Dict, base_path: Optional[Path] = None
    ) -> "ManifestSubject":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            sessions=[
                ManifestSession.from_dict(s, base_path)
                for s in data.get("sessions", [])
            ],
        )


@dataclass
class QAManifest:
    """Complete manifest for QA pipeline input.

    A manifest explicitly lists all input files and their organization,
    allowing the QA pipeline to work with any dataset structure.

    Example manifest (YAML):
    ```yaml
    name: "My fMRI Study"
    description: "Resting state scans from 10 subjects"
    base_path: "/data/my_study"  # Optional: resolve relative paths from here

    subjects:
      - id: "sub-01"
        sessions:
          - id: "ses-01"
            runs:
              - bold: "sub-01/ses-01/func/bold.nii.gz"
                mask: "sub-01/ses-01/func/brain_mask.nii.gz"
                motion: "sub-01/ses-01/func/motion.par"
                label: "run-01"
    ```
    """

    subjects: List[ManifestSubject] = field(default_factory=list)
    name: str = ""
    description: str = ""
    base_path: Optional[Path] = None
    qa_config: Optional[Dict] = None  # Optional embedded QA configuration

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "description": self.description,
            "base_path": str(self.base_path) if self.base_path else None,
            "subjects": [s.to_dict() for s in self.subjects],
        }
        if self.qa_config:
            result["qa_config"] = self.qa_config
        return result

    @classmethod
    def from_dict(cls, data: Dict, manifest_path: Optional[Path] = None) -> "QAManifest":
        """Create from dictionary.

        Parameters
        ----------
        data : dict
            Manifest data
        manifest_path : Path, optional
            Path to the manifest file, used to resolve relative base_path
        """
        base_path = None
        if data.get("base_path"):
            base_path = Path(data["base_path"])
            if manifest_path and not base_path.is_absolute():
                base_path = manifest_path.parent / base_path

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            base_path=base_path,
            subjects=[
                ManifestSubject.from_dict(s, base_path)
                for s in data.get("subjects", [])
            ],
            qa_config=data.get("qa_config"),  # Extract embedded config
        )

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "QAManifest":
        """Load manifest from JSON or YAML file."""
        path = Path(path)
        with open(path, "r") as f:
            if path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            else:
                data = json.load(f)
        return cls.from_dict(data, manifest_path=path)

    def to_file(self, path: Union[str, Path]) -> None:
        """Save manifest to JSON or YAML file."""
        path = Path(path)
        data = self.to_dict()
        with open(path, "w") as f:
            if path.suffix in (".yaml", ".yml"):
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(data, f, indent=2)

    def validate(self) -> List[str]:
        """Validate manifest, checking that all files exist.

        Returns
        -------
        list of str
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.subjects:
            errors.append("Manifest has no subjects")
            return errors

        for subject in self.subjects:
            if not subject.id:
                errors.append("Subject missing 'id' field")
                continue

            if not subject.sessions:
                errors.append(f"Subject {subject.id} has no sessions")
                continue

            for session in subject.sessions:
                if not session.id:
                    errors.append(f"Subject {subject.id}: session missing 'id' field")
                    continue

                if not session.runs:
                    errors.append(
                        f"Subject {subject.id}, session {session.id} has no runs"
                    )
                    continue

                for i, run in enumerate(session.runs):
                    run_id = run.label or f"run-{i + 1:02d}"

                    if run.bold is None:
                        errors.append(
                            f"{subject.id}/{session.id}/{run_id}: missing 'bold' path"
                        )
                    elif not run.bold.exists():
                        errors.append(
                            f"{subject.id}/{session.id}/{run_id}: BOLD file not found: {run.bold}"
                        )

                    if run.mask and not run.mask.exists():
                        errors.append(
                            f"{subject.id}/{session.id}/{run_id}: mask file not found: {run.mask}"
                        )

                    if run.motion and not run.motion.exists():
                        errors.append(
                            f"{subject.id}/{session.id}/{run_id}: motion file not found: {run.motion}"
                        )

        return errors

    def get_all_bold_paths(self) -> List[Path]:
        """Get list of all BOLD file paths in the manifest."""
        paths = []
        for subject in self.subjects:
            for session in subject.sessions:
                for run in session.runs:
                    if run.bold:
                        paths.append(run.bold)
        return paths

    def get_run_count(self) -> int:
        """Get total number of runs in manifest."""
        return sum(
            len(session.runs)
            for subject in self.subjects
            for session in subject.sessions
        )

    def summary(self) -> str:
        """Get human-readable summary of manifest."""
        lines = []
        if self.name:
            lines.append(f"Name: {self.name}")
        if self.description:
            lines.append(f"Description: {self.description}")

        n_subjects = len(self.subjects)
        n_sessions = sum(len(s.sessions) for s in self.subjects)
        n_runs = self.get_run_count()

        lines.append(f"Subjects: {n_subjects}")
        lines.append(f"Sessions: {n_sessions}")
        lines.append(f"Runs: {n_runs}")

        # Count optional files
        n_masks = sum(
            1
            for subj in self.subjects
            for sess in subj.sessions
            for run in sess.runs
            if run.mask
        )
        n_motion = sum(
            1
            for subj in self.subjects
            for sess in subj.sessions
            for run in sess.runs
            if run.motion
        )

        lines.append(f"Runs with mask: {n_masks}/{n_runs}")
        lines.append(f"Runs with motion: {n_motion}/{n_runs}")

        return "\n".join(lines)


class ManifestGenerator:
    """Generate QA manifests from BIDS datasets."""

    def __init__(self, bids_root: Path):
        """Initialize manifest generator.

        Parameters
        ----------
        bids_root : Path
            Root directory of BIDS dataset
        """
        self.bids_root = Path(bids_root).resolve()
        self.extractor = BIDSEntityExtractor()

    def generate_from_globs(
        self,
        globs: List[str],
        output_path: Optional[Path] = None,
        name: str = "",
        description: str = "",
    ) -> QAManifest:
        """Generate manifest from glob patterns.

        Parameters
        ----------
        globs : list of str
            List of glob patterns to match BOLD files
        output_path : Path, optional
            Path to save manifest YAML
        name : str, optional
            Optional name for the manifest
        description : str, optional
            Optional description for the manifest

        Returns
        -------
        QAManifest
            Generated manifest
        """
        # Discover files
        files = self._discover_files(globs)

        # Organize by subject/session
        organized = self._organize_by_subject_session(files)

        # Build manifest structure
        manifest = self._build_manifest_structure(organized, name, description)

        # Save if output path provided
        if output_path:
            manifest.to_file(output_path)

        return manifest

    def _discover_files(self, globs: List[str]) -> List[Path]:
        """Discover files matching glob patterns.

        Parameters
        ----------
        globs : list of str
            Glob patterns

        Returns
        -------
        list of Path
            Discovered file paths
        """
        files = []
        for pattern in globs:
            if '*' in pattern or '?' in pattern:
                # Glob pattern
                matched = list(self.bids_root.glob(pattern))
                files.extend(matched)
            else:
                # Direct path
                path = self.bids_root / pattern
                if path.exists():
                    files.append(path)

        # Filter for BOLD files and deduplicate
        files = [f for f in files if self._is_bold_file(f)]
        files = sorted(set(files))

        return files

    def _is_bold_file(self, path: Path) -> bool:
        """Check if file is a BOLD functional image.

        Parameters
        ----------
        path : Path
            File path

        Returns
        -------
        bool
            True if BOLD file
        """
        return (
            path.suffix in ['.nii', '.gz'] and
            '_bold' in path.name and
            path.is_file()
        )

    def _organize_by_subject_session(
        self,
        files: List[Path]
    ) -> Dict[str, Dict[str, List[Path]]]:
        """Organize files by subject and session.

        Parameters
        ----------
        files : list of Path
            File paths

        Returns
        -------
        dict
            Nested dict: {subject: {session: [files]}}
        """
        organized = {}

        for file_path in files:
            subject, session = self.extractor.extract_subject_session(file_path)

            if not subject:
                print(f"Warning: Could not extract subject from {file_path}")
                continue

            # Use default session if not found
            if not session:
                session = "01"

            # Normalize
            subject = self.extractor.normalize_entity('sub', subject)
            session = self.extractor.normalize_entity('ses', session)

            # Add to structure
            if subject not in organized:
                organized[subject] = {}
            if session not in organized[subject]:
                organized[subject][session] = []

            organized[subject][session].append(file_path)

        return organized

    def _build_manifest_structure(
        self,
        organized: Dict[str, Dict[str, List[Path]]],
        name: str = "",
        description: str = "",
    ) -> QAManifest:
        """Build manifest from organized files.

        Parameters
        ----------
        organized : dict
            Organized file structure
        name : str, optional
            Manifest name
        description : str, optional
            Manifest description

        Returns
        -------
        QAManifest
            Constructed manifest
        """
        subjects = []

        for subject_id, sessions in sorted(organized.items()):
            sessions_list = []

            for session_id, files in sorted(sessions.items()):
                runs = []

                for file_path in sorted(files):
                    entities = self.extractor.extract_from_path(file_path)
                    run_label = entities.get('run') or '01'

                    # Normalize run label
                    if not run_label.startswith('run-'):
                        run_label = f"run-{run_label}"

                    run = ManifestRun(
                        bold=file_path,
                        mask=None,
                        motion=None,
                        label=run_label,
                    )

                    runs.append(run)

                sessions_list.append(ManifestSession(id=session_id, runs=runs))

            subjects.append(ManifestSubject(id=subject_id, sessions=sessions_list))

        return QAManifest(
            subjects=subjects,
            name=name,
            description=description,
            base_path=self.bids_root,
        )


def generate_manifest_from_globs(
    bold_pattern: str,
    mask_pattern: Optional[str] = None,
    motion_pattern: Optional[str] = None,
    base_dir: Optional[Path] = None,
    subject_regex: str = r"sub-([^/_]+)",
    session_regex: str = r"ses-([^/_]+)",
    run_regex: str = r"run-([^/_]+)",
    name: str = "",
    description: str = "",
) -> QAManifest:
    """Generate a manifest from glob patterns.

    This function discovers files using glob patterns and organizes them
    into a manifest structure by extracting subject/session/run identifiers
    from file paths using regex patterns.

    Parameters
    ----------
    bold_pattern : str
        Glob pattern for BOLD files (e.g., "**/func/*bold.nii.gz")
    mask_pattern : str, optional
        Glob pattern for mask files. If provided, masks are matched to
        BOLD files by proximity in directory structure.
    motion_pattern : str, optional
        Glob pattern for motion parameter files.
    base_dir : Path, optional
        Base directory for glob patterns. Defaults to current directory.
    subject_regex : str
        Regex to extract subject ID from path. Default: r"sub-([^/_]+)"
    session_regex : str
        Regex to extract session ID from path. Default: r"ses-([^/_]+)"
    run_regex : str
        Regex to extract run ID from path. Default: r"run-([^/_]+)"
    name : str
        Optional name for the manifest
    description : str
        Optional description for the manifest

    Returns
    -------
    QAManifest
        Generated manifest

    Examples
    --------
    >>> manifest = generate_manifest_from_globs(
    ...     bold_pattern="data/**/func/*bold.nii.gz",
    ...     mask_pattern="data/**/func/*mask.nii.gz",
    ...     motion_pattern="data/**/func/*.par",
    ...     base_dir=Path("/my/data"),
    ... )
    """
    base_dir = Path(base_dir or ".").resolve()

    # Find all BOLD files
    bold_files = sorted(base_dir.glob(bold_pattern))
    if not bold_files:
        raise ValueError(f"No BOLD files found with pattern: {bold_pattern}")

    # Find masks and motion files if patterns provided
    mask_files = sorted(base_dir.glob(mask_pattern)) if mask_pattern else []
    motion_files = sorted(base_dir.glob(motion_pattern)) if motion_pattern else []

    # Build lookup for quick matching
    def build_lookup(files: List[Path]) -> Dict[str, List[Path]]:
        """Build lookup by directory for file matching."""
        lookup: Dict[str, List[Path]] = {}
        for f in files:
            key = str(f.parent)
            if key not in lookup:
                lookup[key] = []
            lookup[key].append(f)
        return lookup

    mask_lookup = build_lookup(mask_files)
    motion_lookup = build_lookup(motion_files)

    def extract_id(path: Path, regex: str) -> Optional[str]:
        """Extract ID from path using regex."""
        match = re.search(regex, str(path))
        return match.group(1) if match else None

    def find_matching_file(
        bold_path: Path, lookup: Dict[str, List[Path]], file_type: str
    ) -> Optional[Path]:
        """Find a matching file for a BOLD file."""
        # First try same directory
        dir_key = str(bold_path.parent)
        candidates = lookup.get(dir_key, [])

        if candidates:
            # If multiple candidates, try to match by run ID
            bold_run = extract_id(bold_path, run_regex)
            for c in candidates:
                c_run = extract_id(c, run_regex)
                if c_run == bold_run:
                    return c
            # If no run match, just take the first
            return candidates[0]

        # Try parent directories
        for parent in bold_path.parents:
            parent_key = str(parent)
            candidates = lookup.get(parent_key, [])
            if candidates:
                return candidates[0]

        return None

    # Organize by subject/session/run
    subjects_dict: Dict[str, Dict[str, List[ManifestRun]]] = {}

    for bold_path in bold_files:
        subject_id = extract_id(bold_path, subject_regex) or "unknown"
        session_id = extract_id(bold_path, session_regex) or "unknown"
        run_id = extract_id(bold_path, run_regex)

        # Find matching mask and motion files
        mask_path = find_matching_file(bold_path, mask_lookup, "mask")
        motion_path = find_matching_file(bold_path, motion_lookup, "motion")

        run = ManifestRun(
            bold=bold_path,
            mask=mask_path,
            motion=motion_path,
            label=f"run-{run_id}" if run_id else "",
        )

        if subject_id not in subjects_dict:
            subjects_dict[subject_id] = {}
        if session_id not in subjects_dict[subject_id]:
            subjects_dict[subject_id][session_id] = []
        subjects_dict[subject_id][session_id].append(run)

    # Convert to manifest structure
    subjects = []
    for subject_id in sorted(subjects_dict.keys()):
        sessions = []
        for session_id in sorted(subjects_dict[subject_id].keys()):
            runs = subjects_dict[subject_id][session_id]
            # Sort runs by label
            runs.sort(key=lambda r: r.label or "")
            sessions.append(ManifestSession(id=session_id, runs=runs))
        subjects.append(ManifestSubject(id=subject_id, sessions=sessions))

    return QAManifest(
        subjects=subjects,
        name=name,
        description=description,
        base_path=base_dir,
    )
