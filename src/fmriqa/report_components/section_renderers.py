"""Section rendering functions for QA HTML reports.

This module contains functions that render specific sections of QA reports,
such as metrics tables, alignment sections, and multi-echo analysis.
"""

from pathlib import Path
from typing import Dict, List, Optional

from .utils import (
    format_metric_name,
    get_metric_tooltip,
    get_metric_standard,
    format_metric_value,
    escape_html,
    relative_asset_path,
)


def render_metrics_table(metrics: Dict[str, float], level: str = "run") -> str:
    """Render metrics as an HTML table with tooltips."""
    html = ["<table class='metrics-table'><thead><tr><th>Metric</th><th>Value</th><th>Good standard</th></tr></thead><tbody>"]

    # Sort metrics for consistent display
    sorted_metrics = sorted(metrics.items())

    for metric_name, value in sorted_metrics:
        formatted_name = format_metric_name(metric_name)
        tooltip = escape_html(get_metric_tooltip(metric_name))
        formatted_value = format_metric_value(value)
        standard_value = get_metric_standard(metric_name)

        html.append(
            f"<tr>"
            f"<td><span class='metric-name'>{formatted_name}<span class='tooltip-text'>{tooltip}</span></span></td>"
            f"<td>{formatted_value}</td>"
            f"<td>{standard_value}</td>"
            f"</tr>"
        )

    html.append("</tbody></table>")
    return "\n".join(html)


def render_metrics_summary(metrics: Dict[str, float], key_metrics: List[str]) -> str:
    """Render key metrics as summary cards."""
    html = ["<div class='metrics-summary'>"]

    for key in key_metrics:
        if key in metrics:
            value = metrics[key]
            formatted_name = format_metric_name(key)
            tooltip = escape_html(get_metric_tooltip(key))
            formatted_value = format_metric_value(value)

            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'><span class='metric-name'>{formatted_name}<span class='tooltip-text'>{tooltip}</span></span></div>"
                f"<div class='metric-item-value'>{formatted_value}</div>"
                f"</div>"
            )

    html.append("</div>")
    return "\n".join(html)


