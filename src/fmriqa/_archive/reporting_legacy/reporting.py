"""Refactored hierarchical HTML report generation using Jinja2 templates."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .report_templates import (
    create_template_environment,
    inline_static_files,
    render_subject_report,
    render_study_report,
)
from fmriqa.io.structures import StudyResults, SubjectResults, SessionResults, RunResult

# Import utilities from report_components
from .report_components import (
    METRIC_TOOLTIPS,
    METRIC_STANDARDS,
    FLAG_DESCRIPTIONS,
    COMPARISON_METRICS,
    format_run_label,
    format_metric_name,
    format_metric_value,
    escape_html,
    escape_js_string,
    relative_asset_path,
    compute_session_metrics,
    compute_subject_metrics,
    serialize_subject_for_export,
    serialize_study_for_interactive,
    render_metrics_table,
    render_metrics_summary,
    get_outlier_badge,
    get_fd_badge,
    get_coverage_badge,
    get_flag_badge,
    ensure_thumbnail,
    build_thumbnail_cards,
)

# Import context helpers for Phase 5
from .report_components.context_helpers import (
    compute_run_percentiles,
    classify_metric_value,
    get_quality_label,
    get_quality_css_class,
    compute_metric_position,
    format_metric_with_context,
)


def generate_subject_report(
    subject: SubjectResults,
    output_dir: Path,
    session_consistency: Dict[str, Dict],
    alignment_report: Optional[Dict] = None,
    metric_distributions: Optional[Dict] = None,
) -> Path:
    """Generate a single report for a subject using Jinja2 templates.

    Parameters
    ----------
    subject : SubjectResults
        Subject results
    output_dir : Path
        Output directory
    session_consistency : dict
        Session consistency metrics
    alignment_report : dict, optional
        Cross-session alignment report
    metric_distributions : dict, optional
        Study-wide metric distributions for percentile calculations

    Returns
    -------
    Path
        Path to the generated report
    """
    # Create Jinja2 environment
    template_env = create_template_environment()

    # Get inline static content
    static_content = inline_static_files(output_dir)

    # Calculate summary stats
    total_runs = sum(len(session.runs) for session in subject.sessions)
    total_flagged = sum(
        1 for session in subject.sessions
        for run in session.runs
        if any(run.flags.values())
    )

    # Build thumbnail cards
    thumb_cards = build_thumbnail_cards(subject, output_dir)

    # Compute subject metrics
    subject_metrics = compute_subject_metrics(subject.sessions)

    # Determine key metrics
    key_metrics = []
    for key in ["tsnr_median", "fd_median", "coverage", "gcor"]:
        if key in subject_metrics:
            key_metrics.append(key)
        elif f"{key}_median" in subject_metrics:
            key_metrics.append(f"{key}_median")
        elif f"{key}_mean" in subject_metrics:
            key_metrics.append(f"{key}_mean")

    # Prepare export data
    export_data = serialize_subject_for_export(subject, session_consistency)

    # Prepare longitudinal timeline data
    longitudinal_data = prepare_longitudinal_data(subject)

    # Prepare template context
    context = {
        # Subject data
        'subject': subject,
        'total_runs': total_runs,
        'total_flagged': total_flagged,
        'thumb_cards': thumb_cards,
        'subject_metrics': subject_metrics,
        'key_metrics': key_metrics,
        'alignment_report': alignment_report,
        'output_dir': output_dir,
        'session_consistency': session_consistency,
        'export_data': export_data,
        'longitudinal_data': longitudinal_data,
        'metric_distributions': metric_distributions,  # Phase 5: For percentile context

        # Static assets (inlined)
        'css_path': f"<style>{static_content['css_inline']}</style>",
        'js_common_path': f"<script>{static_content['js_common']}</script>",
        'js_quality_controls_path': f"<script>{static_content['js_quality_controls']}</script>",
        'js_navigation_path': f"<script>{static_content['js_navigation']}</script>",
        'js_export_path': f"<script>{static_content['js_export']}</script>",
        'js_views_path': f"<script>{static_content['js_views']}</script>",
        'js_threshold_controls_path': f"<script>{static_content['js_threshold_controls']}</script>",
        'js_timeline_path': f"<script>{static_content['js_timeline']}</script>",
        'js_detail_panel_path': f"<script>{static_content['js_detail_panel']}</script>",

        # Helper functions
        'render_metrics_summary': render_metrics_summary,
        'format_run_label': format_run_label,
        'escape_html': escape_html,
        'escape_js_string': escape_js_string,

        # Phase 5: Context helpers for metrics
        'compute_run_percentiles': compute_run_percentiles,
        'classify_metric_value': classify_metric_value,
        'get_quality_label': get_quality_label,
        'get_quality_css_class': get_quality_css_class,
        'compute_metric_position': compute_metric_position,
        'format_metric_with_context': format_metric_with_context,

        # Search function name
        'search_function': 'filterRuns()',
    }

    # Render report
    report_path = output_dir / "subject_report.html"
    return render_subject_report(template_env, context, report_path)


def generate_study_report(
    study: StudyResults,
    output_dir: Path,
    study_aggregate_path: Optional[Path] = None,
    metric_distributions: Optional[Dict] = None,
) -> Path:
    """Generate main study report using Jinja2 templates.

    Parameters
    ----------
    study : StudyResults
        Study results
    output_dir : Path
        Output directory
    study_aggregate_path : Path, optional
        Path to study aggregate figure
    metric_distributions : dict, optional
        Study-wide metric distributions (computed once to avoid redundancy)

    Returns
    -------
    Path
        Path to the generated report
    """
    # Create Jinja2 environment
    template_env = create_template_environment()

    # Get inline static content
    static_content = inline_static_files(output_dir)

    # Calculate total runs
    total_runs = sum(
        len(session.runs) for subject in study.subjects for session in subject.sessions
    )

    # Compute study quality summary
    quality_summary = compute_study_quality_summary(study)

    # Prepare paths
    if study_aggregate_path and study_aggregate_path.exists():
        study_aggregate_rel = relative_asset_path(study_aggregate_path, output_dir)
    else:
        study_aggregate_rel = None

    # Prepare group plots paths
    group_plots_rel = {}
    if study.group_plots:
        for key, path in study.group_plots.items():
            if path and path.exists():
                group_plots_rel[key] = relative_asset_path(path, output_dir)

    # Prepare interactive data
    interactive_data = None
    if total_runs >= 3:
        interactive_data = serialize_study_for_interactive(study)

    # Compute subject metrics for display
    subject_metrics_map = {}
    for subject in study.subjects:
        subject_metrics_map[subject.subject] = compute_subject_metrics(subject.sessions)

    # Compute metric distributions across study (if not already provided)
    if metric_distributions is None:
        metric_distributions = compute_metric_distributions(study)

    # Prepare outlier data for template
    outlier_data = prepare_outlier_data(study)

    # Prepare exclusion data for template
    exclusion_data = prepare_exclusion_data(study)

    # Chart script for interactive dashboard
    chart_script = _get_chart_script()

    # Prepare template context
    context = {
        # Study data
        'study': study,
        'total_runs': total_runs,
        'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'study_aggregate_path': study_aggregate_rel,
        'output_dir': output_dir,
        'analysis_metadata': study.analysis_metadata,

        # Quality summary
        'quality_summary': quality_summary,
        'metric_distributions': metric_distributions,

        # Sections
        'outlier_data': outlier_data,
        'exclusion_data': exclusion_data,
        'chart_script': chart_script,

        # Interactive data
        'interactive_data': interactive_data,
        'comparison_metrics': COMPARISON_METRICS,

        # Subject metrics
        'subject_metrics_map': subject_metrics_map,

        # Static assets (inlined)
        'css_path': f"<style>{static_content['css_inline']}</style>",
        'js_common_path': f"<script>{static_content['js_common']}</script>",
        'js_study_path': f"<script>{static_content['js_study']}</script>",
        'js_threshold_controls_path': f"<script>{static_content['js_threshold_controls']}</script>",

        # Helper functions
        'format_metric_name': format_metric_name,
        'format_metric_value': format_metric_value,
        'relative_asset_path': relative_asset_path,

        # Search function name
        'search_function': 'filterSubjects()',
    }

    # Render report
    report_path = output_dir / "index.html"
    return render_study_report(template_env, context, report_path)


def prepare_longitudinal_data(subject: SubjectResults) -> Dict:
    """Prepare longitudinal timeline data for vertical metric visualization.

    Parameters
    ----------
    subject : SubjectResults
        Subject results containing all sessions and runs

    Returns
    -------
    Dict
        Dictionary with longitudinal data for timeline rendering
    """
    runs_chronological = []

    # Collect all runs in chronological order (session by session)
    for session in subject.sessions:
        session_label = f"ses-{session.session}"
        for run in session.runs:
            run_label = format_run_label(run.info.run)
            run_id = f"{subject.get_identifier()}_{session_label}_{run_label}"

            runs_chronological.append({
                "run_id": run_id,
                "session": session_label,
                "run_label": run_label,
                "metrics": run.metrics,
                "flags": run.flags,
            })

    # Calculate min/max from actual data with 10% padding
    def calculate_range(metric_key, all_runs):
        """Calculate min/max range for a metric with padding."""
        values = [
            run.metrics.get(metric_key)
            for session in subject.sessions
            for run in session.runs
            if run.metrics.get(metric_key) is not None
        ]

        if not values:
            return 0, 1  # Default range if no data

        data_min = min(values)
        data_max = max(values)

        # Add 10% padding on each side
        range_size = data_max - data_min
        if range_size == 0:
            # If all values are the same, create a small range around the value
            padding = abs(data_min) * 0.1 if data_min != 0 else 0.1
            range_min = data_min - padding
            range_max = data_min + padding
        else:
            padding = range_size * 0.1
            range_min = data_min - padding
            range_max = data_max + padding

        # Round to 2 decimal places for clean display
        return round(range_min, 2), round(range_max, 2)

    # Define available metrics with metadata and data-driven ranges
    available_metrics = [
        {
            "key": "tsnr_median",
            "label": "tSNR",
            "threshold": 30.0,
            "direction": "higher",
            "min": calculate_range("tsnr_median", runs_chronological)[0],
            "max": calculate_range("tsnr_median", runs_chronological)[1],
            "unit": "",
        },
        {
            "key": "fd_median",
            "label": "FD",
            "threshold": 0.5,
            "direction": "lower",
            "min": calculate_range("fd_median", runs_chronological)[0],
            "max": calculate_range("fd_median", runs_chronological)[1],
            "unit": "mm",
        },
        {
            "key": "dvars_std_median",
            "label": "DVARS",
            "threshold": 1.5,
            "direction": "lower",
            "min": calculate_range("dvars_std_median", runs_chronological)[0],
            "max": calculate_range("dvars_std_median", runs_chronological)[1],
            "unit": "",
        },
        {
            "key": "coverage",
            "label": "Coverage",
            "threshold": 0.85,
            "direction": "higher",
            "min": max(0.7, calculate_range("coverage", runs_chronological)[0]),  # Floor at 0.7
            "max": min(1.0, calculate_range("coverage", runs_chronological)[1]),  # Ceiling at 1.0
            "unit": "",
        },
        {
            "key": "gcor",
            "label": "GCOR",
            "threshold": None,
            "direction": "lower",
            "min": calculate_range("gcor", runs_chronological)[0],
            "max": calculate_range("gcor", runs_chronological)[1],
            "unit": "",
        },
    ]

    return {
        "runs": runs_chronological,
        "available_metrics": available_metrics,
        "default_metrics": ["tsnr_median", "fd_median"],
    }


def prepare_outlier_data(study: StudyResults) -> Optional[Dict]:
    """Prepare outlier detection data for template rendering.

    Parameters
    ----------
    study : StudyResults
        Study results containing outlier report

    Returns
    -------
    Optional[Dict]
        Dictionary with outlier data for template, or None if no outliers
    """
    outlier_report = getattr(study, 'outlier_report', {})
    has_any_outliers = (
        study.overall_outliers or
        outlier_report.get('extreme_motion', []) or
        outlier_report.get('low_tsnr', [])
    )

    if not has_any_outliers:
        return None

    tsnr_thresh = outlier_report.get('tsnr_threshold', 30.0)

    # Build outlier explanations dictionary
    outlier_explanations = {}

    for run_id in outlier_report.get('multivariate_outliers', []):
        if run_id not in outlier_explanations:
            outlier_explanations[run_id] = []
        distance = outlier_report.get('mahalanobis_distances', {}).get(run_id, 0)
        outlier_explanations[run_id].append(f"Unusual metric pattern (statistical distance: {distance:.1f})")

    for run_id in outlier_report.get('extreme_motion', []):
        if run_id not in outlier_explanations:
            outlier_explanations[run_id] = []
        outlier_explanations[run_id].append("Excessive head motion")

    for run_id in outlier_report.get('low_tsnr', []):
        if run_id not in outlier_explanations:
            outlier_explanations[run_id] = []
        outlier_explanations[run_id].append(f"Low signal quality (tSNR < {tsnr_thresh:.0f})")

    univariate = outlier_report.get('univariate_outliers', {})
    for metric, run_ids in univariate.items():
        metric_name = format_metric_name(metric)
        for run_id in run_ids:
            if run_id not in outlier_explanations:
                outlier_explanations[run_id] = []
            outlier_explanations[run_id].append(f"Univariate outlier: {metric_name}")

    return {
        'tsnr_threshold': tsnr_thresh,
        'outlier_explanations': outlier_explanations,
        'summary': outlier_report.get('summary', {}),
        'warnings': outlier_report.get('warnings', []),
    }


def prepare_exclusion_data(study: StudyResults) -> Optional[Dict]:
    """Prepare exclusion recommendations data for template rendering.

    Parameters
    ----------
    study : StudyResults
        Study results containing exclusion report

    Returns
    -------
    Optional[Dict]
        Dictionary with exclusion data for template, or None if no exclusion report
    """
    exclusion_report = getattr(study, 'exclusion_report', None)
    if exclusion_report is None:
        return None

    # Filter excluded runs
    excluded_runs = [e for e in exclusion_report.run_exclusions if e.excluded]

    # Filter high scrubbing runs (>10% data loss)
    scrubbing = exclusion_report.volume_scrubbing
    high_scrub_runs = sorted(
        [s for s in scrubbing if s.data_loss_percent > 10],
        key=lambda x: -x.data_loss_percent
    )

    # Reason labels mapping
    reason_labels = {
        'fd_median': 'High median FD',
        'fd_percent': 'High % motion volumes',
        'tsnr_min': 'Low absolute tSNR',
        'tsnr_percentile': 'Low tSNR percentile',
        'dvars_percent': 'High % DVARS volumes',
        'outlier_percent': 'High % outlier volumes',
        'mahalanobis': 'Multivariate outlier',
        'coverage': 'Low brain coverage',
    }

    return {
        'summary': exclusion_report.summary,
        'stringency': exclusion_report.stringency,
        'criteria': exclusion_report.criteria,
        'excluded_runs': excluded_runs,
        'high_scrub_runs': high_scrub_runs,
        'reason_labels': reason_labels,
    }


def _get_chart_script() -> str:
    """Get the Chart.js initialization script for study reports."""
    return """<script>
