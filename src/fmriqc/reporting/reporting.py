"""Report generation for fmriqc snapshot QA."""

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from fmriqc.io.structures import StudyResults, SubjectResults

# Color palette for sessions
SESSION_COLORS = [
    '#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#14b8a6',
    '#6366f1', '#84cc16', '#f43f5e', '#0ea5e9', '#a855f7'
]

# Metric metadata
METRIC_INFO = {
    'tsnr_median': {'label': 'tSNR', 'threshold': 30.0, 'direction': 'higher', 'unit': ''},
    'fd_median': {'label': 'FD', 'threshold': 0.3, 'direction': 'lower', 'unit': 'mm'},
    'dvars_std_median': {'label': 'DVARS', 'threshold': 2.5, 'direction': 'lower', 'unit': ''},
    'coverage_signal_fraction': {'label': 'Signal coverage', 'threshold': 0.85, 'direction': 'higher', 'unit': ''},
    'gcor': {'label': 'GCOR', 'threshold': None, 'direction': 'contextual', 'unit': ''},
    'apparent_smoothness_fwhm': {'label': 'Apparent smoothness', 'threshold': None, 'direction': 'contextual', 'unit': 'mm'},
    'outlier_percent_above': {'label': 'Outlier %', 'threshold': 10.0, 'direction': 'lower', 'unit': '%'},
    'fd_percent_above': {'label': 'FD flagged %', 'threshold': 20.0, 'direction': 'lower', 'unit': '%'},
}


def get_static_dir() -> Path:
    """Get path to static files directory."""
    return Path(__file__).parent / 'static'


def get_templates_dir() -> Path:
    """Get path to templates directory."""
    return Path(__file__).parent / 'templates'


def load_static_file(filename: str) -> str:
    """Load a static file as string."""
    filepath = get_static_dir() / filename
    if filepath.exists():
        return filepath.read_text()
    return ''


def make_style_tag(content: str) -> str:
    """Wrap CSS content in a style tag."""
    if not content:
        return ''
    return f'<style>\n{content}\n</style>'


def make_script_tag(content: str) -> str:
    """Wrap JS content in a script tag."""
    if not content:
        return ''
    return f'<script>\n{content}\n</script>'


def create_template_env() -> Environment:
    """Create Jinja2 environment with template directory."""
    return Environment(
        loader=FileSystemLoader(str(get_templates_dir())),
        autoescape=True
    )


def compute_metric_distributions(study: StudyResults) -> Dict[str, List[float]]:
    """Compute distributions of each metric across all runs."""
    distributions: Dict[str, List[float]] = {}

    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                for key, value in run.metrics.items():
                    if isinstance(value, (int, float)) and value is not None:
                        if key not in distributions:
                            distributions[key] = []
                        distributions[key].append(float(value))

    return distributions


def compute_quality_summary(study: StudyResults) -> Dict[str, Any]:
    """Compute quality summary (good/warn/bad counts)."""
    good = warn = bad = 0

    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                flag_count = sum(1 for v in run.flags.values() if v)
                if flag_count == 0:
                    good += 1
                elif flag_count <= 2:
                    warn += 1
                else:
                    bad += 1

    total = good + warn + bad
    return {
        'good_count': good,
        'warn_count': warn,
        'bad_count': bad,
        'good_percent': (good / total * 100) if total > 0 else 0,
        'warn_percent': (warn / total * 100) if total > 0 else 0,
        'bad_percent': (bad / total * 100) if total > 0 else 0,
    }