def render_alignment_section(
    alignment_report: Optional[Dict],
    output_dir: Path,
) -> str:
    """Render cross-session alignment verification section (CIR-208).

    Parameters
    ----------
    alignment_report : dict or None
        CrossSessionReport.to_dict() output
    output_dir : Path
        Base directory for relative paths

    Returns
    -------
    str
        HTML string for alignment section
    """
    if alignment_report is None:
        return ""

    html = []
    html.append("<details class='alignment-section' style='margin-top: 2rem;'>")
    html.append("<summary style='cursor: pointer; font-weight: 600; padding: 0.75rem; background: var(--hover); border-radius: 8px;'>")
    html.append("<span style='display: flex; align-items: center; gap: 0.5rem;'>")
    html.append("<span style='font-size: 1.2rem;'>🔗</span>")
    html.append("<span>Cross-Session Alignment Verification</span>")

    # Add quality badge
    flagged = alignment_report.get("flagged_sessions", [])
    n_sessions = len(alignment_report.get("session_metrics", {}))
    if n_sessions == 0:
        html.append("<span class='flag flag-info' style='margin-left: auto;'>No comparisons</span>")
    elif len(flagged) == 0:
        html.append("<span class='flag flag-success' style='margin-left: auto;'>✓ All aligned</span>")
    else:
        html.append(f"<span class='flag flag-warning' style='margin-left: auto;'>⚠ {len(flagged)} session(s) flagged</span>")

    html.append("</span>")
    html.append("</summary>")
    html.append("<div style='padding: 1rem 0;'>")

    # Reference session info
    ref_session = alignment_report.get("reference_session", "unknown")
    html.append(f"<p><strong>Reference session:</strong> ses-{ref_session}</p>")

    # Stability metrics
    stability = alignment_report.get("stability_metrics", {})
    if stability:
        html.append("<h4 style='margin-top: 1rem;'>Stability Metrics</h4>")
        html.append("<div class='metrics-summary'>")
        if "mean_correlation" in stability:
            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'>Mean Correlation</div>"
                f"<div class='metric-item-value'>{stability['mean_correlation']:.3f}</div>"
                f"</div>"
            )
        if "mean_alignment_score" in stability:
            score = stability['mean_alignment_score']
            quality = "excellent" if score >= 0.9 else "good" if score >= 0.8 else "acceptable" if score >= 0.65 else "poor"
            color = "#27ae60" if quality == "excellent" else "#2ecc71" if quality == "good" else "#f1c40f" if quality == "acceptable" else "#e74c3c"
            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'>Mean Alignment Score</div>"
                f"<div class='metric-item-value' style='color: {color};'>{score:.3f}</div>"
                f"</div>"
            )
        html.append("</div>")

    # Cross-session ICC
    icc_values = alignment_report.get("cross_session_icc", {})
    if icc_values:
        html.append("<h4 style='margin-top: 1rem;'>Cross-Session ICC</h4>")
        html.append("<div class='metrics-summary'>")
        for key, value in icc_values.items():
            formatted_name = key.replace("_", " ").title()
            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'>{formatted_name}</div>"
                f"<div class='metric-item-value'>{value:.3f}</div>"
                f"</div>"
            )
        html.append("</div>")

    # Session-by-session alignment table
    session_metrics = alignment_report.get("session_metrics", {})
    if session_metrics:
        html.append("<h4 style='margin-top: 1rem;'>Session Alignment to Reference</h4>")
        html.append("<div style='overflow-x: auto;'>")
        html.append("<table class='data-table' style='min-width: 600px;'>")
        html.append("<thead><tr>")
        html.append("<th>Session</th>")
        html.append("<th>Correlation</th>")
        html.append("<th>Mutual Info</th>")
        html.append("<th>Edge Align</th>")
        html.append("<th>Dice</th>")
        html.append("<th>COM Shift</th>")
        html.append("<th>Overall</th>")
        html.append("<th>Quality</th>")
        html.append("</tr></thead><tbody>")

        quality_colors = {
            "excellent": "#27ae60",
            "good": "#2ecc71",
            "acceptable": "#f1c40f",
            "poor": "#e74c3c",
            "failed": "#c0392b",
        }

        for session, metrics in sorted(session_metrics.items()):
            quality = metrics.get("quality", "unknown")
            color = quality_colors.get(quality, "#95a5a6")
            is_flagged = session in flagged

            row_style = "background: rgba(231, 76, 60, 0.1);" if is_flagged else ""
            html.append(f"<tr style='{row_style}'>")
            html.append(f"<td><strong>ses-{session}</strong>{'⚠️' if is_flagged else ''}</td>")
            html.append(f"<td>{metrics.get('correlation', 0):.3f}</td>")
            html.append(f"<td>{metrics.get('mutual_information', 0):.3f}</td>")
            html.append(f"<td>{metrics.get('edge_alignment', 0):.3f}</td>")
            html.append(f"<td>{metrics.get('dice_overlap', 0):.3f}</td>")
            html.append(f"<td>{metrics.get('center_of_mass_distance', 0):.2f} mm</td>")
            html.append(f"<td>{metrics.get('overall_score', 0):.3f}</td>")
            html.append(f"<td><span style='color: {color}; font-weight: bold;'>{quality.upper()}</span></td>")
            html.append("</tr>")

        html.append("</tbody></table>")
        html.append("</div>")

    # Flagged sessions
    if flagged:
        html.append("<div class='warnings' style='margin-top: 1rem;'>")
        html.append("<strong>⚠ Sessions with alignment concerns:</strong>")
        html.append("<ul>")
        for sess in flagged:
            html.append(f"<li>ses-{sess} - Review alignment visualization or consider re-registration</li>")
        html.append("</ul>")
        html.append("</div>")

    # Alignment figures
    figure_paths = alignment_report.get("alignment_figure_paths", {})
    if figure_paths:
        html.append("<h4 style='margin-top: 1rem;'>Alignment Visualizations</h4>")
        for label, path_str in figure_paths.items():
            if path_str:
                path = Path(path_str)
                if path.exists():
                    rel_path = relative_asset_path(path, output_dir)
                    html.append(f"<details style='margin-top: 0.5rem;'>")
                    html.append(f"<summary style='cursor: pointer; padding: 0.5rem; background: var(--hover); border-radius: 4px;'>{label}</summary>")
                    html.append(f"<figure style='margin-top: 0.5rem;'><img src='{rel_path}' alt='Alignment verification for {label}' style='max-width: 100%;'></figure>")
                    html.append("</details>")

    html.append("</div>")
    html.append("</details>")

    return "\n".join(html)