let chart = null;
const subjectColors = {};
const colorPalette = ['#0d7377', '#e74c3c', '#3498db', '#2ecc71', '#9b59b6', '#f39c12', '#1abc9c', '#e67e22', '#34495e', '#95a5a6'];

// Assign colors to subjects
qaData.subjects.forEach((subj, i) => {
    subjectColors[subj] = colorPalette[i % colorPalette.length];
});

function getColor(run, colorBy) {
    if (colorBy === 'subject') return subjectColors[run.subject];
    if (colorBy === 'session') {
        const sessions = [...new Set(qaData.runs.map(r => r.session))];
        return colorPalette[sessions.indexOf(run.session) % colorPalette.length];
    }
    if (colorBy === 'flagged') {
        const hasFlags = Object.values(run.flags || {}).some(v => v);
        return hasFlags ? '#e74c3c' : '#2ecc71';
    }
    return '#0d7377';
}

function updateChart() {
    const xMetric = document.getElementById('xMetricSelect').value;
    const yMetric = document.getElementById('yMetricSelect').value;
    const colorBy = document.getElementById('colorBySelect').value;
    const subjectFilter = document.getElementById('subjectFilter').value;

    let filteredRuns = qaData.runs;
    if (subjectFilter !== 'all') {
        filteredRuns = qaData.runs.filter(r => r.subject === subjectFilter);
    }

    const data = filteredRuns
        .filter(r => r.metrics[xMetric] != null && r.metrics[yMetric] != null)
        .map(r => ({
            x: r.metrics[xMetric],
            y: r.metrics[yMetric],
            runData: r,
            backgroundColor: getColor(r, colorBy),
            borderColor: getColor(r, colorBy),
        }));

    const xLabel = qaData.metrics.find(m => m.key === xMetric)?.label || xMetric;
    const yLabel = qaData.metrics.find(m => m.key === yMetric)?.label || yMetric;

    if (chart) chart.destroy();

    const ctx = document.getElementById('comparisonChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                data: data,
                pointRadius: 6,
                pointHoverRadius: 9,
                backgroundColor: data.map(d => d.backgroundColor),
                borderColor: data.map(d => d.borderColor),
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const run = ctx.raw.runData;
                            return `${run.id}: (${ctx.raw.x.toFixed(2)}, ${ctx.raw.y.toFixed(2)})`;
                        }
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: xLabel, font: { weight: 'bold' } } },
                y: { title: { display: true, text: yLabel, font: { weight: 'bold' } } }
            },
            onClick: (evt, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    const run = data[idx].runData;
                    showRunDetails(run);
                }
            }
        }
    });
}