def _normalize_metric_aliases(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Return report metrics with current names plus legacy aliases if present."""
    normalized = dict(metrics)
    if "coverage_signal_fraction" not in normalized and "coverage" in normalized:
        normalized["coverage_signal_fraction"] = normalized["coverage"]
    if "apparent_smoothness_fwhm" not in normalized and "smoothness_fwhm" in normalized:
        normalized["apparent_smoothness_fwhm"] = normalized["smoothness_fwhm"]
    return normalized


def prepare_study_data(study: StudyResults, output_dir: Path) -> Dict[str, Any]:
    """Prepare study data for JavaScript."""
    distributions = compute_metric_distributions(study)

    runs_data = []
    for subject in study.subjects:
        for session in subject.sessions:
            for run in session.runs:
                run_id = f"sub-{subject.subject}_ses-{session.session}_run-{run.info.run}"
                if run.info.task:
                    run_id += f"_task-{run.info.task}"

                metrics = _normalize_metric_aliases(run.metrics)
                runs_data.append({
                    'id': run.info.get_identifier(),
                    'subject': f"sub-{subject.subject}",
                    'session': f"ses-{session.session}",
                    'task': run.info.task or '',
                    'run': run.info.run,
                    'nVolumes': run.metrics.get('n_volumes'),
                    'tr': run.metrics.get('tr'),
                    'maskSource': run.mask_info.source if run.mask_info else '',
                    'motionSource': run.motion_info.source if run.motion_info else '',
                    'metrics': {k: float(v) if isinstance(v, (int, float)) else v
                               for k, v in metrics.items()},
                    'flags': run.flags,
                })

    return {
        'runs': runs_data,
        'distributions': distributions,
        'metricInfo': dict(METRIC_INFO),
        'subjects': [f"sub-{s.subject}" for s in study.subjects],
        'snapshot': study.analysis_metadata.get('snapshot', {}),
        'thresholds': study.analysis_metadata.get('thresholds', {}),
    }


def prepare_subject_data(subject: SubjectResults, output_dir: Path, assets_base: Optional[Path] = None) -> Dict[str, Any]:
    """Prepare subject data for JavaScript.

    Parameters
    ----------
    subject : SubjectResults
        Subject results
    output_dir : Path
        Output directory for reports (where subject_report.html will be)
    assets_base : Path, optional
        Base directory where assets (images) are located. If None, uses output_dir.
    """
    runs_data = []

    # Compute metric ranges from data
    all_metrics: Dict[str, List[float]] = {}
    for session in subject.sessions:
        for run in session.runs:
            for key, value in run.metrics.items():
                if isinstance(value, (int, float)) and value is not None:
                    if key not in all_metrics:
                        all_metrics[key] = []
                    all_metrics[key].append(float(value))

    # Build metric info with computed ranges
    metric_info = {}
    for key, info in METRIC_INFO.items():
        if key in all_metrics:
            values = all_metrics[key]
            val_min = min(values)
            val_max = max(values)
            padding = (val_max - val_min) * 0.1 if val_max != val_min else 0.1

            metric_info[key] = {
                **info,
                'key': key,
                'min': val_min - padding,
                'max': val_max + padding,
            }

    for session in subject.sessions:
        for run in session.runs:
            run_id = run.info.get_identifier()

            # Use asset_paths directly - convert to strings
            thumbnail_path = run.asset_paths.get('thumbnail')
            figure_path = run.asset_paths.get('figure')
            carpet_path = run.asset_paths.get('carpetplot')

            # Convert Path objects to strings
            if thumbnail_path:
                thumbnail_path = str(thumbnail_path)
            if figure_path:
                figure_path = str(figure_path)
            if carpet_path:
                carpet_path = str(carpet_path)

            # If we have absolute paths, try to make them relative to assets_base
            if assets_base:
                if run.thumbnail_path and Path(run.thumbnail_path).is_absolute():
                    try:
                        thumbnail_path = str(Path(run.thumbnail_path).relative_to(assets_base))
                    except ValueError:
                        pass
                if run.figure_path and Path(run.figure_path).is_absolute():
                    try:
                        figure_path = str(Path(run.figure_path).relative_to(assets_base))
                    except ValueError:
                        pass
                if run.carpetplot_path and Path(run.carpetplot_path).is_absolute():
                    try:
                        carpet_path = str(Path(run.carpetplot_path).relative_to(assets_base))
                    except ValueError:
                        pass

            # For subject reports in subdirectory, paths need to go up one level
            # to reach assets in the main output directory
            prefix = "../"

            # Collect spatial map paths for flipbook viewer
            spatial_maps = {}
            for key, path in run.asset_paths.items():
                if key.startswith('spatial_map_'):
                    map_type = key.replace('spatial_map_', '')
                    if path:
                        path_obj = Path(path) if not isinstance(path, Path) else path
                        # Make absolute paths relative to assets_base
                        if assets_base and path_obj.is_absolute():
                            try:
                                path = str(path_obj.relative_to(assets_base))
                            except ValueError:
                                path = str(path)
                        else:
                            path = str(path)
                        spatial_maps[map_type] = prefix + path

            metrics = _normalize_metric_aliases(run.metrics)
            runs_data.append({
                'id': run_id,
                'session': f"ses-{session.session}",
                'run': run.info.run,
                'task': run.info.task or '',
                'label': f"run-{run.info.run}",
                'metrics': {k: float(v) if isinstance(v, (int, float)) else v
                           for k, v in metrics.items()},
                'flags': run.flags,
                'thumbnailPath': prefix + thumbnail_path if thumbnail_path else None,
                'figurePath': prefix + figure_path if figure_path else None,
                'carpetPath': prefix + carpet_path if carpet_path else None,
                'spatialMaps': spatial_maps,
                'provenance': run.provenance.to_dict() if run.provenance else {},
                'warnings': run.warnings,
            })

    return {
        'subject': f"sub-{subject.subject}",
        'snapshotId': subject.sessions[0].runs[0].snapshot.id if subject.sessions and subject.sessions[0].runs and subject.sessions[0].runs[0].snapshot else 'legacy',
        'snapshotLabel': subject.sessions[0].runs[0].snapshot.label if subject.sessions and subject.sessions[0].runs and subject.sessions[0].runs[0].snapshot else '',
        'reportId': subject.sessions[0].runs[0].snapshot.id if subject.sessions and subject.sessions[0].runs and subject.sessions[0].runs[0].snapshot else 'legacy',
        'runs': runs_data,
        'metricInfo': metric_info,
    }


def prepare_outlier_data(study: StudyResults) -> Optional[Dict[str, Any]]:
    """Prepare outlier data for legacy report sections/tests."""
    report = getattr(study, "outlier_report", None)
    if not report:
        return None

    flagged = set(report.get("multivariate_outliers", []))
    flagged.update(report.get("extreme_motion", []))
    flagged.update(report.get("low_tsnr", []))
    for metric_outliers in report.get("univariate_outliers", {}).values():
        flagged.update(metric_outliers)

    if not flagged:
        return None

    explanations = {run_id: [] for run_id in sorted(flagged)}
    for run_id in report.get("multivariate_outliers", []):
        distance = report.get("mahalanobis_distances", {}).get(run_id)
        detail = f"Mahalanobis distance {distance:.2f}" if isinstance(distance, (int, float)) else "Multivariate outlier"
        explanations.setdefault(run_id, []).append(detail)
    for run_id in report.get("extreme_motion", []):
        explanations.setdefault(run_id, []).append("Extreme motion")
    for run_id in report.get("low_tsnr", []):
        explanations.setdefault(run_id, []).append("Low tSNR")
    for metric, run_ids in report.get("univariate_outliers", {}).items():
        for run_id in run_ids:
            explanations.setdefault(run_id, []).append(f"Univariate outlier: {metric}")

    return {
        **report,
        "outlier_explanations": explanations,
    }


def prepare_exclusion_data(study: StudyResults) -> Optional[Dict[str, Any]]:
    """Prepare candidate review flag data for legacy report sections/tests."""
    report = getattr(study, "exclusion_report", None)
    if report is None:
        return None

    excluded_runs = [run for run in report.run_exclusions if run.excluded]
    high_scrub_runs = [
        scrub for scrub in report.volume_scrubbing
        if scrub.data_loss_percent > 10.0
    ]

    return {
        "summary": report.summary,
        "stringency": report.stringency,
        "criteria": report.criteria,
        "excluded_runs": excluded_runs,
        "high_scrub_runs": high_scrub_runs,
    }


def generate_study_report(
    study: StudyResults,
    output_dir: Path,
    version: str = "0.1.0",
    study_aggregate_path: Optional[Path] = None,
) -> Path:
    """Generate the study overview report.

    Parameters
    ----------
    study : StudyResults
        Study results
    output_dir : Path
        Output directory
    version : str
        fmriqc version string

    Returns
    -------
    Path
        Path to generated report
    """
    env = create_template_env()
    template = env.get_template('study_report.html')

    # Load static files
    css_content = load_static_file('css/styles.css')
    d3_content = load_static_file('js/vendor/d3.v7.min.js')
    charts_content = load_static_file('js/charts.js')
    main_content = load_static_file('js/main.js')
    # Compute distributions for medians
    distributions = compute_metric_distributions(study)

    # Prepare subject summaries
    subjects_data = []
    for subj in study.subjects:
        n_runs = sum(len(s.runs) for s in subj.sessions)
        n_flagged = sum(1 for s in subj.sessions for r in s.runs if any(r.flags.values()))
        n_excluded = 0  # Could compute from exclusion report

        # Get median metrics for subject
        subj_tsnr = []
        subj_fd = []
        for session in subj.sessions:
            for run in session.runs:
                if 'tsnr_median' in run.metrics:
                    subj_tsnr.append(run.metrics['tsnr_median'])
                if 'fd_median' in run.metrics:
                    subj_fd.append(run.metrics['fd_median'])

        subjects_data.append({
            'id': f"sub-{subj.subject}",
            'n_sessions': len(subj.sessions),
            'n_runs': n_runs,
            'n_flagged': n_flagged,
            'n_excluded': n_excluded,
            'tsnr': statistics.median(subj_tsnr) if subj_tsnr else 0,
            'fd': statistics.median(subj_fd) if subj_fd else 0,
            'report_path': f"sub-{subj.subject}/subject_report.html",
        })

    # Prepare scatter metrics
    scatter_metrics = [
        {'key': k, 'label': v['label']}
        for k, v in METRIC_INFO.items()
        if k in distributions
    ]

    # Default and additional metrics for distribution toggles
    default_metric_keys = ['tsnr_median', 'fd_median', 'dvars_std_median']
    default_metrics = [{'key': k, 'label': METRIC_INFO[k]['label']}
                       for k in default_metric_keys if k in distributions]
    additional_metrics = [{'key': k, 'label': METRIC_INFO[k]['label']}
                          for k in METRIC_INFO.keys()
                          if k not in default_metric_keys and k in distributions]

    # Quality summary
    quality = compute_quality_summary(study)

    # Exclusion info
    exclusion_count = 0
    exclusion_reasons = ""
    if study.exclusion_report:
        excluded = [e for e in study.exclusion_report.run_exclusions if e.excluded]
        exclusion_count = len(excluded)
        if exclusion_count > 0:
            reasons = {}
            for e in excluded:
                for r in e.reasons:
                    # Convert ExclusionReason enum/object to string for counting
                    reason_str = str(r.value) if hasattr(r, 'value') else str(r)
                    reasons[reason_str] = reasons.get(reason_str, 0) + 1
            exclusion_reasons = ", ".join(f"{v} {k}" for k, v in reasons.items())

    # Total runs
    n_runs = sum(len(s.runs) for subj in study.subjects for s in subj.sessions)

    # Median metrics
    median_tsnr = statistics.median(distributions.get('tsnr_median', [0])) if distributions.get('tsnr_median') else 0
    median_fd = statistics.median(distributions.get('fd_median', [0])) if distributions.get('fd_median') else 0

    # Prepare study data for JS
    study_data = prepare_study_data(study, output_dir)
    snapshot = study.analysis_metadata.get('snapshot', {})
    thresholds = study.analysis_metadata.get('thresholds', {})
    runs_table = study_data['runs']

    # Render
    html = template.render(
        study_name=study.analysis_metadata.get('study_name', 'Study'),
        snapshot=snapshot,
        thresholds=thresholds,
        generation_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
        version=version,
        n_subjects=len(study.subjects),
        n_runs=n_runs,
        median_tsnr=median_tsnr,
        median_fd=median_fd,
        quality=quality,
        subjects=subjects_data,
        runs_table=runs_table,
        default_metrics=default_metrics,
        additional_metrics=additional_metrics,
        scatter_metrics=scatter_metrics,
        exclusion_count=exclusion_count,
        exclusion_reasons=exclusion_reasons,
        study_data_json=json.dumps(study_data),
        css_content=css_content,
        d3_content=d3_content,
        charts_content=charts_content,
        main_content=main_content,
    )

    # Write report
    report_path = output_dir / 'index.html'
    report_path.write_text(html)

    return report_path


def generate_subject_report(
    subject: SubjectResults,
    output_dir: Path,
    study_report_path: str = "../index.html",
    reviews_path: Optional[Path] = None,
    version: str = "0.1.0",
    **_: Any,
) -> Path:
    """Generate a subject report.

    Parameters
    ----------
    subject : SubjectResults
        Subject results
    output_dir : Path
        Output directory for this subject
    study_report_path : str
        Relative path back to study report
    reviews_path : Path, optional
        Path to existing reviews JSON file
    version : str
        fmriqc version string

    Returns
    -------
    Path
        Path to generated report
    """
    env = create_template_env()
    template = env.get_template('subject_report.html')

    # Load static files
    css_content = load_static_file('css/styles.css')
    d3_content = load_static_file('js/vendor/d3.v7.min.js')
    charts_content = load_static_file('js/charts.js')
    main_content = load_static_file('js/main.js')
    flipbook_content = load_static_file('js/flipbook.js')
    reviews_content = load_static_file('js/reviews.js')

    # Prepare subject data
    subject_data = prepare_subject_data(subject, output_dir)

    # Session colors
    sessions = list({r['session'] for r in subject_data['runs']})
    session_colors = {s: SESSION_COLORS[i % len(SESSION_COLORS)]
                      for i, s in enumerate(sorted(sessions))}

    # Prepare runs for template
    runs_template = []
    for run in subject_data['runs']:
        runs_template.append({
            'id': run['id'],
            'label': run['label'],
            'session': run['session'],
            'task': run['task'],
            'review_status': None,  # Will be set by JS from reviews
        })

    # Timeline metrics - show more by default
    timeline_metrics = []
    default_timeline_keys = ['tsnr_median', 'fd_median', 'dvars_std_median', 'coverage_signal_fraction']
    for key in ['tsnr_median', 'fd_median', 'dvars_std_median', 'coverage_signal_fraction', 'gcor', 'apparent_smoothness_fwhm']:
        if key in subject_data['metricInfo']:
            info = subject_data['metricInfo'][key]
            timeline_metrics.append({
                'key': key,
                'label': info['label'],
                'default': key in default_timeline_keys,
            })

    # Count flagged runs
    n_flagged = sum(1 for s in subject.sessions for r in s.runs if any(r.flags.values()))

    # Load existing reviews if available
    initial_reviews = {}
    if reviews_path and reviews_path.exists():
        try:
            with open(reviews_path) as f:
                data = json.load(f)
                initial_reviews = data.get('reviews', {})
        except Exception:
            pass

    # Render
    html = template.render(
        subject_id=f"sub-{subject.subject}",
        generation_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
        version=version,
        study_report_path=study_report_path,
        n_sessions=len(subject.sessions),
        n_runs=len(subject_data['runs']),
        n_flagged=n_flagged,
        runs=runs_template,
        session_colors=session_colors,
        timeline_metrics=timeline_metrics,
        subject_data_json=json.dumps(subject_data),
        initial_reviews_json=json.dumps(initial_reviews),
        css_content=css_content,
        d3_content=d3_content,
        charts_content=charts_content,
        main_content=main_content,
        flipbook_content=flipbook_content,
        reviews_content=reviews_content,
    )

    # Write report
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / 'subject_report.html'
    report_path.write_text(html)

    return report_path


def generate_all_reports(
    study: StudyResults,
    output_dir: Path,
    version: str = "0.1.0"
) -> Dict[str, Path]:
    """Generate all reports for a study.

    Parameters
    ----------
    study : StudyResults
        Study results
    output_dir : Path
        Output directory
    version : str
        fmriqc version string

    Returns
    -------
    Dict[str, Path]
        Dictionary mapping report names to paths
    """
    reports = {}

    # Generate study report
    reports['study'] = generate_study_report(study, output_dir, version)

    # Generate subject reports
    for subject in study.subjects:
        subject_dir = output_dir / f"sub-{subject.subject}"
        reviews_path = subject_dir / 'qa_reviews.json'

        reports[f"sub-{subject.subject}"] = generate_subject_report(
            subject,
            subject_dir,
            study_report_path="../index.html",
            reviews_path=reviews_path if reviews_path.exists() else None,
            version=version,
        )

    return reports