def render_multiecho_section(
    multiecho_report: Optional[Dict],
    output_dir: Path,
) -> str:
    """Render multi-echo and tedana QA section (CIR-206).

    Parameters
    ----------
    multiecho_report : dict or None
        MultiEchoReport.to_dict() output
    output_dir : Path
        Base directory for relative paths

    Returns
    -------
    str
        HTML string for multi-echo section
    """
    if multiecho_report is None:
        return ""

    html = []
    html.append("<details class='multiecho-section' style='margin-top: 2rem;'>")
    html.append("<summary style='cursor: pointer; font-weight: 600; padding: 0.75rem; background: var(--hover); border-radius: 8px;'>")
    html.append("<span style='display: flex; align-items: center; gap: 0.5rem;'>")
    html.append("<span style='font-size: 1.2rem;'>📡</span>")
    html.append("<span>Multi-Echo / Tedana Analysis</span>")

    # Add quality badge
    tedana = multiecho_report.get("tedana_metrics")
    if tedana:
        quality = tedana.get("denoising_quality", "unknown")
        if quality == "good":
            html.append("<span class='flag flag-success' style='margin-left: auto;'>✓ Good denoising</span>")
        elif quality == "acceptable":
            html.append("<span class='flag flag-info' style='margin-left: auto;'>OK denoising</span>")
        else:
            html.append(f"<span class='flag flag-warning' style='margin-left: auto;'>⚠ {quality}</span>")

    html.append("</span>")
    html.append("</summary>")
    html.append("<div style='padding: 1rem 0;'>")

    # Echo-wise metrics table
    echo_metrics = multiecho_report.get("echo_metrics", [])
    if echo_metrics:
        html.append("<h4>Echo-wise Metrics</h4>")
        html.append("<div style='overflow-x: auto;'>")
        html.append("<table class='data-table'>")
        html.append("<thead><tr>")
        html.append("<th>Echo</th><th>TE (ms)</th><th>tSNR</th><th>Mean Signal</th><th>Dropout %</th>")
        html.append("</tr></thead><tbody>")

        for echo in echo_metrics:
            html.append("<tr>")
            html.append(f"<td>E{echo.get('echo_num', '?')}</td>")
            html.append(f"<td>{echo.get('echo_time_ms', 0):.1f}</td>")
            html.append(f"<td>{echo.get('tsnr_median', 0):.1f}</td>")
            html.append(f"<td>{echo.get('mean_signal', 0):.0f}</td>")
            html.append(f"<td>{echo.get('dropout_fraction', 0)*100:.1f}%</td>")
            html.append("</tr>")

        html.append("</tbody></table>")
        html.append("</div>")

    # T2* quality
    t2star = multiecho_report.get("t2star_quality", {})
    if t2star:
        html.append("<h4 style='margin-top: 1rem;'>T2* Decay Fit</h4>")
        html.append("<div class='metrics-summary'>")
        if "estimated_t2star_ms" in t2star:
            val = t2star["estimated_t2star_ms"]
            color = "#27ae60" if 20 <= val <= 50 else "#f1c40f" if 10 <= val <= 70 else "#e74c3c"
            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'>Estimated T2*</div>"
                f"<div class='metric-item-value' style='color: {color};'>{val:.1f} ms</div>"
                f"</div>"
            )
        if "decay_fit_r_squared" in t2star:
            r2 = t2star["decay_fit_r_squared"]
            color = "#27ae60" if r2 >= 0.95 else "#f1c40f" if r2 >= 0.85 else "#e74c3c"
            html.append(
                f"<div class='metric-item'>"
                f"<div class='metric-item-label'>Decay Fit R²</div>"
                f"<div class='metric-item-value' style='color: {color};'>{r2:.3f}</div>"
                f"</div>"
            )
        html.append("</div>")

    # tSNR improvement
    improvement = multiecho_report.get("tsnr_improvement", 0)
    tsnr_optcom = multiecho_report.get("tsnr_optcom", 0)
    if tsnr_optcom > 0:
        html.append("<h4 style='margin-top: 1rem;'>Optimal Combination</h4>")
        html.append("<div class='metrics-summary'>")
        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>Optcom tSNR</div>"
            f"<div class='metric-item-value'>{tsnr_optcom:.1f}</div>"
            f"</div>"
        )
        color = "#27ae60" if improvement >= 20 else "#f1c40f" if improvement >= 10 else "#e74c3c"
        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>tSNR Improvement</div>"
            f"<div class='metric-item-value' style='color: {color};'>{improvement:+.1f}%</div>"
            f"</div>"
        )
        html.append("</div>")

    # Tedana metrics
    if tedana:
        html.append("<h4 style='margin-top: 1rem;'>Tedana Denoising</h4>")
        html.append("<div class='metrics-summary'>")

        n_total = tedana.get("n_components_total", 0)
        n_accepted = tedana.get("n_components_accepted", 0)
        n_rejected = tedana.get("n_components_rejected", 0)

        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>Components</div>"
            f"<div class='metric-item-value'>{n_total}</div>"
            f"</div>"
        )

        accept_rate = tedana.get("acceptance_rate", 0) * 100
        color = "#27ae60" if 20 <= accept_rate <= 60 else "#f1c40f"
        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>Accepted</div>"
            f"<div class='metric-item-value' style='color: {color};'>{n_accepted} ({accept_rate:.0f}%)</div>"
            f"</div>"
        )

        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>Rejected</div>"
            f"<div class='metric-item-value' style='color: #e74c3c;'>{n_rejected}</div>"
            f"</div>"
        )

        var_accepted = tedana.get("variance_explained_accepted", 0)
        html.append(
            f"<div class='metric-item'>"
            f"<div class='metric-item-label'>Variance (BOLD)</div>"
            f"<div class='metric-item-value'>{var_accepted:.1f}%</div>"
            f"</div>"
        )

        html.append("</div>")

        # Classification tags
        tags = tedana.get("classification_tags", {})
        if tags:
            html.append("<details style='margin-top: 0.5rem;'>")
            html.append("<summary style='cursor: pointer; padding: 0.3rem;'>Classification breakdown</summary>")
            html.append("<ul style='margin-top: 0.5rem;'>")
            for tag, count in sorted(tags.items(), key=lambda x: -x[1])[:10]:
                html.append(f"<li>{tag}: {count}</li>")
            html.append("</ul>")
            html.append("</details>")

    # Flags
    flags = multiecho_report.get("flags", [])
    if flags:
        html.append("<div class='warnings' style='margin-top: 1rem;'>")
        html.append("<strong>⚠ Multi-echo QA Flags:</strong>")
        html.append("<ul>")
        for flag in flags:
            html.append(f"<li>{flag}</li>")
        html.append("</ul>")
        html.append("</div>")

    html.append("</div>")
    html.append("</details>")

    return "\n".join(html)


