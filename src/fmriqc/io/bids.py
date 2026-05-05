"""BIDS entity parsing and run-key helpers."""

from __future__ import annotations

import re
from pathlib import Path

from fmriqc.io.structures import RunKey

BIDS_ENTITIES = [
    "sub",
    "ses",
    "task",
    "acq",
    "ce",
    "rec",
    "dir",
    "run",
    "echo",
    "part",
    "space",
    "desc",
]


def strip_nii_suffix(name: str) -> str:
    """Strip common neuroimaging sidecar suffixes from a file name."""
    for suffix in [".nii.gz", ".nii", ".tsv", ".json", ".par", ".txt"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def parse_bids_entities(path: Path | str) -> dict[str, str | None]:
    """Parse BIDS-style entities from a full path or file name."""
    text = str(path)
    filename = strip_nii_suffix(Path(path).name)
    entities: dict[str, str | None] = dict.fromkeys(BIDS_ENTITIES)

    for token in re.split(r"[_/\\]", text):
        token = strip_nii_suffix(token) if token == filename else token
        for key in BIDS_ENTITIES:
            prefix = f"{key}-"
            if token.startswith(prefix):
                entities[key] = token[len(prefix):]
                break
    return entities


def normalize_bids_value(value: str | None, prefix: str) -> str | None:
    """Remove an entity prefix when present."""
    if value is None:
        return None
    return value[len(prefix):] if value.startswith(prefix) else value


def run_key_from_path(path: Path, default_session: str = "01") -> RunKey:
    """Create a canonical RunKey from a BIDS-like path."""
    entities = parse_bids_entities(path)
    subject = entities["sub"]
    if subject is None:
        raise ValueError(f"Cannot extract subject from path: {path}")

    return RunKey(
        subject=subject,
        session=entities["ses"] or default_session,
        task=entities["task"],
        run=entities["run"] or "01",
        echo=entities["echo"],
        acquisition=entities["acq"],
        part=entities["part"],
    )