function showRunDetails(run) {
    const panel = document.getElementById('runDetailsPanel');
    const title = document.getElementById('runDetailsTitle');
    const grid = document.getElementById('runDetailsGrid');

    title.textContent = run.id;
    panel.classList.add('active');

    let html = '';
    qaData.metrics.forEach(m => {
        const val = run.metrics[m.key];
        const displayVal = val != null ? val.toFixed(3) : 'N/A';
        html += `<div class="run-detail-item"><span class="label">${m.label}</span><span class="value">${displayVal}</span></div>`;
    });

    // Show flags
    const activeFlags = Object.entries(run.flags || {}).filter(([k, v]) => v).map(([k]) => k);
    if (activeFlags.length > 0) {
        html += `<div class="run-detail-item" style="grid-column: 1/-1; background: #fee2e2;"><span class="label">Flags</span><span class="value" style="color: #9b2c2c;">${activeFlags.join(', ')}</span></div>`;
    }

    grid.innerHTML = html;
}

// Initialize chart on load
document.addEventListener('DOMContentLoaded', updateChart);
</script>"""


def compute_study_quality_summary(study: StudyResults) -> Dict:
    """Compute quality summary statistics across all runs in the study.

    Categorizes runs into good (0 flags), warning (1-2 flags), and bad (3+ flags).

    Parameters
    ----------
    study : StudyResults
        Study results containing all subjects and runs

    Returns
    -------
    Dict
        Dictionary with counts and percentages for each quality category
    """
    good_count = 0
    warning_count = 0
    bad_count = 0
    total_runs = 0

    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                total_runs += 1
                flag_count = sum(run.flags.values())

                if flag_count == 0:
                    good_count += 1
                elif flag_count <= 2:
                    warning_count += 1
                else:
                    bad_count += 1

    # Calculate percentages
    good_percent = (good_count / total_runs * 100) if total_runs > 0 else 0
    warning_percent = (warning_count / total_runs * 100) if total_runs > 0 else 0
    bad_percent = (bad_count / total_runs * 100) if total_runs > 0 else 0

    return {
        'good_count': good_count,
        'warning_count': warning_count,
        'bad_count': bad_count,
        'total_runs': total_runs,
        'good_percent': good_percent,
        'warning_percent': warning_percent,
        'bad_percent': bad_percent,
    }


def compute_metric_distributions(study: StudyResults) -> Dict:
    """Compute statistical distributions for each metric across all runs in the study.

    Parameters
    ----------
    study : StudyResults
        Study results containing all subjects and runs

    Returns
    -------
    Dict
        Dictionary mapping metric names to their statistical distributions
        (min, max, median, mean, std)
    """
    from collections import defaultdict
    import statistics

    # Collect all metric values
    metric_values = defaultdict(list)

    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                if run.metrics:
                    for key, value in run.metrics.items():
                        if isinstance(value, (int, float)) and value is not None:
                            metric_values[key].append(value)

    # Compute distributions
    distributions = {}
    for metric, values in metric_values.items():
        if len(values) > 0:
            distributions[metric] = {
                'min': min(values),
                'max': max(values),
                'median': statistics.median(values),
                'mean': statistics.mean(values),
                'std': statistics.stdev(values) if len(values) > 1 else 0,
                'count': len(values),
                'all_values': values,  # Needed for percentile calculations (Phase 5)
            }

    return distributions
