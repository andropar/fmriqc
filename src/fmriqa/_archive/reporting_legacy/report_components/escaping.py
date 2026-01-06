"""Escaping and path utilities for QA report generation.

This module provides functions for safely escaping text for use in HTML
and JavaScript contexts, as well as path manipulation for asset references.
"""

from pathlib import Path
from typing import Optional


def escape_html(text: str) -> str:
    """Escape HTML special characters.

    Converts characters that have special meaning in HTML to their
    entity equivalents to prevent HTML injection.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Escaped text safe for HTML

    Examples
    --------
    >>> escape_html("<script>alert('XSS')</script>")
    '&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;'
    >>> escape_html('R&D "Project"')
    'R&amp;D &quot;Project&quot;'
    """
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))


def escape_js_string(text: str) -> str:
    """Escape string for use in JavaScript string literals.

    Escapes characters that would break JavaScript string literals,
    including quotes, backslashes, and newlines.

    Parameters
    ----------
    text : str
        Text to escape

    Returns
    -------
    str
        Escaped text safe for JavaScript strings

    Examples
    --------
    >>> escape_js_string("He said \\"hello\\"")
    'He said \\\\"hello\\\\"'
    >>> escape_js_string("Line 1\\nLine 2")
    'Line 1\\\\nLine 2'
    """
    return (text.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", "\\r"))


def relative_asset_path(path: Optional[Path], base: Path) -> str:
    """Return a POSIX-style relative path for assets.

    Computes a relative path from base directory to the asset path,
    suitable for use in HTML src/href attributes. Always returns
    forward slashes regardless of platform.

    Parameters
    ----------
    path : Path or None
        Absolute path to the asset file
    base : Path
        Base directory (typically the report output directory)

    Returns
    -------
    str
        POSIX-style relative path, or empty string if path is None

    Examples
    --------
    >>> from pathlib import Path
    >>> base = Path("/output/qa")
    >>> asset = Path("/output/qa/sub-01/figure.png")
    >>> relative_asset_path(asset, base)
    'sub-01/figure.png'
    >>> relative_asset_path(None, base)
    ''
    """
    import os

    if path is None:
        return ""
    path = path.resolve()
    base = base.resolve()
    try:
        rel = path.relative_to(base)
    except ValueError:
        # Fallback for paths outside base directory
        rel = Path(os.path.relpath(path, base))
    return rel.as_posix()
