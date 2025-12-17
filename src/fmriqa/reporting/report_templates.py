"""Jinja2 template environment setup and utilities."""

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .report_components.utils import (
    format_run_label,
    escape_html,
    escape_js_string,
    relative_asset_path,
    compute_session_metrics,
)
from .report_components.section_renderers import (
    render_metrics_table,
    render_metrics_summary,
)
from .report_components.constants import FLAG_DESCRIPTIONS


def get_package_dir() -> Path:
    """Get the package root directory."""
    # This file is at src/fmriqa/reporting/report_templates.py
    # We need to get src/fmriqa (parent of parent)
    return Path(__file__).parent.parent


def create_template_environment() -> Environment:
    """Create and configure the Jinja2 environment."""
    package_dir = get_package_dir()
    template_dir = package_dir / "templates"

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Add custom filters
    env.filters['sum_attr'] = lambda lst, attr: sum(len(getattr(item, attr)) for item in lst)
    env.filters['count_flagged'] = lambda runs: sum(1 for r in runs if any(r.flags.values()))
    env.filters['format_run_label'] = format_run_label
    env.filters['dict_items'] = lambda d: d.items()
    env.filters['escape_html'] = escape_html
    env.filters['escape_js'] = escape_js_string
    env.filters['relative_asset'] = lambda path, output_dir: relative_asset_path(path, output_dir)

    # Add global functions that can be called in templates
    env.globals['compute_session_metrics'] = compute_session_metrics
    env.globals['render_metrics_table'] = render_metrics_table
    env.globals['render_metrics_summary'] = render_metrics_summary
    env.globals['flag_descriptions'] = FLAG_DESCRIPTIONS

    return env


def get_static_paths(output_dir: Path) -> dict:
    """Get paths to static assets (CSS, JS) for embedding or linking.

    Parameters
    ----------
    output_dir : Path
        The output directory for the report

    Returns
    -------
    dict
        Dictionary with paths to CSS and JS files
    """
    package_dir = get_package_dir()
    static_dir = package_dir / "static"

    # For now, we'll inline the CSS and JS by reading the files
    # In production, you might want to copy them to output_dir and link
    return {
        'css_path': static_dir / "css" / "styles.css",
        'js_common_path': static_dir / "js" / "common.js",
        'js_quality_controls_path': static_dir / "js" / "quality_controls.js",
        'js_navigation_path': static_dir / "js" / "navigation.js",
        'js_export_path': static_dir / "js" / "export.js",
        'js_views_path': static_dir / "js" / "views.js",
        'js_study_path': static_dir / "js" / "study.js",
        'js_threshold_controls_path': static_dir / "js" / "threshold_controls.js",
    }


def inline_static_files(output_dir: Path) -> dict:
    """Read static files and prepare them for inlining in HTML.

    Parameters
    ----------
    output_dir : Path
        The output directory for the report

    Returns
    -------
    dict
        Dictionary with inline CSS and JS content
    """
    paths = get_static_paths(output_dir)

    # Read CSS
    css_content = paths['css_path'].read_text(encoding='utf-8')

    # Read JS files
    js_files = {
        'common': paths['js_common_path'].read_text(encoding='utf-8'),
        'quality_controls': paths['js_quality_controls_path'].read_text(encoding='utf-8'),
        'navigation': paths['js_navigation_path'].read_text(encoding='utf-8'),
        'export': paths['js_export_path'].read_text(encoding='utf-8'),
        'views': paths['js_views_path'].read_text(encoding='utf-8'),
        'study': paths['js_study_path'].read_text(encoding='utf-8'),
        'threshold_controls': paths['js_threshold_controls_path'].read_text(encoding='utf-8'),
    }

    return {
        'css_inline': css_content,
        'js_common': js_files['common'],
        'js_quality_controls': js_files['quality_controls'],
        'js_navigation': js_files['navigation'],
        'js_export': js_files['export'],
        'js_views': js_files['views'],
        'js_study': js_files['study'],
        'js_threshold_controls': js_files['threshold_controls'],
    }


def render_subject_report(
    template_env: Environment,
    context: dict,
    output_path: Path
) -> Path:
    """Render and save subject report.

    Parameters
    ----------
    template_env : Environment
        Jinja2 environment
    context : dict
        Template context data
    output_path : Path
        Path to save the report

    Returns
    -------
    Path
        Path to the saved report
    """
    template = template_env.get_template('subject_report.html')
    html = template.render(**context)
    output_path.write_text(html, encoding='utf-8')
    return output_path


def render_study_report(
    template_env: Environment,
    context: dict,
    output_path: Path
) -> Path:
    """Render and save study report.

    Parameters
    ----------
    template_env : Environment
        Jinja2 environment
    context : dict
        Template context data
    output_path : Path
        Path to save the report

    Returns
    -------
    Path
        Path to the saved report
    """
    template = template_env.get_template('study_report.html')
    html = template.render(**context)
    output_path.write_text(html, encoding='utf-8')
    return output_path
