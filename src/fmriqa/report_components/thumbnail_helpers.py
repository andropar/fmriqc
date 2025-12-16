"""Thumbnail helper functions for QA reports.

This module contains functions for managing thumbnails and building
thumbnail card data structures for report display.
"""

from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

from .utils import format_run_label, escape_html, relative_asset_path
from .badge_helpers import get_outlier_badge, get_fd_badge, get_coverage_badge, get_flag_badge

if TYPE_CHECKING:
    from ..structures import RunResult, SubjectResults


def ensure_thumbnail(run: "RunResult", output_dir: Path) -> Optional[Path]:
    """
    Ensure a thumbnail image exists for this run.
    Prefers existing thumbnails; otherwise generates one from mean map + mask.
    """
    from ..visualization import create_run_thumbnail

    thumb_candidates: List[Path] = []
    if run.thumbnail_path is not None:
        thumb_candidates.append(Path(run.thumbnail_path))
    thumb_rel = run.asset_paths.get("thumbnail") if getattr(run, "asset_paths", None) else None
    if thumb_rel:
        thumb_candidates.append((output_dir / thumb_rel))

    for cand in thumb_candidates:
        if cand and cand.exists():
            return cand

    # Try to generate a thumbnail if we have data
    mean_map = run.maps.get("mean")
    mask = getattr(run, "mask", None)
    if mean_map is None or mask is None:
        return None

    thumb_dir = output_dir / "thumbnails" / f"sub-{run.info.subject}" / f"ses-{run.info.session}"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{run.info.get_identifier()}_thumbnail.png"
    try:
        create_run_thumbnail(mean_map, mask, thumb_path)
        run.thumbnail_path = thumb_path
        run.asset_paths = getattr(run, "asset_paths", {}) or {}
        run.asset_paths["thumbnail"] = relative_asset_path(thumb_path, output_dir)
        return thumb_path
    except Exception:
        return None


def build_thumbnail_cards(subject: "SubjectResults", output_dir: Path) -> Dict[str, List[Dict[str, str]]]:
    """Prepare thumbnail card metadata per session, generating thumbnails if needed."""
    cards_by_session: Dict[str, List[Dict[str, str]]] = {}

    for session in subject.sessions:
        session_label = f"ses-{session.session}"
        cards: List[Dict[str, str]] = []
        for run in session.runs:
            thumb_path = ensure_thumbnail(run, output_dir)
            if thumb_path is None:
                continue
            run_label = format_run_label(run.info.run)
            run_id = f"{subject.get_identifier()}_{session_label}_{run_label}"
            run_id_html = escape_html(run_id)
            img_rel = relative_asset_path(thumb_path, output_dir)

            outlier_text, outlier_class = get_outlier_badge(run)
            fd_text, fd_class = get_fd_badge(run)
            cov_text, cov_class = get_coverage_badge(run)
            flag_text, flag_class = get_flag_badge(run)
            n_vols = ""
            if run.series and "global_signal" in run.series and hasattr(run.series["global_signal"], "__len__"):
                try:
                    n_vols = f"{len(run.series['global_signal'])} vols"
                except Exception:
                    n_vols = ""

            cards.append(
                {
                    "run_label": run_label,
                    "run_id": run_id_html,
                    "img": img_rel,
                    "outlier_text": outlier_text,
                    "outlier_class": outlier_class,
                    "fd_text": fd_text,
                    "fd_class": fd_class,
                    "cov_text": cov_text,
                    "cov_class": cov_class,
                    "flag_text": flag_text,
                    "flag_class": flag_class,
                    "subtitle": f"{session_label} · {run_label}" + (f" · {n_vols}" if n_vols else ""),
                }
            )
        if cards:
            cards_by_session[session_label] = cards

    return cards_by_session
