"""Section rendering functions for QA HTML reports.

This module contains functions that render specific sections of QA reports.

Note: render_alignment_section, render_multiecho_section, and
render_analysis_info_section have been migrated to Jinja2 templates in Phase 1
and removed from this module. See templates/components/ for the new implementations.
"""

from typing import Dict, List

from .utils import (
    format_metric_name,
    get_metric_tooltip,
    get_metric_standard,
    format_metric_value,
    escape_html,
)


def render_metrics_table(metrics: Dict[str, float], level: str = "run") -> str:
    """Render metrics as an HTML table with tooltips.

    Parameters
    ----------
    metrics : dict
        Dictionary of metric names to values
    level : str, optional
        Context level (run, session, subject), by default "run"

    Returns
    -------
    str
        HTML string for metrics table

    Examples
    --------
    >>> metrics = {'tsnr_median': 45.2, 'fd_median': 0.15}
    >>> html = render_metrics_table(metrics)
    >>> 'tsnr_median' in html
    True
    """
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
    """Render key metrics as summary cards.

    Parameters
    ----------
    metrics : dict
        Dictionary of metric names to values
    key_metrics : list of str
        List of metric names to display as summary cards

    Returns
    -------
    str
        HTML string for metrics summary cards

    Examples
    --------
    >>> metrics = {'tsnr_median': 45.2, 'fd_median': 0.15, 'gcor': 0.03}
    >>> key_metrics = ['tsnr_median', 'fd_median']
    >>> html = render_metrics_summary(metrics, key_metrics)
    >>> 'tsnr_median' in html
    True
    """
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
