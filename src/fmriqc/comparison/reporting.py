"""HTML reporting for snapshot comparisons."""

from html import escape
from pathlib import Path
from typing import List

from fmriqc.comparison.structures import PairingReport, RunComparison
from fmriqc.io.structures import SnapshotInfo


def generate_comparison_report(
    left_snapshot: SnapshotInfo,
    right_snapshot: SnapshotInfo,
    pairing: PairingReport,
    comparisons: List[RunComparison],
    output_dir: Path,
) -> Path:
    """Generate a compact static HTML comparison report."""
    rows = []
    for comparison in comparisons:
        d = comparison.metric_deltas
        rows.append(
            "<tr>"
            f"<td>{escape(comparison.run_key.to_string())}</td>"
            f"<td>{escape(comparison.status)}</td>"
            f"<td>{_fmt_delta(d.get('tsnr_median'))}</td>"
            f"<td>{_fmt_delta(d.get('fd_median'))}</td>"
            f"<td>{_fmt_delta(d.get('dvars_std_median'))}</td>"
            f"<td>{_fmt_delta(d.get('coverage_signal_fraction'))}</td>"
            f"<td>{escape('; '.join(comparison.warnings))}</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>fmriqc Snapshot Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 32px; color: #17202a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d7dde5; padding: 8px; text-align: left; font-size: 14px; }}
    th {{ background: #f2f5f8; }}
    .meta {{ color: #5b6775; }}
  </style>
</head>
<body>
  <h1>Snapshot Comparison</h1>
  <p class="meta">{escape(left_snapshot.id)} vs {escape(right_snapshot.id)}</p>
  <p>Paired runs: {len(pairing.paired)} · Left only: {len(pairing.left_only)} · Right only: {len(pairing.right_only)} · Duplicate warnings: {len(pairing.warnings)}</p>
  <table>
    <thead><tr><th>Run</th><th>Status</th><th>Delta tSNR</th><th>Delta FD</th><th>Delta DVARS</th><th>Delta Coverage</th><th>Warnings</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="meta">Interpretation is contextual. tSNR increases may reflect smoothing; FD comparisons depend on motion provenance.</p>
</body>
</html>"""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def _fmt_delta(delta) -> str:
    if delta is None or delta.delta is None:
        return "-"
    return f"{delta.delta:.4g}"