def render_analysis_info_section(analysis_metadata: Dict) -> str:
    """Render analysis information and interactive threshold controls.

    Parameters
    ----------
    analysis_metadata : dict
        Analysis metadata containing config, versions, thresholds, etc.

    Returns
    -------
    str
        HTML for the analysis info section with interactive controls
    """
    html = ["<details class='analysis-info-section'>"]
    html.append("<summary><h3>Analysis Information & Threshold Controls</h3></summary>")
    html.append("<div class='analysis-info-content'>")

    # Provenance information
    html.append("<div class='info-group'>")
    html.append("<h4>Provenance</h4>")
    html.append("<table class='info-table'>")

    if "timestamp" in analysis_metadata:
        html.append(f"<tr><th>Analysis Date</th><td>{escape_html(analysis_metadata['timestamp'])}</td></tr>")

    if "data_source" in analysis_metadata:
        html.append(f"<tr><th>Data Source</th><td>{escape_html(str(analysis_metadata['data_source']))}</td></tr>")

    if "glob_pattern" in analysis_metadata:
        pattern = analysis_metadata['glob_pattern']
        if pattern != "manifest":
            html.append(f"<tr><th>Glob Pattern</th><td><code>{escape_html(str(pattern))}</code></td></tr>")

    if "manifest_path" in analysis_metadata and analysis_metadata["manifest_path"]:
        html.append(f"<tr><th>Manifest</th><td><code>{escape_html(str(analysis_metadata['manifest_path']))}</code></td></tr>")

    if "total_runs" in analysis_metadata:
        html.append(f"<tr><th>Total Runs</th><td>{analysis_metadata['total_runs']}</td></tr>")

    html.append("</table>")
    html.append("</div>")

    # Software versions
    if "versions" in analysis_metadata:
        versions = analysis_metadata["versions"]
        html.append("<div class='info-group'>")
        html.append("<h4>Software Versions</h4>")
        html.append("<table class='info-table'>")

        for key, value in sorted(versions.items()):
            formatted_key = key.capitalize()
            html.append(f"<tr><th>{formatted_key}</th><td>{escape_html(str(value))}</td></tr>")

        html.append("</table>")
        html.append("</div>")

    # Interactive threshold controls
    if "thresholds" in analysis_metadata:
        thresholds = analysis_metadata["thresholds"]
        html.append("<div class='info-group threshold-controls'>")
        html.append("<h4>QA Thresholds (Interactive)</h4>")
        html.append("<p class='threshold-help'>Adjust thresholds to see how they affect run classifications in real-time. Changes are temporary and local to your browser.</p>")

        # Define threshold metadata (label, description, min, max, step, default)
        threshold_specs = {
            "dvars_z_threshold": {
                "label": "DVARS Z-score",
                "description": "Z-score for DVARS outlier detection",
                "min": 1.0,
                "max": 5.0,
                "step": 0.1,
            },
            "fd_threshold": {
                "label": "Framewise Displacement",
                "description": "Threshold for high-motion timepoints (mm)",
                "min": 0.1,
                "max": 1.0,
                "step": 0.05,
            },
            "fd_median_threshold": {
                "label": "Median FD",
                "description": "Median FD threshold for run quality (mm)",
                "min": 0.1,
                "max": 1.0,
                "step": 0.05,
            },
            "outlier_threshold": {
                "label": "Outlier Fraction",
                "description": "Max fraction of outlier timepoints per run",
                "min": 0.01,
                "max": 0.2,
                "step": 0.01,
            },
            "tsnr_drop_threshold": {
                "label": "tSNR Drop",
                "description": "Fractional tSNR drop threshold",
                "min": 0.1,
                "max": 0.5,
                "step": 0.05,
            },
            "slice_intensity_threshold": {
                "label": "Slice Intensity",
                "description": "Slice intensity z-score threshold",
                "min": 1.0,
                "max": 5.0,
                "step": 0.5,
            },
            "outlier_metric_threshold": {
                "label": "Mahalanobis Distance",
                "description": "Multivariate outlier detection threshold",
                "min": 2.0,
                "max": 5.0,
                "step": 0.5,
            },
        }

        html.append("<div class='threshold-grid'>")

        for threshold_key, spec in threshold_specs.items():
            if threshold_key in thresholds:
                current_value = thresholds[threshold_key]
                html.append("<div class='threshold-control'>")
                html.append(f"<label for='threshold-{threshold_key}'><strong>{spec['label']}</strong></label>")
                html.append(f"<p class='threshold-description'>{spec['description']}</p>")
                html.append("<div class='threshold-input-group'>")
                html.append(
                    f"<input type='range' "
                    f"id='threshold-{threshold_key}' "
                    f"class='threshold-slider' "
                    f"data-threshold-key='{threshold_key}' "
                    f"min='{spec['min']}' "
                    f"max='{spec['max']}' "
                    f"step='{spec['step']}' "
                    f"value='{current_value}' />"
                )
                html.append(
                    f"<input type='number' "
                    f"id='threshold-{threshold_key}-value' "
                    f"class='threshold-value-input' "
                    f"data-threshold-key='{threshold_key}' "
                    f"min='{spec['min']}' "
                    f"max='{spec['max']}' "
                    f"step='{spec['step']}' "
                    f"value='{current_value}' />"
                )
                html.append("</div>")
                html.append("</div>")

        html.append("</div>")

        # Action buttons
        html.append("<div class='threshold-actions'>")
        html.append("<button id='reset-thresholds-btn' class='btn-secondary'>Reset to Defaults</button>")
        html.append("<button id='export-exclusions-btn' class='btn-primary'>Export Updated Exclusion List</button>")
        html.append("</div>")

        html.append("</div>")

    html.append("</div>")
    html.append("</details>")

    return "\n".join(html)
