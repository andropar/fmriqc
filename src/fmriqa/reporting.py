"""Hierarchical HTML report generation."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

from .structures import StudyResults, SubjectResults, SessionResults, RunResult
from .visualization import create_run_thumbnail

# Import constants and utilities from report_components
from .report_components import (
    METRIC_TOOLTIPS,
    METRIC_STANDARDS,
    FLAG_DESCRIPTIONS,
    COMPARISON_METRICS,
    CSS_STYLE,
    get_subject_report_scripts,
    get_study_report_scripts,
    format_run_label,
    format_metric_name,
    get_metric_tooltip,
    get_metric_standard,
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
    render_alignment_section,
    render_multiecho_section,
    render_analysis_info_section,
    get_outlier_badge,
    get_fd_badge,
    get_coverage_badge,
    get_flag_badge,
    ensure_thumbnail,
    build_thumbnail_cards,
)


# Private helper functions specific to reporting
def generate_subject_report(
    subject: SubjectResults,
    output_dir: Path,
    session_consistency: Dict[str, Dict],
    alignment_report: Optional[Dict] = None,
) -> Path:
    """Generate a single accordion-style report for a subject.

    Parameters
    ----------
    subject : SubjectResults
        Subject results
    output_dir : Path
        Output directory
    session_consistency : dict
        Session consistency metrics
    alignment_report : dict, optional
        Cross-session alignment report (from CrossSessionReport.to_dict())
    """

    html = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>QA Report - {subject.get_identifier()}</title>",
        "<meta name='description' content='fMRI Quality Assurance Report'>",
        CSS_STYLE,
        "</head><body>",
        "<a href='#main-content' class='skip-link'>Skip to main content</a>",
        "<div class='search-box' role='search'><span aria-hidden='true'>🔍</span><input type='text' id='searchInput' placeholder='Search runs...' oninput='filterRuns()' aria-label='Search runs'></div>",
        "<button class='export-btn' onclick='openExportModal()' aria-label='Export data'><span aria-hidden='true'>📥</span> Export</button>",
        "<button class='dark-mode-toggle' onclick='toggleDarkMode()' aria-label='Toggle dark mode'><span aria-hidden='true'>🌙</span> Dark</button>",
        "<button class='sidebar-toggle' onclick='toggleSidebar()' aria-label='Open help sidebar'><span aria-hidden='true'>ℹ️</span> Help</button>",
        "<div class='sidebar-overlay' onclick='toggleSidebar()'></div>",
        "<div class='export-modal-overlay' id='exportOverlay' onclick='closeExportModal()'></div>",
        "<div class='export-modal' id='exportModal'>",
        "<button class='export-modal-close' onclick='closeExportModal()'>×</button>",
        "<h3>Export Data</h3>",
        "<div class='export-option' onclick='exportCSV()'>",
        "<span class='export-option-icon'>📊</span>",
        "<div class='export-option-content'>",
        "<h4>CSV (Spreadsheet)</h4>",
        "<p>Metrics table for Excel, Google Sheets, or statistical software. One row per run.</p>",
        "</div></div>",
        "<div class='export-option' onclick='exportJSON()'>",
        "<span class='export-option-icon'>📋</span>",
        "<div class='export-option-content'>",
        "<h4>JSON (Complete Data)</h4>",
        "<p>Full structured data including metrics, flags, consistency, and metadata.</p>",
        "</div></div>",
        "<div class='export-option' onclick='exportFlagged()'>",
        "<span class='export-option-icon'>⚠️</span>",
        "<div class='export-option-content'>",
        "<h4>Flagged Runs Only</h4>",
        "<p>CSV with only runs that have quality flags for review.</p>",
        "</div></div>",
        "</div>",
        "<div class='easter-egg' id='easterEgg'>",
        "<button class='easter-egg-close' onclick='closeEasterEgg()'>×</button>",
        "<h2>🧠 You found the secret!</h2>",
        "<p>Congratulations! You've unlocked the Konami code easter egg. Your fMRI data is in good hands.</p>",
        "<p style='font-size: 2rem; margin: 1rem 0;'>🧠 → 🧠 → 🧠</p>",
        "<p><em>Keep up the great QA work!</em></p>",
        "</div>",
        "<div class='keyboard-hint' id='keyboardHint'>",
        "<strong>Keyboard:</strong> ",
        "<kbd>J</kbd>/<kbd>K</kbd> Next/prev run | <kbd>Space</kbd> Toggle good/bad | <kbd>/</kbd> Search | <kbd>F</kbd> Next flagged | <kbd>E</kbd> Expand | <kbd>C</kbd> Collapse",
        "</div>",
        "<div class='sidebar' id='sidebar'>",
        "<button class='sidebar-close' onclick='toggleSidebar()'>×</button>",
        "<h3>QA Report Guide</h3>",
        "<h4>Metrics</h4>",
        "<p>Hover over any metric name to see its description. Key metrics include:</p>",
        "<ul>",
        "<li><strong>tSNR:</strong> Temporal signal-to-noise ratio - measures signal quality over time</li>",
        "<li><strong>FD:</strong> Framewise displacement - measures head motion between volumes</li>",
        "<li><strong>DVARS:</strong> Rate of change of BOLD signal - detects signal artifacts</li>",
        "<li><strong>Coverage:</strong> Fraction of brain covered by the mask</li>",
        "<li><strong>GCOR:</strong> Global correlation - measures global signal strength</li>",
        "</ul>",
        "<h4>Aggregate Plots</h4>",
        "<p>Aggregate plots show spatial maps averaged across all runs in a session. These include:</p>",
        "<ul>",
        "<li><strong>Mean:</strong> Average signal intensity</li>",
        "<li><strong>tSNR:</strong> Temporal signal-to-noise ratio map</li>",
        "<li><strong>CoV:</strong> Coefficient of variation - measures variability</li>",
        "<li><strong>Dropout:</strong> Areas with signal loss</li>",
        "<li><strong>AR(1):</strong> Lag-1 autocorrelation - measures temporal structure</li>",
        "</ul>",
        "<h4>Carpet Plots</h4>",
        "<p>Carpet plots visualize the time series of all brain voxels, sorted by z-coordinate. They help identify:</p>",
        "<ul>",
        "<li>Motion artifacts (horizontal stripes)</li>",
        "<li>Physiological noise (periodic patterns)</li>",
        "<li>Signal drift over time</li>",
        "<li>Outlier volumes</li>",
        "</ul>",
        "<p>The top panel shows framewise displacement, the middle shows voxel time series (z-scored), and the bottom shows global signal.</p>",
        "</div>",
    ]

    # Build navigation panel data
    total_runs = sum(len(session.runs) for session in subject.sessions)
    total_flagged = sum(
        1 for session in subject.sessions
        for run in session.runs
        if any(run.flags.values())
    )
    # Build thumbnail cards for inline display
    thumb_cards = build_thumbnail_cards(subject, output_dir)

    html.append("<div class='nav-panel' id='navPanel'>")
    html.append("<div class='nav-panel-header'>")
    html.append("<h4>Navigation</h4>")
    html.append(f"<div class='nav-progress'><span id='reviewCount'>0</span>/<span>{total_runs}</span> reviewed")
    html.append("<div class='nav-progress-bar'><div class='nav-progress-fill' id='progressFill' style='width: 0%'></div></div></div>")
    html.append("<div class='nav-filters'>")
    html.append("<button class='nav-filter-btn active' id='filterAll' onclick='filterNav(\"all\")'>All</button>")
    html.append(f"<button class='nav-filter-btn' id='filterFlagged' onclick='filterNav(\"flagged\")'>{total_flagged} Flagged</button>")
    html.append("</div></div>")
    html.append("<div class='nav-panel-body' id='navBody'>")

    for session in subject.sessions:
        session_id = f"{subject.subject}_{session.session}"
        html.append(f"<div class='nav-session' data-session='{session.session}'>")
        html.append(f"<div class='nav-item nav-session-header' onclick=\"document.getElementById('session-details-{session_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})\">")
        html.append(f"<span class='nav-item-dot'></span><span class='nav-item-label'><strong>ses-{session.session}</strong></span>")
        html.append("</div>")

        for run in session.runs:
            # Build run_id to match the details section format
            session_label = f"ses-{session.session}"
            run_label = format_run_label(run.info.run)
            run_id = f"{subject.get_identifier()}_{session_label}_{run_label}"
            run_id_js = escape_js_string(run_id)
            run_id_html = escape_html(run_id)

            flag_count = sum(1 for v in run.flags.values() if v)
            dot_class = "flagged" if flag_count > 0 else ""
            flag_badge = f"<span class='nav-item-flags'>{flag_count}</span>" if flag_count > 0 else ""
            has_flags = "true" if flag_count > 0 else "false"

            html.append(f"<div class='nav-item nav-run' data-run='{run_id_html}' data-flagged='{has_flags}' onclick=\"navigateToRun('{run_id_js}')\">")
            html.append(f"<span class='nav-item-dot {dot_class}'></span>")
            html.append(f"<span class='nav-item-label'>{run_label}</span>")
            html.append(flag_badge)
            html.append("</div>")

        html.append("</div>")

    html.append("</div></div>")
    html.append("<button class='nav-toggle-btn' onclick='toggleNavPanel()'>☰ Nav</button>")

    html.extend([
        "<main id='main-content' class='container content-with-nav' role='main'>",
        "<nav class='breadcrumb' aria-label='Breadcrumb'>",
        "<a href='../index.html'>Study overview</a>",
        f"<span aria-hidden='true'>/</span><strong aria-current='page'>{subject.get_identifier()}</strong>",
        "</nav>",
        f"<h1>{subject.get_identifier()} quality report</h1>",
        f"<p>This page summarises all {len(subject.sessions)} session(s) and their runs.</p>",
        "<div class='view-toggle'>"
        "<button class='view-btn active' id='viewThumbBtn' onclick=\"setView('thumb')\">Thumbnail view</button>"
        "<button class='view-btn' id='viewDetailBtn' onclick=\"setView('detail')\">Detail view</button>"
        "</div>",
    ])
    subject_metrics = compute_subject_metrics(subject.sessions)

    # Determine which key metrics are available
    key_metrics = []
    for key in ["tsnr_median", "fd_median", "coverage", "gcor"]:
        if key in subject_metrics:
            key_metrics.append(key)
        elif f"{key}_median" in subject_metrics:
            key_metrics.append(f"{key}_median")
        elif f"{key}_mean" in subject_metrics:
            key_metrics.append(f"{key}_mean")
    
    html.append("<section id='thumbnail-view'>")
    html.append("<h2>Thumbnail view (quick scan)</h2>")
    if thumb_cards:
        html.append(
            "<p class='thumb-guide'>Visual quick scan of all runs. Look for missing coverage, mask holes, banding/striping, or extreme brightness. "
            "Quality indicators: green (good), yellow (warning), red (issues). Click any card to jump to full details.</p>"
        )

        # View controls (filters + density)
        sessions = list(thumb_cards.keys())
        html.append("<div class='thumb-view-controls'>")
        html.append("<div class='thumb-filters'>")
        html.append("<button class='pill active' data-session='all' onclick=\"filterThumbs('all')\">All</button>")
        for sess in sessions:
            html.append(f"<button class='pill' data-session='{sess}' onclick=\"filterThumbs('{sess}')\">{sess}</button>")
        html.append("</div>")
        html.append("<div class='thumb-density-toggle'>")
        html.append("<button class='density-btn' onclick=\"setThumbDensity('compact', this)\">Compact</button>")
        html.append("<button class='density-btn active' onclick=\"setThumbDensity('comfortable', this)\">Comfortable</button>")
        html.append("<button class='density-btn' onclick=\"setThumbDensity('spacious', this)\">Spacious</button>")
        html.append("</div>")
        html.append("</div>")

        # Session groups
        for sess, cards in thumb_cards.items():
            html.append(f"<details class='thumb-session' open data-session='{sess}'>")
            html.append(f"<summary><strong>{sess}</strong> <span class='session-meta'>{len(cards)} runs</span></summary>")
            html.append("<div class='thumb-grid' id='thumb-grid-{sess}'>")
            for card in cards:
                # Determine overall quality class
                quality_class = "good"
                if card['flag_class'] == 'badge-bad' or card['outlier_class'] == 'badge-bad':
                    quality_class = "bad"
                elif card['flag_class'] == 'badge-warn' or card['outlier_class'] == 'badge-warn' or card['fd_class'] == 'badge-warn':
                    quality_class = "warn"

                html.append(
                    f"<a class='thumb-card' data-session='{sess}' href='#run-details-{card['run_id']}' "
                    f"onclick=\"openDetailAndJump('{card['run_id']}'); return false;\">"
                    f"<div class='thumb-image'>"
                    f"<img src='{card['img']}' alt='Mean+mask {card['run_label']}'>"
                    f"<div class='thumb-quality-indicator {quality_class}'></div>"
                    f"</div>"
                    f"<div class='thumb-content'>"
                    f"<div class='thumb-meta'><span class='thumb-title'>{card['run_label']}</span>"
                    f"<span class='badge {card['outlier_class']}'>{card['outlier_text']}</span></div>"
                    f"<div class='thumb-badges'>"
                    f"<span class='badge {card['fd_class']}'>{card['fd_text']}</span>"
                    f"<span class='badge {card['cov_class']}'>{card['cov_text']}</span>"
                    f"<span class='badge {card['flag_class']}'>{card['flag_text']}</span>"
                    f"</div>"
                    f"<div class='thumb-subtitle'>{card['subtitle']}</div>"
                    f"</div>"
                    f"</a>"
                )
            html.append("</div>")
            html.append("</details>")
    else:
        html.append("<p>No thumbnails available for this subject.</p>")
    html.append("</section>")

    html.append("<section id='detail-view' class='hidden'>")
    html.append("<h2>Detail view</h2>")
    html.append("<p><a class='thumb-link' href='#' onclick=\"setView('thumb'); return false;\">⬅ Back to thumbnails</a></p>")

    html.append("<h2>Subject summary</h2>")
    html.append("<div class='summary-cards'>")
    html.append(
        f"<div class='card'><h3>Sessions</h3><div class='value'>{len(subject.sessions)}</div></div>"
    )
    html.append(
        f"<div class='card'><h3>Runs</h3><div class='value'>{total_runs}</div></div>"
    )
    html.append("</div>")
    
    # Subject-level metrics summary
    if subject_metrics:
        html.append("<h3>Subject-level metrics</h3>")
        html.append(render_metrics_summary(subject_metrics, key_metrics))

    # Cross-session alignment verification (CIR-208)
    if alignment_report is not None and len(subject.sessions) > 1:
        html.append(render_alignment_section(alignment_report, output_dir))

    html.append("<h2>Sessions and runs</h2>")
    for session in subject.sessions:
        session_label = f"ses-{session.session}"
        consistency = session_consistency.get(session.session, {})
        interpretation = consistency.get("consistency_interpretation")
        inconsistent_runs = consistency.get("inconsistent_runs", [])
        session_metrics = compute_session_metrics(session.runs)

        # Count flagged runs
        flagged_runs_count = sum(1 for run in session.runs if sum(run.flags.values()) > 0)
        session_is_good = flagged_runs_count == 0
        
        session_id = f"{subject.get_identifier()}_{session_label}"
        session_id_html = escape_html(session_id)
        session_id_js = escape_js_string(session_id)

        html.append(f"<details id='session-details-{session_id_html}'>")
        summary_text = f"{session_label}"
        if flagged_runs_count > 0:
            summary_text += f" <span class='session-meta'>({flagged_runs_count} flagged)</span>"
        summary_text += f" <span class='session-meta'>{len(session.runs)} runs</span>"
        quality_class = "quality-good" if session_is_good else "quality-bad"
        quality_text = "✓ Good" if session_is_good else "✗ Bad"
        html.append(
            f"<summary>"
            f"<span>{summary_text}</span>"
            f"<span class='quality-indicator {quality_class}' id='session-{session_id}' onclick='handleSessionQuality(\"{session_id_js}\", event)'>{quality_text}</span>"
            f"</summary>"
        )
        html.append("<div>")

        if interpretation:
            consistency_tooltip = "Consistency measures how similar runs are within a session. It assesses variability in key metrics (tSNR, FD, global signal) across runs. Higher consistency indicates more reliable data."
            html.append(
                f"<p><strong>Consistency:</strong> <span class='consistency-label' data-tooltip='{consistency_tooltip}'>{interpretation}</span></p>"
            )
        if inconsistent_runs:
            html.append(
                f"<p><strong>Inconsistent runs:</strong> {', '.join(format_run_label(r) for r in inconsistent_runs)}</p>"
            )

        # Session aggregate image
        if session.aggregate_figure_path and session.aggregate_figure_path.exists():
            session_img_rel = relative_asset_path(session.aggregate_figure_path, output_dir)
            html.append(
                f"<figure><figcaption>Session aggregate maps</figcaption><img src='{session_img_rel}' alt='Session aggregate maps for {session_label}'></figure>"
            )

        # Session-level metrics
        if session_metrics:
            html.append("<h3>Session-level metrics</h3>")
            session_key_metrics = []
            for key in ["tsnr_median", "fd_median", "coverage", "gcor"]:
                if key in session_metrics:
                    session_key_metrics.append(key)
                elif f"{key}_median" in session_metrics:
                    session_key_metrics.append(f"{key}_median")
                elif f"{key}_mean" in session_metrics:
                    session_key_metrics.append(f"{key}_mean")
            if session_key_metrics:
                html.append(render_metrics_summary(session_metrics, session_key_metrics))

        # Runs within session
        html.append("<h3>Runs</h3>")
        for run in session.runs:
            run_label = format_run_label(run.info.run)
            flags = sum(run.flags.values())
            run_is_good = flags == 0
            if flags == 0:
                flag_badge = "<span class='flag flag-success'>✓ 0 flags</span>"
            elif flags <= 2:
                flag_badge = f"<span class='flag flag-warning'>⚠ {flags} flag(s)</span>"
            else:
                flag_badge = f"<span class='flag flag-danger'>✗ {flags} flag(s)</span>"

            run_id = f"{subject.get_identifier()}_{session_label}_{run_label}"
            run_id_html = escape_html(run_id)
            run_id_js = escape_js_string(run_id)
            session_id_js = escape_js_string(session_id)

            quality_class = "quality-good" if run_is_good else "quality-bad"
            quality_text = "✓ Good" if run_is_good else "✗ Bad"

            html.append(f"<details id='run-details-{run_id_html}'>")
            html.append(
                f"<summary class='run-summary'>"
                f"<span>{run_label}</span>"
                f"<span class='session-meta'>{flag_badge}</span>"
                f"<span class='quality-indicator {quality_class}' id='run-{run_id_html}' data-session-id='{session_id}' onclick='handleRunQuality(\"{run_id_js}\", \"{session_id_js}\", event)'>{quality_text}</span>"
                f"</summary>"
            )
            html.append("<div>")

            # Show what flags are set at the top
            active_flags = [flag_name for flag_name, is_set in run.flags.items() if is_set]
            if active_flags:
                html.append("<div class='flag-list'>")
                html.append("<strong>⚠ Flags raised:</strong>")
                html.append("<ul>")
                for flag_name in active_flags:
                    flag_desc = FLAG_DESCRIPTIONS.get(flag_name, flag_name.replace("_", " ").title())
                    html.append(f"<li>{flag_desc}</li>")
                html.append("</ul>")
                html.append("</div>")

            # Carpet plot (first, always visible)
            if run.carpetplot_path and run.carpetplot_path.exists():
                carpet_rel = relative_asset_path(run.carpetplot_path, output_dir)
                html.append(
                    f"<figure><figcaption>Carpet plot</figcaption><img src='{carpet_rel}' alt='Carpet plot for {run_label}'></figure>"
                )

            # Main QA figure (toggleable, default closed)
            if run.figure_path and run.figure_path.exists():
                figure_rel = relative_asset_path(run.figure_path, output_dir)
                html.append("<details style='margin-top: 1.5rem;'>")
                html.append("<summary style='cursor: pointer; font-weight: 600; padding: 0.75rem; background: var(--hover); border-radius: 8px;'>QA summary plot</summary>")
                html.append("<div style='padding-top: 1rem;'>")
                html.append(
                    f"<figure><figcaption>QA summary</figcaption><img src='{figure_rel}' alt='QA summary for {run_label}'></figure>"
                )
                html.append("</div>")
                html.append("</details>")

            # Run metrics table (toggleable, default closed)
            html.append("<details style='margin-top: 1.5rem;'>")
            html.append("<summary style='cursor: pointer; font-weight: 600; padding: 0.75rem; background: var(--hover); border-radius: 8px;'>QA metrics table</summary>")
            html.append("<div style='padding-top: 1rem;'>")
            html.append(render_metrics_table(run.metrics, level="run"))
            html.append("</div>")
            html.append("</details>")

            if run.warnings:
                html.append("<div class='warnings'><strong>Warnings</strong><ul>")
                for warning in run.warnings:
                    html.append(f"<li>{warning}</li>")
                html.append("</ul></div>")

            html.append("</div>")
            html.append("</details>")

        html.append("</div>")
        html.append("</details>")

    html.append("</section>")  # end detail view
    html.append("</main>")
    html.append("<script>")
    html.append("function setView(view){")
    html.append("  const thumb = document.getElementById('thumbnail-view');")
    html.append("  const detail = document.getElementById('detail-view');")
    html.append("  const btnThumb = document.getElementById('viewThumbBtn');")
    html.append("  const btnDetail = document.getElementById('viewDetailBtn');")
    html.append("  if(view==='thumb'){")
    html.append("    thumb.classList.remove('hidden'); detail.classList.add('hidden');")
    html.append("    btnThumb.classList.add('active'); btnDetail.classList.remove('active');")
    html.append("  } else {")
    html.append("    detail.classList.remove('hidden'); thumb.classList.add('hidden');")
    html.append("    btnDetail.classList.add('active'); btnThumb.classList.remove('active');")
    html.append("  }")
    html.append("}")
    html.append("function openDetailAndJump(runId){")
    html.append("  setView('detail');")
    html.append("  const target = document.getElementById('run-details-' + runId);")
    html.append("  if(target){ target.setAttribute('open','true'); target.scrollIntoView({behavior:'smooth', block:'start'}); }")
    html.append("}")
    html.append("function filterThumbs(session){")
    html.append("  const cards = document.querySelectorAll('.thumb-card');")
    html.append("  cards.forEach(c => {")
    html.append("    if(session==='all' || c.dataset.session===session){ c.classList.remove('hidden'); } else { c.classList.add('hidden'); }")
    html.append("  });")
    html.append("  const sections = document.querySelectorAll('.thumb-session');")
    html.append("  sections.forEach(sec => {")
    html.append("    const sess = sec.dataset.session;")
    html.append("    if(session==='all' || sess===session){ sec.classList.remove('hidden'); } else { sec.classList.add('hidden'); }")
    html.append("  });")
    html.append("  document.querySelectorAll('.thumb-filters .pill').forEach(btn => btn.classList.remove('active'));")
    html.append("  const activeBtn = document.querySelector(`.thumb-filters .pill[data-session='${session}']`);")
    html.append("  if(activeBtn){ activeBtn.classList.add('active'); }")
    html.append("}")
    html.append("function toggleSidebar() {")
    html.append("  const sidebar = document.getElementById('sidebar');")
    html.append("  const overlay = document.querySelector('.sidebar-overlay');")
    html.append("  sidebar.classList.toggle('open');")
    html.append("  overlay.classList.toggle('active');")
    html.append("}")
    html.append("")
    html.append("function getStorageKey(id) {")
    html.append("  return 'qa_quality_' + id;")
    html.append("}")
    html.append("")
    html.append("function loadQualityState(id) {")
    html.append("  const key = getStorageKey(id);")
    html.append("  const stored = localStorage.getItem(key);")
    html.append("  return stored === 'good' ? 'good' : (stored === 'bad' ? 'bad' : null);")
    html.append("}")
    html.append("")
    html.append("function saveQualityState(id, quality) {")
    html.append("  const key = getStorageKey(id);")
    html.append("  localStorage.setItem(key, quality);")
    html.append("}")
    html.append("")
    html.append("function setQualityIndicator(element, quality) {")
    html.append("  if (quality === 'good') {")
    html.append("    element.className = 'quality-indicator quality-good';")
    html.append("    element.textContent = '✓ Good';")
    html.append("  } else {")
    html.append("    element.className = 'quality-indicator quality-bad';")
    html.append("    element.textContent = '✗ Bad';")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("function handleRunQuality(runId, sessionId, event) {")
    html.append("  event.stopPropagation();")
    html.append("  const indicator = document.getElementById('run-' + runId);")
    html.append("  const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';")
    html.append("  const newQuality = currentQuality === 'good' ? 'bad' : 'good';")
    html.append("  setQualityIndicator(indicator, newQuality);")
    html.append("  saveQualityState(runId, newQuality);")
    html.append("  updateSessionQuality(sessionId);")
    html.append("  updateReviewProgress();")
    html.append("}")
    html.append("")
    html.append("function handleSessionQuality(sessionId, event) {")
    html.append("  event.stopPropagation();")
    html.append("  const indicator = document.getElementById('session-' + sessionId);")
    html.append("  const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';")
    html.append("  const newQuality = currentQuality === 'good' ? 'bad' : 'good';")
    html.append("  setQualityIndicator(indicator, newQuality);")
    html.append("  saveQualityState(sessionId, newQuality);")
    html.append("  const runIndicators = document.querySelectorAll('.quality-indicator[id^=\"run-\"][data-session-id=\"' + sessionId + '\"]');")
    html.append("  runIndicators.forEach(function(runIndicator) {")
    html.append("    const runId = runIndicator.id.replace('run-', '');")
    html.append("    setQualityIndicator(runIndicator, newQuality);")
    html.append("    saveQualityState(runId, newQuality);")
    html.append("  });")
    html.append("  updateReviewProgress();")
    html.append("}")
    html.append("")
    html.append("function updateSessionQuality(sessionId) {")
    html.append("  const sessionIndicator = document.getElementById('session-' + sessionId);")
    html.append("  if (!sessionIndicator) return;")
    html.append("  const runIndicators = document.querySelectorAll('.quality-indicator[id^=\"run-\"][data-session-id=\"' + sessionId + '\"]');")
    html.append("  if (runIndicators.length === 0) return;")
    html.append("  const allGood = Array.from(runIndicators).every(function(ind) { return ind.classList.contains('quality-good'); });")
    html.append("  const allBad = Array.from(runIndicators).every(function(ind) { return ind.classList.contains('quality-bad'); });")
    html.append("  if (allGood) {")
    html.append("    setQualityIndicator(sessionIndicator, 'good');")
    html.append("    saveQualityState(sessionId, 'good');")
    html.append("  } else if (allBad) {")
    html.append("    setQualityIndicator(sessionIndicator, 'bad');")
    html.append("    saveQualityState(sessionId, 'bad');")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("let konamiCode = [];")
    html.append("const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'KeyB', 'KeyA'];")
    html.append("")
    html.append("function toggleDarkMode() {")
    html.append("  document.body.classList.toggle('dark-mode');")
    html.append("  const isDark = document.body.classList.contains('dark-mode');")
    html.append("  localStorage.setItem('qa_dark_mode', isDark);")
    html.append("  document.querySelector('.dark-mode-toggle').textContent = isDark ? '☀️ Light' : '🌙 Dark';")
    html.append("}")
    html.append("")
    html.append("function filterRuns() {")
    html.append("  const searchTerm = document.getElementById('searchInput').value.toLowerCase();")
    html.append("  const allDetails = document.querySelectorAll('details');")
    html.append("  allDetails.forEach(function(detail) {")
    html.append("    const text = detail.textContent.toLowerCase();")
    html.append("    if (text.includes(searchTerm)) {")
    html.append("      detail.classList.remove('hidden');")
    html.append("    } else {")
    html.append("      detail.classList.add('hidden');")
    html.append("    }")
    html.append("  });")
    html.append("}")
    html.append("")
    html.append("function openExportModal() {")
    html.append("  document.getElementById('exportModal').classList.add('active');")
    html.append("  document.getElementById('exportOverlay').classList.add('active');")
    html.append("}")
    html.append("")
    html.append("function closeExportModal() {")
    html.append("  document.getElementById('exportModal').classList.remove('active');")
    html.append("  document.getElementById('exportOverlay').classList.remove('active');")
    html.append("}")
    html.append("")
    html.append("function downloadFile(content, filename, type) {")
    html.append("  const blob = new Blob([content], { type: type });")
    html.append("  const url = window.URL.createObjectURL(blob);")
    html.append("  const a = document.createElement('a');")
    html.append("  a.href = url;")
    html.append("  a.download = filename;")
    html.append("  document.body.appendChild(a);")
    html.append("  a.click();")
    html.append("  document.body.removeChild(a);")
    html.append("  window.URL.revokeObjectURL(url);")
    html.append("  closeExportModal();")
    html.append("}")
    html.append("")
    html.append("function getQAData() {")
    html.append("  const dataEl = document.getElementById('qa-export-data');")
    html.append("  return dataEl ? JSON.parse(dataEl.textContent) : null;")
    html.append("}")
    html.append("")
    html.append("function exportJSON() {")
    html.append("  const data = getQAData();")
    html.append("  if (!data) { alert('No data available'); return; }")
    html.append("  const json = JSON.stringify(data, null, 2);")
    html.append("  const filename = 'qa_' + data.subject + '_' + new Date().toISOString().split('T')[0] + '.json';")
    html.append("  downloadFile(json, filename, 'application/json');")
    html.append("}")
    html.append("")
    html.append("function exportCSV() {")
    html.append("  const data = getQAData();")
    html.append("  if (!data) { alert('No data available'); return; }")
    html.append("  const rows = [];")
    html.append("  // Collect all metric keys")
    html.append("  const metricKeys = new Set();")
    html.append("  const flagKeys = new Set();")
    html.append("  data.sessions.forEach(function(sess) {")
    html.append("    sess.runs.forEach(function(run) {")
    html.append("      Object.keys(run.metrics).forEach(function(k) { metricKeys.add(k); });")
    html.append("      Object.keys(run.flags).forEach(function(k) { flagKeys.add(k); });")
    html.append("    });")
    html.append("  });")
    html.append("  const metricList = Array.from(metricKeys).sort();")
    html.append("  const flagList = Array.from(flagKeys).sort();")
    html.append("  // Header row")
    html.append("  const header = ['subject', 'session', 'run', 'task', 'echo'].concat(metricList).concat(flagList.map(function(f) { return 'flag_' + f; }));")
    html.append("  rows.push(header);")
    html.append("  // Data rows")
    html.append("  data.sessions.forEach(function(sess) {")
    html.append("    sess.runs.forEach(function(run) {")
    html.append("      const row = [data.subject, sess.session, run.run, run.task || '', run.echo || ''];")
    html.append("      metricList.forEach(function(k) { row.push(run.metrics[k] !== undefined ? run.metrics[k] : ''); });")
    html.append("      flagList.forEach(function(k) { row.push(run.flags[k] !== undefined ? (run.flags[k] ? 1 : 0) : ''); });")
    html.append("      rows.push(row);")
    html.append("    });")
    html.append("  });")
    html.append("  const csv = rows.map(function(row) { return row.map(function(cell) { return '\"' + String(cell).replace(/\"/g, '\"\"') + '\"'; }).join(','); }).join('\\n');")
    html.append("  const filename = 'qa_' + data.subject + '_' + new Date().toISOString().split('T')[0] + '.csv';")
    html.append("  downloadFile(csv, filename, 'text/csv');")
    html.append("}")
    html.append("")
    html.append("function exportFlagged() {")
    html.append("  const data = getQAData();")
    html.append("  if (!data) { alert('No data available'); return; }")
    html.append("  const rows = [];")
    html.append("  rows.push(['subject', 'session', 'run', 'task', 'echo', 'flags', 'flag_count']);")
    html.append("  data.sessions.forEach(function(sess) {")
    html.append("    sess.runs.forEach(function(run) {")
    html.append("      const activeFlags = Object.entries(run.flags).filter(function(e) { return e[1]; }).map(function(e) { return e[0]; });")
    html.append("      if (activeFlags.length > 0) {")
    html.append("        rows.push([data.subject, sess.session, run.run, run.task || '', run.echo || '', activeFlags.join('; '), activeFlags.length]);")
    html.append("      }")
    html.append("    });")
    html.append("  });")
    html.append("  if (rows.length === 1) { alert('No flagged runs found!'); closeExportModal(); return; }")
    html.append("  const csv = rows.map(function(row) { return row.map(function(cell) { return '\"' + String(cell).replace(/\"/g, '\"\"') + '\"'; }).join(','); }).join('\\n');")
    html.append("  const filename = 'qa_' + data.subject + '_flagged_' + new Date().toISOString().split('T')[0] + '.csv';")
    html.append("  downloadFile(csv, filename, 'text/csv');")
    html.append("}")
    html.append("")
    html.append("function closeEasterEgg() {")
    html.append("  document.getElementById('easterEgg').classList.remove('active');")
    html.append("}")
    html.append("")
    html.append("function checkKonamiCode(key) {")
    html.append("  konamiCode.push(key);")
    html.append("  if (konamiCode.length > konamiSequence.length) {")
    html.append("    konamiCode.shift();")
    html.append("  }")
    html.append("  if (konamiCode.length === konamiSequence.length) {")
    html.append("    let match = true;")
    html.append("    for (let i = 0; i < konamiSequence.length; i++) {")
    html.append("      if (konamiCode[i] !== konamiSequence[i]) {")
    html.append("        match = false;")
    html.append("        break;")
    html.append("      }")
    html.append("    }")
    html.append("    if (match) {")
    html.append("      document.getElementById('easterEgg').classList.add('active');")
    html.append("      konamiCode = [];")
    html.append("    }")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("let currentRunIndex = -1;")
    html.append("let allRuns = [];")
    html.append("")
    html.append("function initKeyboardNavigation() {")
    html.append("  // Only select run details, not session details")
    html.append("  allRuns = Array.from(document.querySelectorAll('details[id^=\"run-details-\"]'));")
    html.append("}")
    html.append("")
    html.append("function navigateRuns(direction) {")
    html.append("  if (allRuns.length === 0) initKeyboardNavigation();")
    html.append("  if (allRuns.length === 0) return;")
    html.append("  if (currentRunIndex < 0) currentRunIndex = direction > 0 ? 0 : allRuns.length - 1;")
    html.append("  else currentRunIndex += direction;")
    html.append("  if (currentRunIndex < 0) currentRunIndex = allRuns.length - 1;")
    html.append("  if (currentRunIndex >= allRuns.length) currentRunIndex = 0;")
    html.append("  const runDetail = allRuns[currentRunIndex];")
    html.append("  // Close all other runs first")
    html.append("  allRuns.forEach(function(d) { if (d !== runDetail) d.open = false; });")
    html.append("  // Open parent session first")
    html.append("  const parentSession = runDetail.closest('details[id^=\"session-details-\"]');")
    html.append("  if (parentSession) parentSession.open = true;")
    html.append("  runDetail.open = true;")
    html.append("  runDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });")
    html.append("  // Update nav highlight")
    html.append("  const runId = runDetail.id.replace('run-details-', '');")
    html.append("  updateActiveNavItem(runId);")
    html.append("}")
    html.append("")
    html.append("document.addEventListener('keydown', function(e) {")
    html.append("  if (e.target.tagName === 'INPUT') return;")
    html.append("  if (e.key === 'j' || e.key === 'J') {")
    html.append("    e.preventDefault();")
    html.append("    navigateRuns(1);")
    html.append("  } else if (e.key === 'k' || e.key === 'K') {")
    html.append("    e.preventDefault();")
    html.append("    navigateRuns(-1);")
    html.append("  } else if (e.key === ' ' && e.target.tagName !== 'INPUT') {")
    html.append("    e.preventDefault();")
    html.append("    // Toggle good/bad on current run")
    html.append("    if (currentRunIndex >= 0 && currentRunIndex < allRuns.length) {")
    html.append("      const runDetail = allRuns[currentRunIndex];")
    html.append("      const runId = runDetail.id.replace('run-details-', '');")
    html.append("      const indicator = document.getElementById('run-' + runId);")
    html.append("      if (indicator) {")
    html.append("        const sessionId = indicator.dataset.sessionId;")
    html.append("        const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';")
    html.append("        const newQuality = currentQuality === 'good' ? 'bad' : 'good';")
    html.append("        setQualityIndicator(indicator, newQuality);")
    html.append("        saveQualityState(runId, newQuality);")
    html.append("        if (sessionId) updateSessionQuality(sessionId);")
    html.append("        updateReviewProgress();")
    html.append("      }")
    html.append("    }")
    html.append("  } else if (e.key === '/' && e.target.tagName !== 'INPUT') {")
    html.append("    e.preventDefault();")
    html.append("    document.getElementById('searchInput').focus();")
    html.append("  } else if (e.key === 'f' || e.key === 'F') {")
    html.append("    e.preventDefault();")
    html.append("    nextFlagged();")
    html.append("  } else if (e.key === 'e' || e.key === 'E') {")
    html.append("    e.preventDefault();")
    html.append("    expandAll();")
    html.append("  } else if (e.key === 'c' || e.key === 'C') {")
    html.append("    e.preventDefault();")
    html.append("    collapseAll();")
    html.append("  }")
    html.append("  checkKonamiCode(e.code);")
    html.append("});")
    html.append("")
    # Navigation panel functions
    html.append("function toggleNavPanel() {")
    html.append("  document.getElementById('navPanel').classList.toggle('collapsed');")
    html.append("  document.querySelector('.content-with-nav').classList.toggle('content-with-nav');")
    html.append("}")
    html.append("")
    html.append("function navigateToRun(runId) {")
    html.append("  const detail = document.getElementById('run-details-' + runId);")
    html.append("  if (detail) {")
    html.append("    // Close all other runs first")
    html.append("    document.querySelectorAll('details[id^=\"run-details-\"]').forEach(function(d) {")
    html.append("      if (d !== detail) d.open = false;")
    html.append("    });")
    html.append("    // Open parent session first")
    html.append("    const parent = detail.closest('details[id^=\"session-details-\"]');")
    html.append("    if (parent) parent.open = true;")
    html.append("    detail.open = true;")
    html.append("    detail.scrollIntoView({ behavior: 'smooth', block: 'start' });")
    html.append("    updateActiveNavItem(runId);")
    html.append("    // Sync keyboard navigation index")
    html.append("    if (allRuns.length === 0) initKeyboardNavigation();")
    html.append("    currentRunIndex = allRuns.indexOf(detail);")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("function updateActiveNavItem(runId) {")
    html.append("  document.querySelectorAll('.nav-item').forEach(function(item) {")
    html.append("    item.classList.remove('active');")
    html.append("  });")
    html.append("  const navItem = document.querySelector('.nav-run[data-run=\"' + runId + '\"]');")
    html.append("  if (navItem) {")
    html.append("    navItem.classList.add('active');")
    html.append("    // Scroll nav item into view within the nav panel")
    html.append("    navItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("function filterNav(filter) {")
    html.append("  document.querySelectorAll('.nav-filter-btn').forEach(function(btn) { btn.classList.remove('active'); });")
    html.append("  document.getElementById('filter' + filter.charAt(0).toUpperCase() + filter.slice(1)).classList.add('active');")
    html.append("  const navRuns = document.querySelectorAll('.nav-run');")
    html.append("  navRuns.forEach(function(item) {")
    html.append("    if (filter === 'all') {")
    html.append("      item.style.display = '';")
    html.append("    } else if (filter === 'flagged') {")
    html.append("      item.style.display = item.dataset.flagged === 'true' ? '' : 'none';")
    html.append("    }")
    html.append("  });")
    html.append("}")
    html.append("")
    html.append("function updateReviewProgress() {")
    html.append("  const total = document.querySelectorAll('.nav-run').length;")
    html.append("  let reviewed = 0;")
    html.append("  document.querySelectorAll('.nav-run').forEach(function(item) {")
    html.append("    const runId = item.dataset.run;")
    html.append("    if (loadQualityState(runId)) reviewed++;")
    html.append("  });")
    html.append("  document.getElementById('reviewCount').textContent = reviewed;")
    html.append("  const pct = total > 0 ? (reviewed / total * 100) : 0;")
    html.append("  document.getElementById('progressFill').style.width = pct + '%';")
    html.append("  // Update nav item dots based on quality state")
    html.append("  document.querySelectorAll('.nav-run').forEach(function(item) {")
    html.append("    const runId = item.dataset.run;")
    html.append("    const quality = loadQualityState(runId);")
    html.append("    const dot = item.querySelector('.nav-item-dot');")
    html.append("    if (quality === 'good') {")
    html.append("      dot.classList.remove('flagged', 'bad');")
    html.append("      dot.classList.add('good');")
    html.append("    } else if (quality === 'bad') {")
    html.append("      dot.classList.remove('flagged', 'good');")
    html.append("      dot.classList.add('bad');")
    html.append("    }")
    html.append("  });")
    html.append("}")
    html.append("")
    html.append("// Enhanced keyboard shortcuts")
    html.append("function expandAll() {")
    html.append("  document.querySelectorAll('details').forEach(function(d) { d.open = true; });")
    html.append("}")
    html.append("function collapseAll() {")
    html.append("  document.querySelectorAll('details').forEach(function(d) { d.open = false; });")
    html.append("}")
    html.append("function nextFlagged() {")
    html.append("  const flaggedRuns = document.querySelectorAll('.nav-run[data-flagged=\"true\"]');")
    html.append("  if (flaggedRuns.length === 0) return;")
    html.append("  const activeRun = document.querySelector('.nav-run.active');")
    html.append("  let nextIndex = 0;")
    html.append("  if (activeRun) {")
    html.append("    for (let i = 0; i < flaggedRuns.length; i++) {")
    html.append("      if (flaggedRuns[i] === activeRun) { nextIndex = (i + 1) % flaggedRuns.length; break; }")
    html.append("    }")
    html.append("  }")
    html.append("  navigateToRun(flaggedRuns[nextIndex].dataset.run);")
    html.append("}")
    html.append("")
    html.append("document.addEventListener('DOMContentLoaded', function() {")
    html.append("  const darkMode = localStorage.getItem('qa_dark_mode') === 'true';")
    html.append("  if (darkMode) {")
    html.append("    document.body.classList.add('dark-mode');")
    html.append("    document.querySelector('.dark-mode-toggle').textContent = '☀️ Light';")
    html.append("  }")
    html.append("  const allIndicators = document.querySelectorAll('.quality-indicator[id^=\"run-\"], .quality-indicator[id^=\"session-\"]');")
    html.append("  allIndicators.forEach(function(indicator) {")
    html.append("    const id = indicator.id.replace(/^(run-|session-)/, '');")
    html.append("    const storedQuality = loadQualityState(id);")
    html.append("    if (storedQuality) {")
    html.append("      setQualityIndicator(indicator, storedQuality);")
    html.append("    }")
    html.append("  });")
    html.append("  const sessionIndicators = document.querySelectorAll('.quality-indicator[id^=\"session-\"]');")
    html.append("  sessionIndicators.forEach(function(sessionIndicator) {")
    html.append("    const sessionId = sessionIndicator.id.replace('session-', '');")
    html.append("    updateSessionQuality(sessionId);")
    html.append("  });")
    html.append("  initKeyboardNavigation();")
    html.append("  updateReviewProgress();")
    html.append("  initTooltips();")
    html.append("});")
    html.append("")
    html.append("// Tooltip positioning")
    html.append("function initTooltips() {")
    html.append("  document.querySelectorAll('.metric-name').forEach(function(el) {")
    html.append("    const tooltip = el.querySelector('.tooltip-text');")
    html.append("    if (!tooltip) return;")
    html.append("    el.addEventListener('mouseenter', function(e) {")
    html.append("      const rect = el.getBoundingClientRect();")
    html.append("      const tooltipWidth = 300;")
    html.append("      let left = rect.left;")
    html.append("      let top = rect.bottom + 8;")
    html.append("      // Keep tooltip in viewport")
    html.append("      if (left + tooltipWidth > window.innerWidth - 16) {")
    html.append("        left = window.innerWidth - tooltipWidth - 16;")
    html.append("      }")
    html.append("      if (top + 100 > window.innerHeight) {")
    html.append("        top = rect.top - 8;")
    html.append("        tooltip.style.transform = 'translateY(-100%)';")
    html.append("      } else {")
    html.append("        tooltip.style.transform = 'translateY(0)';")
    html.append("      }")
    html.append("      tooltip.style.left = left + 'px';")
    html.append("      tooltip.style.top = top + 'px';")
    html.append("    });")
    html.append("  });")
    html.append("}")
    html.append("</script>")

    # Embed export data as hidden JSON
    export_data = serialize_subject_for_export(subject, session_consistency)
    json_data = json.dumps(export_data, indent=None, separators=(',', ':'))
    html.append(f"<script type='application/json' id='qa-export-data'>{json_data}</script>")

    # Include JavaScript for interactivity
    html.append("<script>")
    html.extend(get_subject_report_scripts())
    html.append("</script>")

    html.append("</body></html>")

    report_path = output_dir / "subject_report.html"
    report_path.write_text("\n".join(html), encoding="utf-8")
    return report_path


def generate_study_report(
    study: StudyResults,
    output_dir: Path,
    study_aggregate_path: Optional[Path] = None,
) -> Path:
    """Generate main study report."""
    total_runs = sum(
        len(session.runs) for subject in study.subjects for session in subject.sessions
    )

    html = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>fMRI QA Report</title>",
        CSS_STYLE,
        "</head><body>",
        "<div class='search-box'><span>🔍</span><input type='text' id='searchInput' placeholder='Search subjects...' oninput='filterSubjects()'></div>",
        "<button class='dark-mode-toggle' onclick='toggleDarkMode()'>🌙 Dark</button>",
        "<div class='easter-egg' id='easterEgg'>",
        "<button class='easter-egg-close' onclick='closeEasterEgg()'>×</button>",
        "<h2>🧠 You found the secret!</h2>",
        "<p>Congratulations! You've unlocked the Konami code easter egg. Your fMRI data is in good hands.</p>",
        "<p style='font-size: 2rem; margin: 1rem 0;'>🧠 → 🧠 → 🧠</p>",
        "<p><em>Keep up the great QA work!</em></p>",
        "</div>",
        "<div class='keyboard-hint' id='keyboardHint'>",
        "<strong>Keyboard shortcuts:</strong><br>",
        "<kbd>/</kbd> Search",
        "</div>",
        "<header><div class='container'>",
        "<h1>fMRI Quality Assurance Report</h1>",
        f"<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        "</div></header>",
        "<div class='container'>",
    ]

    html.append("<div class='summary-cards'>")
    html.append(
        f"<div class='card'><h3>Subjects</h3><div class='value'>{len(study.subjects)}</div></div>"
    )
    html.append(
        f"<div class='card'><h3>Total Runs</h3><div class='value'>{total_runs}</div></div>"
    )

    if study.overall_metrics:
        if "tsnr_median" in study.overall_metrics:
            html.append(
                f"<div class='card'><h3>Median tSNR</h3><div class='value'>{study.overall_metrics['tsnr_median']:.1f}</div></div>"
            )
        if "fd_median" in study.overall_metrics:
            html.append(
                f"<div class='card'><h3>Median FD</h3><div class='value'>{study.overall_metrics['fd_median']:.3f}</div></div>"
            )

    html.append("</div>")

    # Analysis information and threshold controls
    if study.analysis_metadata:
        html.append(render_analysis_info_section(study.analysis_metadata))

    if study_aggregate_path and study_aggregate_path.exists():
        html.append("<h2>Study aggregate maps</h2>")
        img_rel = relative_asset_path(study_aggregate_path, output_dir)
        html.append(f"<figure><img src='{img_rel}' alt='Aggregate maps'></figure>")

    if study.group_plots:
        html.append("<h2>Group Comparisons</h2>")
        html.append("<div class='stats-dashboard'>")
        
        for key, path in study.group_plots.items():
            if path and path.exists():
                img_rel = relative_asset_path(path, output_dir)
                html.append(f"<div class='stat-card' style='text-align: center;'>")
                html.append(f"<h4>{format_metric_name(key)} Distribution</h4>")
                html.append(f"<img src='{img_rel}' alt='{key} comparison' style='max-width: 100%; height: auto; border-radius: 8px;'>")
                html.append("</div>")
        
        html.append("</div>")

    # Interactive comparison dashboard (CIR-200)
    if total_runs >= 3:
        interactive_data = serialize_study_for_interactive(study)
        html.append("<h2>Interactive Comparison</h2>")
        html.append("<p class='section-intro'>Explore metrics across all runs. Click on data points to see details.</p>")
        html.append("<div class='interactive-dashboard'>")
        html.append("<div class='dashboard-controls'>")
        html.append("<div class='control-group'>")
        html.append("<label for='xMetricSelect'>X-Axis Metric</label>")
        html.append("<select id='xMetricSelect' onchange='updateChart()'>")
        for key, label, _ in COMPARISON_METRICS:
            selected = "selected" if key == "tsnr_median" else ""
            html.append(f"<option value='{key}' {selected}>{label}</option>")
        html.append("</select></div>")
        html.append("<div class='control-group'>")
        html.append("<label for='yMetricSelect'>Y-Axis Metric</label>")
        html.append("<select id='yMetricSelect' onchange='updateChart()'>")
        for key, label, _ in COMPARISON_METRICS:
            selected = "selected" if key == "fd_median" else ""
            html.append(f"<option value='{key}' {selected}>{label}</option>")
        html.append("</select></div>")
        html.append("<div class='control-group'>")
        html.append("<label for='colorBySelect'>Color By</label>")
        html.append("<select id='colorBySelect' onchange='updateChart()'>")
        html.append("<option value='subject' selected>Subject</option>")
        html.append("<option value='session'>Session</option>")
        html.append("<option value='flagged'>Flagged Status</option>")
        html.append("</select></div>")
        html.append("<div class='control-group'>")
        html.append("<label for='subjectFilter'>Filter Subject</label>")
        html.append("<select id='subjectFilter' onchange='updateChart()'>")
        html.append("<option value='all'>All Subjects</option>")
        for subj in interactive_data['subjects']:
            html.append(f"<option value='{subj}'>{subj}</option>")
        html.append("</select></div>")
        html.append("</div>")  # controls
        html.append("<div class='chart-container'><canvas id='comparisonChart'></canvas></div>")
        html.append("<div id='runDetailsPanel' class='run-details-panel'>")
        html.append("<h4 id='runDetailsTitle'>Click a point to see details</h4>")
        html.append("<div id='runDetailsGrid' class='run-details-grid'></div>")
        html.append("</div>")
        html.append("</div>")  # dashboard
        # Embed data for JavaScript
        html.append(f"<script>const qaData = {json.dumps(interactive_data)};</script>")
        html.append("<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>")
        html.append("""<script>
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
</script>""")

    # Outlier section with detailed explanations
    outlier_report = getattr(study, 'outlier_report', {})
    has_any_outliers = (
        study.overall_outliers or
        outlier_report.get('extreme_motion', []) or
        outlier_report.get('low_tsnr', [])
    )

    if has_any_outliers:
        html.append("<h2>Outliers Detected</h2>")
        html.append("<p class='section-intro'>Runs flagged for quality concerns based on multiple detection methods.</p>")

        # Add methodology explanation
        tsnr_thresh = outlier_report.get('tsnr_threshold', 30.0)
        html.append("<details class='methodology-info' style='margin-bottom: 1.5rem; background: var(--paper-warm); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);'>")
        html.append("<summary style='cursor: pointer; font-weight: 600;'>How are outliers detected?</summary>")
        html.append("<div style='margin-top: 0.75rem; font-size: 0.9rem; line-height: 1.6;'>")
        html.append("<p><strong>Unusual runs</strong> are flagged when their combination of metrics is statistically unusual compared to other runs. This catches runs that might look okay on individual metrics but have an unusual pattern overall.</p>")
        html.append("<p style='margin-top: 0.5rem;'><strong>Extreme motion</strong> flags runs with too much head movement: median framewise displacement > 0.5mm, or more than 20% of volumes exceeding 0.3mm movement.</p>")
        html.append(f"<p style='margin-top: 0.5rem;'><strong>Low tSNR</strong> flags runs where signal quality is poor: median tSNR below {tsnr_thresh:.0f}. For reference, tSNR below 20 is poor, 20-40 is marginal, above 40 is good.</p>")
        html.append("<p style='margin-top: 0.5rem;'><strong>Single-metric outliers</strong> flag runs that are extreme on any individual metric (more than 3 standard deviations from typical).</p>")
        html.append("</div>")
        html.append("</details>")

        # Build explanation for each outlier
        outlier_explanations = {}

        # Multivariate outliers (unusual pattern)
        for run_id in outlier_report.get('multivariate_outliers', []):
            if run_id not in outlier_explanations:
                outlier_explanations[run_id] = []
            distance = outlier_report.get('mahalanobis_distances', {}).get(run_id, 0)
            outlier_explanations[run_id].append(f"Unusual metric pattern (statistical distance: {distance:.1f})")

        # Extreme motion
        for run_id in outlier_report.get('extreme_motion', []):
            if run_id not in outlier_explanations:
                outlier_explanations[run_id] = []
            outlier_explanations[run_id].append("Excessive head motion")

        # Low tSNR
        for run_id in outlier_report.get('low_tsnr', []):
            if run_id not in outlier_explanations:
                outlier_explanations[run_id] = []
            outlier_explanations[run_id].append(f"Low signal quality (tSNR < {tsnr_thresh:.0f})")

        # Per-metric univariate outliers
        univariate = outlier_report.get('univariate_outliers', {})
        for metric, run_ids in univariate.items():
            metric_name = format_metric_name(metric)
            for run_id in run_ids:
                if run_id not in outlier_explanations:
                    outlier_explanations[run_id] = []
                outlier_explanations[run_id].append(f"Univariate outlier: {metric_name}")

        # Summary stats
        summary = outlier_report.get('summary', {})
        if summary:
            html.append("<div class='outlier-summary' style='display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;'>")
            html.append(f"<div class='stat-card'><span class='stat-value'>{summary.get('multivariate_outliers', 0)}</span><span class='stat-label'>Multivariate</span></div>")
            html.append(f"<div class='stat-card'><span class='stat-value'>{summary.get('extreme_motion_runs', 0)}</span><span class='stat-label'>High Motion</span></div>")
            html.append(f"<div class='stat-card'><span class='stat-value'>{summary.get('low_tsnr_runs', 0)}</span><span class='stat-label'>Low tSNR</span></div>")
            html.append(f"<div class='stat-card'><span class='stat-value'>{summary.get('percentage_flagged', 0):.1f}%</span><span class='stat-label'>Total Flagged</span></div>")
            html.append("</div>")

        # Detailed table of outliers with reasons (collapsed by default)
        if outlier_explanations:
            n_outliers = len(outlier_explanations)
            html.append(f"<details><summary>View all {n_outliers} flagged runs</summary>")
            html.append("<table class='metrics-table'>")
            html.append("<thead><tr><th>Run</th><th>Reasons Flagged</th></tr></thead>")
            html.append("<tbody>")
            for run_id, reasons in sorted(outlier_explanations.items()):
                reasons_html = "<br>".join(f"• {r}" for r in reasons)
                html.append(f"<tr><td><code>{run_id}</code></td><td style='text-align: left;'>{reasons_html}</td></tr>")
            html.append("</tbody></table>")
            html.append("</details>")

        # Warnings from outlier detection
        if outlier_report.get('warnings'):
            html.append("<details style='margin-top: 1rem;'><summary>Detection Warnings</summary><ul>")
            for warning in outlier_report['warnings']:
                html.append(f"<li>{warning}</li>")
            html.append("</ul></details>")

    # Exclusion Recommendations section (CIR-212)
    exclusion_report = getattr(study, 'exclusion_report', None)
    if exclusion_report is not None:
        html.append("<h2>Exclusion Recommendations</h2>")
        html.append("<p class='section-intro'>Automatic exclusion recommendations based on configurable quality criteria.</p>")

        summary = exclusion_report.summary
        html.append("<div class='stats-dashboard' style='margin-bottom: 1.5rem;'>")
        html.append(f"<div class='stat-card'><span class='stat-value'>{summary['excluded_runs']}</span><span class='stat-label'>Recommended Exclusions</span></div>")
        html.append(f"<div class='stat-card'><span class='stat-value'>{summary['retained_runs']}</span><span class='stat-label'>Retained Runs</span></div>")
        html.append(f"<div class='stat-card'><span class='stat-value'>{summary['exclusion_rate_percent']:.1f}%</span><span class='stat-label'>Exclusion Rate</span></div>")
        html.append(f"<div class='stat-card'><span class='stat-value'>{summary['volume_data_loss_percent']:.1f}%</span><span class='stat-label'>Volume Data Loss</span></div>")
        html.append("</div>")

        # Criteria info
        html.append("<details style='margin-bottom: 1rem;'><summary>Exclusion Criteria (Stringency: {0})</summary>".format(exclusion_report.stringency.capitalize()))
        html.append("<ul style='margin-top: 0.5rem;'>")
        criteria = exclusion_report.criteria
        if 'fd_median_max' in criteria:
            html.append(f"<li>Median FD threshold: {criteria['fd_median_max']}mm</li>")
        if 'fd_percent_max' in criteria:
            html.append(f"<li>Max high-motion volumes: {criteria['fd_percent_max']}%</li>")
        if 'tsnr_min' in criteria:
            html.append(f"<li>Minimum tSNR: {criteria['tsnr_min']}</li>")
        if 'tsnr_percentile_min' in criteria:
            html.append(f"<li>Minimum tSNR percentile: {criteria['tsnr_percentile_min']}%</li>")
        if 'dvars_percent_max' in criteria:
            html.append(f"<li>Max high-DVARS volumes: {criteria['dvars_percent_max']}%</li>")
        if 'mahalanobis_max' in criteria:
            html.append(f"<li>Mahalanobis distance threshold: {criteria['mahalanobis_max']}</li>")
        html.append("</ul></details>")

        # List excluded runs with reasons (collapsed by default)
        excluded = [e for e in exclusion_report.run_exclusions if e.excluded]
        if excluded:
            n_excluded = len(excluded)
            html.append(f"<details><summary>View all {n_excluded} runs recommended for exclusion</summary>")
            html.append("<table class='metrics-table'>")
            html.append("<thead><tr><th>Run</th><th>Reasons</th></tr></thead>")
            html.append("<tbody>")
            for exc in excluded:
                reasons_html = "<br>".join(f"• {r.description}" for r in exc.reasons)
                html.append(f"<tr><td><code>{exc.run_id}</code></td><td style='text-align: left;'>{reasons_html}</td></tr>")
            html.append("</tbody></table>")
            html.append("</details>")

        # Volume scrubbing summary
        scrubbing = exclusion_report.volume_scrubbing
        high_scrub = [s for s in scrubbing if s.data_loss_percent > 10]
        if high_scrub:
            html.append("<details style='margin-top: 1rem;'><summary>Runs with >10% Volume Scrubbing</summary>")
            html.append("<table class='metrics-table' style='margin-top: 0.5rem;'>")
            html.append("<thead><tr><th>Run</th><th>Flagged Volumes</th><th>Data Loss</th></tr></thead>")
            html.append("<tbody>")
            for s in sorted(high_scrub, key=lambda x: -x.data_loss_percent):
                html.append(f"<tr><td><code>{s.run_id}</code></td><td>{len(s.flagged_volumes)}/{s.n_volumes}</td><td>{s.data_loss_percent:.1f}%</td></tr>")
            html.append("</tbody></table>")
            html.append("</details>")

        # Reason breakdown
        reason_counts = summary.get('exclusion_reason_counts', {})
        if reason_counts:
            html.append("<details style='margin-top: 1rem;'><summary>Exclusion Reason Breakdown</summary>")
            html.append("<ul style='margin-top: 0.5rem;'>")
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
            for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
                label = reason_labels.get(reason, reason)
                html.append(f"<li>{label}: {count} run(s)</li>")
            html.append("</ul></details>")

    html.append("<h2>Subjects</h2>")
    html.append("<div class='subject-grid'>")

    for subject in study.subjects:
        n_runs = sum(len(session.runs) for session in subject.sessions)
        subject_id = subject.get_identifier()
        
        html.append("<div class='subject-card'>")
        
        # Subject aggregate image
        if subject.aggregate_figure_path and subject.aggregate_figure_path.exists():
            img_rel = relative_asset_path(subject.aggregate_figure_path, output_dir)
            html.append(f"<img src='{img_rel}' alt='Aggregate maps for {subject_id}'>")
        
        html.append("<div class='subject-card-content'>")
        html.append(f"<h3>{subject_id}</h3>")
        html.append(f"<p><strong>{len(subject.sessions)}</strong> session(s)</p>")
        html.append(f"<p><strong>{n_runs}</strong> total run(s)</p>")
        
        # Key metrics summary
        subject_metrics = compute_subject_metrics(subject.sessions)
        if subject_metrics:
            key_metrics_list = []
            for key in ["tsnr_median", "fd_median"]:
                if key in subject_metrics:
                    key_metrics_list.append(key)
                elif f"{key}_median" in subject_metrics:
                    key_metrics_list.append(f"{key}_median")
            
            if key_metrics_list:
                html.append("<p style='margin-top: 1rem; font-size: 0.9rem;'>")
                metric_parts = []
                for key in key_metrics_list[:2]:
                    if key in subject_metrics:
                        val = subject_metrics[key]
                        name = format_metric_name(key).split()[0]
                        metric_parts.append(f"{name}: {format_metric_value(val)}")
                if metric_parts:
                    html.append(" | ".join(metric_parts))
                html.append("</p>")
        
        html.append(
            f"<a href='sub-{subject.subject}/subject_report.html'>View subject report →</a>"
        )
        html.append("</div>")
        html.append("</div>")

    html.append("</div>")
    html.append("<script>")
    html.append("let konamiCode = [];")
    html.append("const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'KeyB', 'KeyA'];")
    html.append("")
    html.append("function toggleDarkMode() {")
    html.append("  document.body.classList.toggle('dark-mode');")
    html.append("  const isDark = document.body.classList.contains('dark-mode');")
    html.append("  localStorage.setItem('qa_dark_mode', isDark);")
    html.append("  document.querySelector('.dark-mode-toggle').textContent = isDark ? '☀️ Light' : '🌙 Dark';")
    html.append("}")
    html.append("")
    html.append("function filterSubjects() {")
    html.append("  const searchTerm = document.getElementById('searchInput').value.toLowerCase();")
    html.append("  const allCards = document.querySelectorAll('.subject-card');")
    html.append("  allCards.forEach(function(card) {")
    html.append("    const text = card.textContent.toLowerCase();")
    html.append("    if (text.includes(searchTerm)) {")
    html.append("      card.classList.remove('hidden');")
    html.append("    } else {")
    html.append("      card.classList.add('hidden');")
    html.append("    }")
    html.append("  });")
    html.append("}")
    html.append("")
    html.append("function closeEasterEgg() {")
    html.append("  document.getElementById('easterEgg').classList.remove('active');")
    html.append("}")
    html.append("")
    html.append("function checkKonamiCode(key) {")
    html.append("  konamiCode.push(key);")
    html.append("  if (konamiCode.length > konamiSequence.length) {")
    html.append("    konamiCode.shift();")
    html.append("  }")
    html.append("  if (konamiCode.length === konamiSequence.length) {")
    html.append("    let match = true;")
    html.append("    for (let i = 0; i < konamiSequence.length; i++) {")
    html.append("      if (konamiCode[i] !== konamiSequence[i]) {")
    html.append("        match = false;")
    html.append("        break;")
    html.append("      }")
    html.append("    }")
    html.append("    if (match) {")
    html.append("      document.getElementById('easterEgg').classList.add('active');")
    html.append("      konamiCode = [];")
    html.append("    }")
    html.append("  }")
    html.append("}")
    html.append("")
    html.append("document.addEventListener('keydown', function(e) {")
    html.append("  if (e.target.tagName === 'INPUT') return;")
    html.append("  if (e.key === '/' && e.target.tagName !== 'INPUT') {")
    html.append("    e.preventDefault();")
    html.append("    document.getElementById('searchInput').focus();")
    html.append("  }")
    html.append("  checkKonamiCode(e.code);")
    html.append("});")
    html.append("")
    html.append("document.addEventListener('DOMContentLoaded', function() {")
    html.append("  const darkMode = localStorage.getItem('qa_dark_mode') === 'true';")
    html.append("  if (darkMode) {")
    html.append("    document.body.classList.add('dark-mode');")
    html.append("    document.querySelector('.dark-mode-toggle').textContent = '☀️ Light';")
    html.append("  }")
    html.append("  setView('thumb');")
    html.append("  initTooltips();")
    html.append("});")
    html.append("")
    html.append("// Tooltip positioning")
    html.append("function initTooltips() {")
    html.append("  document.querySelectorAll('.metric-name').forEach(function(el) {")
    html.append("    const tooltip = el.querySelector('.tooltip-text');")
    html.append("    if (!tooltip) return;")
    html.append("    el.addEventListener('mouseenter', function(e) {")
    html.append("      const rect = el.getBoundingClientRect();")
    html.append("      const tooltipWidth = 300;")
    html.append("      let left = rect.left;")
    html.append("      let top = rect.bottom + 8;")
    html.append("      if (left + tooltipWidth > window.innerWidth - 16) {")
    html.append("        left = window.innerWidth - tooltipWidth - 16;")
    html.append("      }")
    html.append("      if (top + 100 > window.innerHeight) {")
    html.append("        top = rect.top - 8;")
    html.append("        tooltip.style.transform = 'translateY(-100%)';")
    html.append("      } else {")
    html.append("        tooltip.style.transform = 'translateY(0)';")
    html.append("      }")
    html.append("      tooltip.style.left = left + 'px';")
    html.append("      tooltip.style.top = top + 'px';")
    html.append("    });")
    html.append("  });")
    html.append("}")
    html.append("</script>")

    # Include JavaScript for interactivity
    html.append("<script>")
    html.extend(get_study_report_scripts())
    html.append("</script>")

    html.append("</div></body></html>")

    report_path = output_dir / "index.html"
    report_path.write_text("\n".join(html), encoding="utf-8")
    return report_path
