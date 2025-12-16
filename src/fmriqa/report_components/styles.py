"""CSS styles for QA reports.

This module contains the CSS stylesheet as a string constant.
Keeping it in a separate file makes styling changes easier to manage.
"""

CSS_STYLE = """
<style>
    /* Minimal research-focused QA report styling */
    :root {
        --ink: #222;
        --ink-light: #555;
        --paper: #fff;
        --paper-alt: #f8f8f8;
        --border: #ddd;
        --accent: #0066cc;
        --success: #228b22;
        --warning: #cc7000;
        --danger: #cc0000;
        --muted: #666;
        --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        --font-mono: 'SF Mono', Consolas, monospace;
    }

    * { box-sizing: border-box; }
    body { font-family: var(--font-sans); margin: 0; background: var(--paper); color: var(--ink); line-height: 1.5; font-size: 14px; }
    .container { max-width: 1600px; margin: 0 auto; padding: 2rem; }

    /* Skip link - only visible on focus for accessibility */
    .skip-link { position: absolute; top: -40px; left: 0; background: var(--ink); color: var(--paper); padding: 8px; z-index: 10000; }
    .skip-link:focus { top: 0; }

    /* Simple header */
    header { background: var(--ink); color: var(--paper); padding: 1.5rem 0; }
    header .container { padding: 1rem 2rem; }
    h1 { margin: 0 0 0.5rem 0; font-size: 1.75rem; font-weight: 600; }
    header p { margin: 0; opacity: 0.8; font-size: 0.9rem; }

    h2 { font-size: 1.25rem; font-weight: 600; margin: 2rem 0 1rem 0; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }
    h3 { font-size: 1rem; font-weight: 600; margin: 1.5rem 0 0.75rem 0; }

    /* Summary cards */
    .summary-cards { display: flex; flex-wrap: wrap; gap: 1rem; margin: 1.5rem 0; }
    .card { background: var(--paper-alt); padding: 1rem; border: 1px solid var(--border); flex: 1; min-width: 150px; }
    .card h3 { margin: 0 0 0.25rem 0; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; font-weight: 500; }
    .card .value { font-size: 1.75rem; font-weight: 600; font-family: var(--font-mono); }

    /* View toggle */
    .view-toggle { display: inline-flex; gap: 0.5rem; margin: 0.5rem 0 1rem 0; }
    .view-btn { padding: 0.5rem 0.9rem; border: 1px solid var(--border); background: var(--paper); cursor: pointer; font-size: 0.9rem; border-radius: 999px; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
    .view-btn:hover { border-color: var(--accent); color: var(--accent); }
    .view-btn.active { background: var(--accent); color: var(--paper); border-color: var(--accent); box-shadow: 0 2px 6px rgba(0,0,0,0.12); }

    /* Subject grid */
    .subject-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
    .subject-card { background: var(--paper); border: 1px solid var(--border); overflow: hidden; }
    .subject-card img { width: 100%; height: auto; display: block; border-bottom: 1px solid var(--border); }
    .subject-card-content { padding: 1rem; }
    .subject-card h3 { margin: 0 0 0.5rem 0; font-size: 1rem; }
    .subject-card p { margin: 0.25rem 0; color: var(--muted); font-size: 0.85rem; }
    .subject-card a { display: inline-block; margin-top: 0.75rem; padding: 0.5rem 1rem; background: var(--ink); color: var(--paper); text-decoration: none; font-size: 0.85rem; }
    .subject-card a:hover { background: var(--accent); }

    /* Tables */
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.85rem; }
    th, td { padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
    th { background: var(--paper-alt); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }
    td { font-family: var(--font-mono); font-size: 0.8rem; }
    tr:hover { background: var(--paper-alt); }

    /* Tooltips */
    .metric-name { cursor: help; border-bottom: 1px dotted var(--muted); position: relative; }
    .metric-name .tooltip-text { visibility: hidden; opacity: 0; position: fixed; background: var(--ink); color: var(--paper); padding: 0.5rem 0.75rem; font-size: 0.8rem; font-family: var(--font-sans); width: 280px; z-index: 10000; line-height: 1.4; transition: opacity 0.15s; }
    .metric-name:hover .tooltip-text { visibility: visible; opacity: 1; }

    /* Status flags */
    .flag { display: inline-block; padding: 0.2rem 0.5rem; font-size: 0.7rem; font-family: var(--font-mono); text-transform: uppercase; }
    .flag-success { background: #e8f5e9; color: var(--success); }
    .flag-warning { background: #fff3e0; color: var(--warning); }
    .flag-danger { background: #ffebee; color: var(--danger); }
    .flag-info { background: var(--paper-alt); color: var(--muted); }

    /* Figures */
    figure { margin: 1.5rem 0; text-align: center; }
    figure img { max-width: 100%; border: 1px solid var(--border); }
    figcaption { margin-top: 0.5rem; color: var(--muted); font-size: 0.85rem; }

    /* Links */
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* Breadcrumb */
    .breadcrumb { padding: 0.5rem 0; margin-bottom: 1rem; font-size: 0.85rem; color: var(--muted); }
    .breadcrumb a { color: var(--accent); }

    /* Collapsible details */
    details { margin: 1rem 0; border: 1px solid var(--border); }
    details summary { cursor: pointer; padding: 0.75rem 1rem; background: var(--paper-alt); font-weight: 500; list-style: none; display: flex; align-items: center; }
    details summary::-webkit-details-marker { display: none; }
    details summary::before { content: '▸'; margin-right: 0.5rem; color: var(--muted); }
    details[open] summary::before { content: '▾'; }
    details[open] summary { border-bottom: 1px solid var(--border); }
    details > div, details > table, details > ul { padding: 1rem; margin: 0; }
    details > table { padding: 0; }

    .session-meta { font-size: 0.8rem; color: var(--muted); font-family: var(--font-mono); margin-left: auto; }

    /* Warnings */
    .warnings { background: #fff3e0; color: var(--warning); padding: 0.75rem 1rem; margin: 1rem 0; border-left: 3px solid var(--warning); font-size: 0.85rem; }
    .warnings strong { display: block; margin-bottom: 0.25rem; }
    .warnings ul { margin: 0.25rem 0 0 0; padding-left: 1.25rem; }

    /* Metrics summary */
    .metrics-summary { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; }
    .metric-item { background: var(--paper-alt); padding: 0.75rem 1rem; border-left: 3px solid var(--accent); min-width: 140px; }
    .metric-item-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-item-value { font-size: 1.25rem; font-weight: 600; font-family: var(--font-mono); }

    /* Flag list */
    .flag-list { background: #fff3e0; padding: 0.75rem 1rem; margin: 1rem 0; border-left: 3px solid var(--warning); font-size: 0.85rem; }
    .flag-list strong { display: block; margin-bottom: 0.25rem; }
    .flag-list ul { margin: 0; padding-left: 1.25rem; }

    /* Stats dashboard */
    .stats-dashboard { display: flex; flex-wrap: wrap; gap: 1rem; margin: 1.5rem 0; }
    .stat-card { background: var(--paper-alt); padding: 1rem; border: 1px solid var(--border); flex: 1; min-width: 200px; }
    .stat-card h4 { margin: 0 0 0.5rem 0; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }
    .stat-value { font-size: 1.5rem; font-weight: 600; font-family: var(--font-mono); }
    .stat-label { font-size: 0.75rem; color: var(--muted); }

    /* Quality indicators */
    .quality-indicator { display: inline-block; padding: 0.2rem 0.5rem; font-size: 0.7rem; font-family: var(--font-mono); margin-left: 0.5rem; cursor: pointer; }
    .quality-indicator.quality-good { background: #e8f5e9; color: var(--success); }
    .quality-indicator.quality-bad { background: #ffebee; color: var(--danger); }

    /* Fixed buttons */
    .dark-mode-toggle, .sidebar-toggle, .export-btn { position: fixed; top: 1rem; z-index: 1000; padding: 0.5rem 0.75rem; border: 1px solid var(--border); background: var(--paper); cursor: pointer; font-size: 0.8rem; }
    .dark-mode-toggle { right: 7rem; }
    .sidebar-toggle { right: 1rem; }
    .export-btn { right: 12rem; background: var(--success); color: white; border: none; }
    .search-box { position: fixed; top: 1rem; left: 1rem; z-index: 1000; }
    .search-box input { padding: 0.5rem; border: 1px solid var(--border); font-size: 0.85rem; width: 180px; }

    /* Sidebar */
    .sidebar { position: fixed; top: 0; right: -350px; width: 320px; height: 100vh; background: var(--paper); border-left: 1px solid var(--border); z-index: 999; padding: 1.5rem; overflow-y: auto; transition: right 0.2s; }
    .sidebar.open { right: 0; }
    .sidebar-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.3); z-index: 998; display: none; }
    .sidebar-overlay.active { display: block; }
    .sidebar-close { position: absolute; top: 0.75rem; right: 0.75rem; background: none; border: none; font-size: 1.25rem; cursor: pointer; }
    .sidebar h3 { margin-top: 0; }
    .sidebar h4 { margin: 1.5rem 0 0.5rem 0; font-size: 0.85rem; color: var(--accent); }
    .sidebar p, .sidebar li { font-size: 0.85rem; color: var(--muted); }

    /* Nav panel - only show on wide screens */
    .nav-panel { position: fixed; top: 4rem; left: 1rem; width: 200px; max-height: calc(100vh - 6rem); background: var(--paper); border: 1px solid var(--border); z-index: 999; overflow: hidden; display: none; flex-direction: column; }
    .nav-panel-header { padding: 0.75rem; border-bottom: 1px solid var(--border); background: var(--paper-alt); }
    .nav-panel-header h4 { margin: 0; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }
    .nav-panel-body { overflow-y: auto; padding: 0.5rem; }
    .nav-item { display: block; padding: 0.4rem 0.5rem; font-size: 0.8rem; color: var(--ink-light); cursor: pointer; border-left: 2px solid transparent; }
    .nav-item:hover { background: var(--paper-alt); }
    .nav-item.active { background: var(--paper-alt); border-left-color: var(--accent); font-weight: 600; }
    .nav-item-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; margin-right: 0.5rem; background: var(--border); }
    .nav-item-dot.flagged { background: var(--warning); }
    .nav-item-dot.good { background: var(--success); }
    .nav-item-dot.bad { background: var(--danger); }
    .nav-progress { font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem; }
    .nav-progress-bar { height: 3px; background: var(--border); margin-top: 0.25rem; }
    .nav-progress-fill { height: 100%; background: var(--accent); }
    .nav-filters { display: flex; gap: 0.25rem; margin-top: 0.5rem; }
    .nav-filter-btn { flex: 1; padding: 0.25rem; font-size: 0.65rem; border: 1px solid var(--border); background: var(--paper); cursor: pointer; }
    .nav-filter-btn:hover, .nav-filter-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
    .nav-toggle-btn { display: none; }
    .content-with-nav { margin-left: 0; }
    @media (min-width: 1200px) {
        .nav-panel { display: flex; }
        .content-with-nav { margin-left: 220px; }
    }

    /* Interactive dashboard */
    .interactive-dashboard { border: 1px solid var(--border); padding: 1rem; margin: 1.5rem 0; }
    .interactive-dashboard h3 { margin: 0 0 1rem 0; }
    .dashboard-controls { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
    .control-group label { display: block; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; margin-bottom: 0.25rem; }
    .dashboard-controls select { padding: 0.4rem; border: 1px solid var(--border); font-size: 0.85rem; }
    .chart-container { height: 300px; }
    .run-details-panel { margin-top: 1rem; padding: 0.75rem; background: var(--paper-alt); display: none; }
    .run-details-panel.active { display: block; }
    .run-details-grid { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .run-detail-item { display: flex; justify-content: space-between; padding: 0.4rem 0.5rem; background: var(--paper); font-size: 0.8rem; min-width: 150px; }
    .run-detail-item .label { color: var(--muted); }
    .run-detail-item .value { font-family: var(--font-mono); }

    /* Modals */
    .easter-egg, .export-modal { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: var(--paper); padding: 2rem; border: 1px solid var(--border); z-index: 10000; max-width: 400px; display: none; }
    .easter-egg.active, .export-modal.active { display: block; }
    .easter-egg-close, .export-modal-close { position: absolute; top: 0.5rem; right: 0.5rem; background: none; border: none; font-size: 1.25rem; cursor: pointer; }
    .export-modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; display: none; }
    .export-modal-overlay.active { display: block; }
    .export-option { display: flex; padding: 0.75rem; margin: 0.5rem 0; border: 1px solid var(--border); cursor: pointer; }
    .export-option:hover { border-color: var(--accent); background: var(--paper-alt); }
    .export-option-icon { font-size: 1.25rem; margin-right: 0.75rem; }
    .export-option-content h4 { margin: 0; font-size: 0.9rem; }
    .export-option-content p { margin: 0.25rem 0 0 0; font-size: 0.8rem; color: var(--muted); }

    .keyboard-hint { position: fixed; bottom: 1rem; right: 1rem; background: var(--paper); padding: 0.5rem 0.75rem; border: 1px solid var(--border); font-size: 0.75rem; color: var(--muted); z-index: 1000; }
    .keyboard-hint kbd { background: var(--paper-alt); padding: 0.1rem 0.3rem; border: 1px solid var(--border); font-family: var(--font-mono); font-size: 0.7rem; }

    .hidden { display: none !important; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }

    /* Thumbnails - Enhanced Design */
    .thumb-guide {
        margin-top: -0.5rem;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* View density controls */
    .thumb-view-controls {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 1rem 0;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .thumb-density-toggle {
        display: flex;
        gap: 0.25rem;
        background: var(--paper-alt);
        padding: 0.25rem;
        border-radius: 6px;
        border: 1px solid var(--border);
    }

    .density-btn {
        padding: 0.4rem 0.8rem;
        border: none;
        background: transparent;
        cursor: pointer;
        font-size: 0.85rem;
        border-radius: 4px;
        transition: all 0.2s;
        font-weight: 500;
    }

    .density-btn:hover {
        background: var(--paper);
    }

    .density-btn.active {
        background: var(--paper);
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    /* Thumbnail grid with dynamic sizing */
    .thumb-grid {
        display: grid;
        gap: 1.25rem;
        margin: 1rem 0 1.5rem 0;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    }

    .thumb-grid.density-compact {
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 0.75rem;
    }

    .thumb-grid.density-spacious {
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1.5rem;
    }

    /* Enhanced thumbnail cards */
    .thumb-card {
        display: flex;
        flex-direction: column;
        border: 1px solid var(--border);
        background: var(--paper);
        text-decoration: none;
        color: inherit;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }

    .thumb-card:hover {
        border-color: var(--accent);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }

    .thumb-card:active {
        transform: translateY(0);
    }

    /* Image container with aspect ratio */
    .thumb-image {
        background: #e8e8e8;
        position: relative;
        overflow: hidden;
        aspect-ratio: 4/3;
    }

    .thumb-image img {
        width: 100%;
        height: 100%;
        object-fit: contain;
        display: block;
        transition: transform 0.3s;
    }

    .thumb-card:hover .thumb-image img {
        transform: scale(1.05);
    }

    /* Quality indicator overlay */
    .thumb-quality-indicator {
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    .thumb-quality-indicator.good { background: var(--success); }
    .thumb-quality-indicator.warn { background: var(--warning); }
    .thumb-quality-indicator.bad { background: var(--danger); }

    /* Card content */
    .thumb-content {
        padding: 0.9rem;
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        flex-grow: 1;
    }

    .thumb-meta {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 0.5rem;
    }

    .thumb-title {
        font-weight: 600;
        font-size: 1rem;
        line-height: 1.3;
        flex: 1;
    }

    /* Enhanced badges */
    .badge {
        font-family: var(--font-mono);
        font-size: 0.7rem;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        border: none;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        white-space: nowrap;
    }

    .badge-good {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        color: #2e7d32;
    }

    .badge-warn {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        color: #e65100;
    }

    .badge-bad {
        background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
        color: #c62828;
    }

    .badge-muted {
        background: var(--paper-alt);
        color: var(--muted);
        font-weight: 500;
    }

    .thumb-badges {
        display: flex;
        gap: 0.4rem;
        flex-wrap: wrap;
    }

    .thumb-subtitle {
        font-size: 0.8rem;
        color: var(--muted);
        margin-top: auto;
        padding-top: 0.5rem;
        border-top: 1px solid var(--border);
    }

    .thumb-link {
        display: inline-block;
        margin: 0.5rem 0 0 0;
        font-weight: 600;
        color: var(--accent);
    }

    .thumb-link:hover {
        text-decoration: underline;
    }

    .thumb-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .pill {
        padding: 0.4rem 0.8rem;
        border: 1px solid var(--border);
        background: var(--paper);
        cursor: pointer;
        font-size: 0.8rem;
        border-radius: 999px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: all 0.15s ease;
    }
    .pill:hover {
        border-color: var(--accent);
        color: var(--accent);
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .pill.active {
        background: var(--accent);
        color: var(--paper);
        border-color: var(--accent);
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .thumb-badges { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-top: 0.35rem; }
    .thumb-subtitle { font-size: 0.78rem; color: var(--muted); margin-top: 0.35rem; }

    /* Dark mode */
    body.dark-mode { --ink: #e0e0e0; --ink-light: #aaa; --paper: #1a1a1a; --paper-alt: #252525; --border: #444; --muted: #888; }
    body.dark-mode header { background: #111; }

    /* Responsive */
    @media (max-width: 768px) {
        .container { padding: 1rem; }
        h1 { font-size: 1.25rem; }
        .summary-cards { flex-direction: column; }
        .subject-grid { grid-template-columns: 1fr; }
        .nav-panel { display: none; }
        .search-box, .dark-mode-toggle, .export-btn, .sidebar-toggle, .keyboard-hint { position: static; margin: 0.5rem; }
        .search-box input { width: 100%; }
    }

    /* Analysis info section and threshold controls */
    .analysis-info-section { margin: 1.5rem 0; }
    .analysis-info-content { padding: 1rem; }
    .info-group { margin: 1.5rem 0; }
    .info-group h4 { font-size: 0.95rem; font-weight: 600; margin: 0 0 0.75rem 0; color: var(--ink-light); }
    .info-table { width: auto; margin: 0; font-size: 0.85rem; }
    .info-table th { width: 180px; text-align: right; padding-right: 1rem; background: transparent; text-transform: none; font-weight: 500; color: var(--ink-light); }
    .info-table td { font-family: var(--font-sans); }
    .info-table code { background: var(--paper-alt); padding: 0.2rem 0.4rem; font-family: var(--font-mono); font-size: 0.8rem; }

    .threshold-controls { border-top: 1px solid var(--border); padding-top: 1.5rem; margin-top: 2rem; }
    .threshold-help { color: var(--muted); font-size: 0.85rem; margin: 0.5rem 0 1rem 0; }
    .threshold-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin: 1rem 0; }
    .threshold-control { display: flex; flex-direction: column; }
    .threshold-control label { font-size: 0.9rem; margin-bottom: 0.25rem; }
    .threshold-description { font-size: 0.8rem; color: var(--muted); margin: 0 0 0.5rem 0; }
    .threshold-input-group { display: flex; align-items: center; gap: 0.75rem; }
    .threshold-slider { flex: 1; height: 6px; border-radius: 3px; background: var(--border); outline: none; -webkit-appearance: none; }
    .threshold-slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 16px; height: 16px; border-radius: 50%; background: var(--accent); cursor: pointer; }
    .threshold-slider::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: var(--accent); cursor: pointer; border: none; }
    .threshold-slider:hover::-webkit-slider-thumb { background: var(--ink); }
    .threshold-slider:hover::-moz-range-thumb { background: var(--ink); }
    .threshold-value-input { width: 80px; padding: 0.4rem 0.5rem; border: 1px solid var(--border); font-family: var(--font-mono); font-size: 0.85rem; text-align: right; }
    .threshold-value-input:focus { outline: none; border-color: var(--accent); }

    .threshold-actions { margin-top: 1.5rem; display: flex; gap: 1rem; flex-wrap: wrap; }
    .btn-primary, .btn-secondary { padding: 0.6rem 1.2rem; border: none; cursor: pointer; font-size: 0.9rem; font-weight: 500; border-radius: 4px; }
    .btn-primary { background: var(--accent); color: var(--paper); }
    .btn-primary:hover { background: var(--ink); }
    .btn-secondary { background: var(--paper-alt); color: var(--ink); border: 1px solid var(--border); }
    .btn-secondary:hover { background: var(--border); }

    /* Aggregate statistics display */
    .aggregate-stats { background: var(--secondary); padding: 1rem; margin: 1rem 0; border-radius: 8px; display: flex; gap: 2rem; justify-content: center; font-size: 1.1rem; }
    .aggregate-stats strong { color: var(--primary); font-size: 1.3rem; }

    /* Modified threshold indicator */
    .btn-modified { animation: pulse 2s ease-in-out infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }

    /* Session flag badges */
    .session-flag-badge { display: inline-block; padding: 0.3rem 0.8rem; border-radius: 4px; font-size: 0.9rem; font-weight: 500; }

    /* Flag list styling */
    .flags-list { list-style: none; padding: 0; margin: 0.5rem 0; }
    .flag-item { padding: 0.5rem; margin: 0.25rem 0; background: rgba(231, 76, 60, 0.1); border-left: 3px solid var(--danger); border-radius: 4px; }
    .no-flags { padding: 0.5rem; margin: 0.25rem 0; background: rgba(39, 174, 96, 0.1); border-left: 3px solid var(--success); border-radius: 4px; color: var(--success); }

    @media print {
        body { background: white; }
        header { background: #222 !important; -webkit-print-color-adjust: exact; }
        .search-box, .dark-mode-toggle, .export-btn, .sidebar, .sidebar-toggle, .keyboard-hint, .nav-panel, .interactive-dashboard { display: none !important; }
        .container { max-width: 100%; padding: 0; }
        .card, .subject-card, table { border: 1px solid #ccc; }
    }

    @media (prefers-reduced-motion: reduce) {
        * { transition: none !important; animation: none !important; }
    }
</style>
"""
