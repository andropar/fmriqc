"""Visualization functions for QA reports."""

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np

from fmriqc.core.constants import PlotStyle
from fmriqc.io.structures import RunInfo, StudyResults
from fmriqc.utils import is_finite_number


def _mid_slices(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Get middle slices from 3D volume."""
    cx = data.shape[0] // 2
    cy = data.shape[1] // 2
    cz = data.shape[2] // 2
    return (data[cx, :, :], data[:, cy, :], data[:, :, cz])


def _multi_view_slices(
    data: np.ndarray,
    n_slices: int = 5
) -> Dict[str, List[np.ndarray]]:
    """
    Get multiple slices from each orientation for mosaic display.

    Parameters
    ----------
    data : np.ndarray
        3D volume (x, y, z)
    n_slices : int
        Number of slices to extract per orientation (default: 5)

    Returns
    -------
    dict
        Dictionary with keys 'sagittal', 'coronal', 'axial', each containing
        a list of 2D slice arrays.
    """
    # Calculate slice positions (evenly spaced, avoiding edges)
    def get_slice_indices(dim_size: int, n: int) -> List[int]:
        margin = dim_size // 10  # 10% margin on each side
        usable = dim_size - 2 * margin
        if usable < n:
            # Fall back to full range if volume is too small
            margin = 0
            usable = dim_size
        step = usable // (n + 1)
        return [margin + step * (i + 1) for i in range(n)]

    sagittal_idx = get_slice_indices(data.shape[0], n_slices)
    coronal_idx = get_slice_indices(data.shape[1], n_slices)
    axial_idx = get_slice_indices(data.shape[2], n_slices)

    return {
        'sagittal': [data[i, :, :] for i in sagittal_idx],
        'coronal': [data[:, i, :] for i in coronal_idx],
        'axial': [data[:, :, i] for i in axial_idx],
    }


def display_mosaic(
    ax: plt.Axes,
    data: np.ndarray,
    title: str,
    cmap: str = "viridis",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    mask: Optional[np.ndarray] = None,
    n_slices: int = 3,
) -> plt.cm.ScalarMappable:
    """
    Display a multi-view mosaic (sagittal, coronal, axial) in a single axes.

    Creates a 3-row display with sagittal, coronal, and axial views,
    each showing n_slices evenly spaced slices.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes to draw on
    data : np.ndarray
        3D volume to display
    title : str
        Title for the subplot
    cmap : str
        Colormap name
    vmin, vmax : float, optional
        Color scale limits
    mask : np.ndarray, optional
        Mask to overlay as contours
    n_slices : int
        Number of slices per orientation (default: 3)

    Returns
    -------
    ScalarMappable
        The image object for colorbar creation
    """
    # Auto-scale if not specified
    if vmin is None and np.any(data > 0):
        vmin = np.percentile(data[data > 0], 2)
    if vmax is None and np.any(data > 0):
        vmax = np.percentile(data[data > 0], 98)

    # Get slices from each orientation
    slices = _multi_view_slices(data, n_slices)

    # Create mosaic: 3 rows (orientations) x n_slices columns
    rows = []
    for orientation in ['sagittal', 'coronal', 'axial']:
        row_slices = slices[orientation]
        # Rotate each slice appropriately and concatenate horizontally
        rotated = [np.rot90(s) for s in row_slices]
        # Pad to same height if needed (for non-isotropic voxels)
        max_height = max(s.shape[0] for s in rotated)
        max_width = max(s.shape[1] for s in rotated)
        padded = []
        for s in rotated:
            pad_h = max_height - s.shape[0]
            pad_w = max_width - s.shape[1]
            if pad_h > 0 or pad_w > 0:
                s = np.pad(s, ((0, pad_h), (0, pad_w)), mode='constant', constant_values=0)
            padded.append(s)
        row = np.hstack(padded)
        rows.append(row)

    # Stack rows vertically with small gap
    max_row_width = max(r.shape[1] for r in rows)
    padded_rows = []
    for r in rows:
        if r.shape[1] < max_row_width:
            r = np.pad(r, ((0, 0), (0, max_row_width - r.shape[1])), mode='constant', constant_values=0)
        padded_rows.append(r)
    mosaic = np.vstack(padded_rows)

    # Display
    im = ax.imshow(mosaic, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')
    ax.set_title(title, fontsize=PlotStyle.FONT_LABEL)
    ax.axis("off")

    # Add orientation labels
    row_height = mosaic.shape[0] // 3
    for i, label in enumerate(['Sag', 'Cor', 'Ax']):
        ax.text(-5, row_height * i + row_height // 2, label,
                fontsize=PlotStyle.FONT_SMALL, va='center', ha='right', fontweight='bold')

    return im


def encode_image_base64(path: Path) -> str:
    """Encode image as base64 for embedding in HTML."""
    with path.open("rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _center_slices_from_mask(mask: np.ndarray) -> Tuple[int, int, int]:
    """
    Pick slice indices near the center of mass of the mask.
    Falls back to geometric center if mask is empty.
    """
    if mask is None:
        raise ValueError("Mask is required to pick center slices")
    if not np.any(mask):
        cx = mask.shape[0] // 2
        cy = mask.shape[1] // 2
        cz = mask.shape[2] // 2
        return cx, cy, cz
    coords = np.argwhere(mask)
    cx = int(np.median(coords[:, 0]))
    cy = int(np.median(coords[:, 1]))
    cz = int(np.median(coords[:, 2]))
    return cx, cy, cz


def _plot_slice_with_mask(ax: plt.Axes, img_slice: np.ndarray, mask_slice: np.ndarray, title: str):
    """Helper to plot a single slice with semi-transparent mask fill and contour."""
    rotated_img = np.rot90(img_slice)
    rotated_mask = np.rot90(mask_slice.astype(float))
    ax.imshow(rotated_img, cmap="gray", interpolation="nearest")
    ax.imshow(np.ma.masked_where(rotated_mask == 0, rotated_mask), cmap="spring", alpha=0.25, interpolation="nearest")
    try:
        ax.contour(rotated_mask, levels=[0.5], colors="magenta", linewidths=0.7)
    except Exception:
        pass
    ax.set_title(title, fontsize=PlotStyle.FONT_SMALL)
    ax.axis("off")


def create_run_thumbnail(
    mean_img: np.ndarray,
    mask: np.ndarray,
    output_path: Path,
    figsize: Tuple[float, float] = (1.5, 1.5),
    n_slices: int = 3,
) -> Path:
    """
    Create a compact axial-only thumbnail with mask overlay for table rows.

    Shows a small grid of axial slices with the mask contour overlaid,
    suitable for quick visual identification in a table cell.

    Parameters
    ----------
    mean_img : np.ndarray
        3D mean BOLD volume
    mask : np.ndarray
        3D brain mask
    output_path : Path
        Output file path
    figsize : tuple
        Figure size (small for table use)
    n_slices : int
        Number of axial slices to show
    """
    mask_bool = mask.astype(bool)

    # Get evenly spaced axial slice indices
    z_dim = mean_img.shape[2]
    margin = z_dim // 6
    usable = z_dim - 2 * margin
    step = usable // (n_slices + 1)
    z_indices = [margin + step * (i + 1) for i in range(n_slices)]

    # Create a horizontal strip of axial slices
    fig, axes = plt.subplots(1, n_slices, figsize=figsize)
    if n_slices == 1:
        axes = [axes]

    for ax, z in zip(axes, z_indices):
        img_slice = np.rot90(mean_img[:, :, z])
        mask_slice = np.rot90(mask_bool[:, :, z])

        ax.imshow(img_slice, cmap='gray', interpolation='nearest')
        # Add mask contour
        try:
            ax.contour(mask_slice, levels=[0.5], colors='cyan', linewidths=0.5)
        except Exception:
            pass
        ax.axis('off')

    plt.subplots_adjust(wspace=0.02, hspace=0, left=0, right=1, top=1, bottom=0)
    fig.savefig(output_path, dpi=80, bbox_inches='tight', pad_inches=0.01, facecolor='black')
    plt.close(fig)
    return output_path


# ============================================================================
# Helper functions for create_run_figure()
# ============================================================================

def _build_run_summary_title(
    info: RunInfo,
    mask: Optional[np.ndarray],
    maps: Dict[str, np.ndarray],
    fd_series: Optional[np.ndarray],
    thresholds: Dict[str, float]
) -> str:
    """
    Build summary title string with key metrics.

    Parameters
    ----------
    info : RunInfo
        Run metadata
    mask : np.ndarray, optional
        Brain mask
    maps : dict
        Spatial maps dictionary
    fd_series : np.ndarray, optional
        Framewise displacement time series
    thresholds : dict
        Threshold values

    Returns
    -------
    str
        Formatted title string
    """
    stats_parts = []
    if mask is not None:
        n_voxels = np.sum(mask > 0)
        stats_parts.append(f"Voxels: {n_voxels:,}")
    if "tsnr" in maps:
        tsnr_med = np.median(maps["tsnr"][maps["tsnr"] > 0])
        stats_parts.append(f"tSNR: {tsnr_med:.1f}")
    if fd_series is not None:
        fd_med = np.median(fd_series)
        fd_pct = np.mean(fd_series > thresholds.get("fd", 0.2)) * 100
        stats_parts.append(f"FD: {fd_med:.3f}mm ({fd_pct:.1f}% high)")

    title_str = f"sub-{info.subject} ses-{info.session} run-{info.run}"
    if stats_parts:
        title_str += f"  |  {' • '.join(stats_parts)}"
    return title_str


def _add_value_annotation(
    ax: plt.Axes,
    data: np.ndarray,
    mask: Optional[np.ndarray] = None,
    unit: str = ""
) -> None:
    """
    Add min/median/max annotation below a plot.

    Parameters
    ----------
    ax : plt.Axes
        Axes to annotate
    data : np.ndarray
        Data array
    mask : np.ndarray, optional
        Mask to restrict values
    unit : str
        Unit string to append
    """
    if mask is not None:
        vals = data[mask > 0]
    else:
        vals = data[data != 0] if np.any(data != 0) else data.ravel()
    if len(vals) > 0:
        med = np.median(vals)
        mn, mx = np.min(vals), np.max(vals)
        text = f"min:{mn:.1f} med:{med:.1f} max:{mx:.1f}{unit}"
        ax.text(0.5, -0.02, text, transform=ax.transAxes, fontsize=PlotStyle.FONT_SMALL,
                ha="center", va="top", color="gray", style="italic")


def _display_spatial_map(
    ax: plt.Axes,
    data: np.ndarray,
    title: str,
    use_mosaic: bool = True,
    cmap: str = "viridis",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None
) -> plt.cm.ScalarMappable:
    """
    Display a spatial map with optional mosaic or single slice.

    Parameters
    ----------
    ax : plt.Axes
        Axes to draw on
    data : np.ndarray
        3D volume to display
    title : str
        Title for the subplot
    use_mosaic : bool
        If True, show multi-view mosaic; if False, show single axial slice
    cmap : str
        Colormap name
    vmin, vmax : float, optional
        Color scale limits

    Returns
    -------
    ScalarMappable
        The image object for colorbar creation
    """
    if use_mosaic:
        im = display_mosaic(ax, data, title, cmap=cmap, vmin=vmin, vmax=vmax, n_slices=3)
    else:
        _, _, axial = _mid_slices(data)
        if vmin is None and np.any(data > 0):
            vmin = np.percentile(data[data > 0], 2)
        if vmax is None and np.any(data > 0):
            vmax = np.percentile(data[data > 0], 98)
        im = ax.imshow(np.rot90(axial), cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(title, fontsize=PlotStyle.FONT_LABEL)
        ax.axis("off")
    return im


def _plot_dvars_panel(ax: plt.Axes, series: Dict[str, np.ndarray], style_dict: Dict[str, Any]) -> None:
    """
    Plot DVARS time series panel.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    series : dict
        Time series data dictionary
    style_dict : dict
        Style configuration (colors, threshold style)
    """
    time = np.arange(series["dvars"].shape[0])
    valid_time = time[1:]
    dvars_color = style_dict["dvars_color"]
    threshold_style = style_dict["threshold_style"]

    # Plot standardized DVARS
    if "dvars_std" in series:
        dvars_vals = series["dvars_std"][1:]
        ax.fill_between(valid_time, dvars_vals, alpha=0.3, color=dvars_color)
        ax.plot(valid_time, dvars_vals, color=dvars_color, linewidth=1, label="DVARS (std)")

        # Shade high DVARS volumes
        dvars_thresh = series.get("dvars_threshold", 2.5)
        high_dvars = dvars_vals > dvars_thresh
        if np.any(high_dvars):
            ax.fill_between(valid_time, 0, dvars_vals, where=high_dvars,
                          alpha=0.4, color="red", label=f">{dvars_thresh:.1f}")
    else:
        ax.plot(valid_time, series["dvars"][1:], color=dvars_color, linewidth=1, label="DVARS")

    dvars_thresh = series.get("dvars_threshold", 2.5)
    ax.axhline(dvars_thresh, **threshold_style, label=f"Thresh ({dvars_thresh:.1f})")
    ax.set_title("DVARS", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_xlabel("Volume", fontsize=9)
    ax.set_ylabel("DVARS (std)", fontsize=9)
    ax.set_xlim(0, len(time) - 1)


def _plot_fd_panel(
    ax: plt.Axes,
    fd_series: Optional[np.ndarray],
    thresholds: Dict[str, float],
    style_dict: Dict[str, Any]
) -> None:
    """
    Plot framewise displacement time series panel.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    fd_series : np.ndarray, optional
        FD time series
    thresholds : dict
        Threshold values
    style_dict : dict
        Style configuration
    """
    if fd_series is not None:
        fd_color = style_dict["fd_color"]
        threshold_style = style_dict["threshold_style"]

        ax.fill_between(range(len(fd_series)), fd_series, alpha=0.3, color=fd_color)
        ax.plot(fd_series, color=fd_color, linewidth=1, label="FD")

        fd_thresh = thresholds.get("fd", 0.2)
        ax.axhline(fd_thresh, **threshold_style, label=f"Thresh ({fd_thresh}mm)")

        # Shade high-motion volumes
        high_motion = fd_series > fd_thresh
        if np.any(high_motion):
            ax.fill_between(range(len(fd_series)), 0, fd_series, where=high_motion,
                          alpha=0.4, color="darkred", label=f"High ({np.sum(high_motion)})")

        ax.set_title("Framewise Displacement", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax.legend(fontsize=7, loc="upper right")
        ax.set_xlabel("Volume", fontsize=9)
        ax.set_ylabel("FD (mm)", fontsize=9)
        ax.set_xlim(0, len(fd_series) - 1)
        ax.set_ylim(0, max(0.5, np.percentile(fd_series, 99) * 1.1))
    else:
        ax.text(0.5, 0.5, "FD not available", ha="center", va="center", fontsize=10, color="gray")
        ax.set_title("Framewise Displacement", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax.axis("off")


def _plot_global_signal_panel(ax: plt.Axes, gs_signal: np.ndarray, style_dict: Dict[str, Any]) -> None:
    """
    Plot global signal panel with raw and detrended versions.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    gs_signal : np.ndarray
        Global signal time series
    style_dict : dict
        Style configuration
    """
    gs_color = style_dict["gs_color"]
    gs_detrend_color = PlotStyle.COLOR_SUCCESS

    ax.fill_between(range(len(gs_signal)), gs_signal, alpha=0.3, color=gs_color)
    ax.plot(gs_signal, color=gs_color, linewidth=1, label="Raw")

    # Add detrended version
    t = np.arange(len(gs_signal))
    degree = min(2, max(len(gs_signal) - 1, 0))
    gs_trend = np.polyval(np.polyfit(t, gs_signal, degree), t) if degree >= 1 else np.full_like(gs_signal, np.mean(gs_signal))
    gs_detrended = gs_signal - gs_trend + np.mean(gs_signal)
    ax.plot(gs_detrended, color=gs_detrend_color, linewidth=1, alpha=0.8, label="Detrended")

    ax.set_title("Global Signal", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_xlabel("Volume", fontsize=9)
    ax.set_ylabel("Signal (a.u.)", fontsize=9)
    ax.set_xlim(0, len(gs_signal) - 1)


def _plot_psd_panel(ax: plt.Axes, series: Dict[str, np.ndarray], style_dict: Dict[str, Any]) -> None:
    """
    Plot power spectral density panel.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    series : dict
        Time series data dictionary
    style_dict : dict
        Style configuration
    """
    psd_color = style_dict["psd_color"]

    if "freq" in series and "psd" in series:
        freq = series["freq"]
        psd = series["psd"]
        ax.fill_between(freq, psd, alpha=0.3, color=psd_color)
        ax.plot(freq, psd, color=psd_color, linewidth=1)
        ax.set_title("Power Spectrum (GS)", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax.set_xlabel("Frequency (Hz)", fontsize=9)
        ax.set_ylabel("Power", fontsize=9)
        ax.set_xlim(0, min(0.5, freq[-1]))

        ax.text(
            0.98,
            0.95,
            "PSD diagnostic",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color="gray",
        )
    else:
        ax.text(0.5, 0.5, "PSD not available", ha="center", va="center", fontsize=10, color="gray")
        ax.set_title("Power Spectrum (GS)", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax.axis("off")


def _plot_slice_qc_panels(
    gs: gridspec.GridSpec,
    row_idx: int,
    slice_qc: Dict[str, np.ndarray],
    fig: plt.Figure
) -> None:
    """
    Plot all three slice QC panels in a row.

    Parameters
    ----------
    gs : GridSpec
        GridSpec object for layout
    row_idx : int
        Row index in the gridspec
    slice_qc : dict
        Slice QC metrics dictionary
    fig : Figure
        Matplotlib figure object
    """
    threshold_style = {"color": "gray", "linestyle": "--", "alpha": 0.6, "linewidth": 1}

    # Panel 1: Slice intensity over time
    ax_slice1 = fig.add_subplot(gs[row_idx, 0])
    im_slice = ax_slice1.imshow(
        slice_qc["slice_mean"],
        aspect="auto",
        cmap="viridis",
        interpolation="nearest",
    )
    ax_slice1.set_title("Slice Intensity Over Time", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax_slice1.set_xlabel("Volume", fontsize=9)
    ax_slice1.set_ylabel("Slice", fontsize=9)
    cbar_slice = fig.colorbar(im_slice, ax=ax_slice1, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar_slice.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)

    # Panel 2: Slice temporal variability
    ax_slice2 = fig.add_subplot(gs[row_idx, 1])
    ax_slice2.fill_between(range(len(slice_qc["slice_std"])), slice_qc["slice_std"],
                          alpha=0.3, color=PlotStyle.COLOR_INFO)
    ax_slice2.plot(slice_qc["slice_std"], "o-", markersize=3, color=PlotStyle.COLOR_INFO, linewidth=1)
    ax_slice2.set_title("Slice Temporal Variability", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax_slice2.set_xlabel("Slice", fontsize=9)
    ax_slice2.set_ylabel("Std", fontsize=9)

    if np.any(slice_qc["hyperintense_slices"]):
        hyperintense_idx = np.where(slice_qc["hyperintense_slices"])[0]
        ax_slice2.scatter(
            hyperintense_idx,
            slice_qc["slice_std"][hyperintense_idx],
            color="red", s=50, zorder=5, marker="^",
            label=f"Hyperintense ({len(hyperintense_idx)})",
        )
        ax_slice2.legend(fontsize=PlotStyle.FONT_SMALL)

    # Panel 3: Slice outlier fraction
    ax_slice3 = fig.add_subplot(gs[row_idx, 2])
    ax_slice3.fill_between(range(len(slice_qc["slice_outliers"])),
                          slice_qc["slice_outliers"] * 100, alpha=0.3, color="#f39c12")
    ax_slice3.plot(slice_qc["slice_outliers"] * 100, "o-", markersize=3,
                  color="#f39c12", linewidth=1)
    ax_slice3.set_title("Slice Outlier Fraction", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax_slice3.set_xlabel("Slice", fontsize=9)
    ax_slice3.set_ylabel("Outlier %", fontsize=9)
    ax_slice3.axhline(5.0, **threshold_style, label="5% threshold")
    ax_slice3.legend(fontsize=PlotStyle.FONT_SMALL)


# ============================================================================
# Helper functions for create_carpetplot()
# ============================================================================

def _prepare_carpet_data(data: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """
    Prepare carpet plot data: mask, sort by z-coordinate, and z-score.

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data
    mask : np.ndarray
        3D brain mask

    Returns
    -------
    masked_z : np.ndarray
        Z-scored voxel time series (time, voxels)
    masked_raw : np.ndarray
        Raw voxel time series (time, voxels)
    n_time : int
        Number of time points
    n_voxels : int
        Number of voxels
    """
    masked = data[mask].T  # (time, voxels)
    n_time, n_voxels = masked.shape

    # Sort voxels by z-coordinate
    coords = np.array(np.where(mask)).T
    z_order = np.argsort(coords[:, 2])
    masked_sorted = masked[:, z_order]

    # Z-score the data
    mean_ts = np.mean(masked_sorted, axis=0)
    std_ts = np.std(masked_sorted, axis=0, ddof=1)
    masked_z = (masked_sorted - mean_ts) / (std_ts + 1e-6)

    return masked_z, masked, n_time, n_voxels


def _create_carpet_figure_layout(has_fd: bool, has_dvars: bool) -> Tuple[plt.Figure, gridspec.GridSpec, int]:
    """
    Create figure and grid layout for carpet plot.

    Parameters
    ----------
    has_fd : bool
        Whether FD data is available
    has_dvars : bool
        Whether DVARS data is available

    Returns
    -------
    fig : Figure
        Matplotlib figure
    gs : GridSpec
        Grid layout specification
    n_panels : int
        Number of vertical panels
    """
    n_panels = 4 if has_fd else 3
    height_ratios = [1, 1, 5, 1.5] if has_fd else [1, 5, 1.5]

    fig = plt.figure(figsize=PlotStyle.CARPETPLOT_SIZE)
    gs = gridspec.GridSpec(n_panels, 1, height_ratios=height_ratios, hspace=0.08)

    return fig, gs, n_panels


def _plot_fd_trace(
    ax: plt.Axes,
    fd: np.ndarray,
    info: RunInfo,
    style_dict: Dict[str, Any],
    fd_threshold: float,
) -> None:
    """
    Plot FD time series trace.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    fd : np.ndarray
        Framewise displacement series
    info : RunInfo
        Run information for title
    style_dict : dict
        Style configuration
    """
    fd_color = style_dict["fd_color"]
    threshold_style = style_dict["threshold_style"]

    ax.fill_between(range(len(fd)), fd, alpha=0.3, color=fd_color)
    ax.plot(fd, color=fd_color, linewidth=1, label="FD")
    ax.axhline(fd_threshold, **threshold_style, label=f"Threshold ({fd_threshold:g}mm)")

    # Mark high-motion volumes
    high_motion = fd > fd_threshold
    if np.any(high_motion):
        ax.scatter(
            np.where(high_motion)[0], fd[high_motion],
            color="darkred", s=20, zorder=5, label=f"High motion ({np.sum(high_motion)})"
        )

    ax.set_ylabel("FD (mm)", fontsize=10)
    ax.set_xlim(0, len(fd) - 1)
    ax.set_ylim(0, max(0.5, np.percentile(fd, 99) * 1.1))
    ax.legend(loc="upper right", fontsize=PlotStyle.FONT_SMALL)
    ax.set_xticklabels([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title(
        f"Carpetplot - sub-{info.subject} ses-{info.session} run-{info.run}",
        fontsize=12, fontweight="bold"
    )


def _plot_dvars_outlier_trace(
    ax_dvars: plt.Axes,
    dvars: Optional[np.ndarray],
    outlier_frac: np.ndarray,
    n_time: int,
    info: RunInfo,
    has_fd: bool,
    style_dict: Dict[str, Any]
) -> None:
    """
    Plot DVARS and outlier fraction traces.

    Parameters
    ----------
    ax_dvars : plt.Axes
        Primary axes for DVARS
    dvars : np.ndarray, optional
        DVARS time series
    outlier_frac : np.ndarray
        Outlier fraction per volume
    n_time : int
        Number of time points
    info : RunInfo
        Run information for title
    has_fd : bool
        Whether FD panel exists above
    style_dict : dict
        Style configuration
    """
    dvars_color = style_dict["dvars_color"]
    outlier_color = style_dict["outlier_color"]

    # Plot DVARS if available
    if dvars is not None and len(dvars) > 0:
        dvars_plot = np.concatenate([[np.nan], dvars]) if len(dvars) == n_time - 1 else dvars
        ax_dvars.plot(dvars_plot, color=dvars_color, linewidth=1, label="DVARS")
        ax_dvars.set_ylabel("DVARS", fontsize=10, color=dvars_color)
        ax_dvars.tick_params(axis='y', labelcolor=dvars_color)

    # Add outlier fraction on secondary axis
    ax_outlier = ax_dvars.twinx()
    ax_outlier.fill_between(range(n_time), outlier_frac * 100, alpha=0.3, color=outlier_color)
    ax_outlier.plot(outlier_frac * 100, color=outlier_color, linewidth=1, alpha=0.7, label="Outliers")
    ax_outlier.set_ylabel("Outlier %", fontsize=10, color=outlier_color)
    ax_outlier.tick_params(axis='y', labelcolor=outlier_color)
    ax_outlier.set_ylim(0, max(10, np.percentile(outlier_frac * 100, 99) * 1.2))

    ax_dvars.set_xlim(0, n_time - 1)
    ax_dvars.set_xticklabels([])
    ax_dvars.spines["bottom"].set_visible(False)

    if not has_fd:
        ax_dvars.set_title(
            f"Carpetplot - sub-{info.subject} ses-{info.session} run-{info.run}",
            fontsize=12, fontweight="bold"
        )


def _plot_carpet_main(
    ax: plt.Axes,
    carpet_data: np.ndarray,
    fd: Optional[np.ndarray],
    style_dict: Dict[str, Any],
    fd_threshold: float,
) -> None:
    """
    Plot main carpet visualization.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    carpet_data : np.ndarray
        Z-scored voxel time series (time, voxels)
    fd : np.ndarray, optional
        FD series for marking high-motion volumes
    style_dict : dict
        Style configuration
    """
    # Downsample voxels if necessary
    max_voxels = 5000
    if carpet_data.shape[1] > max_voxels:
        step = carpet_data.shape[1] // max_voxels
        display_data = carpet_data[:, ::step]
    else:
        display_data = carpet_data

    im = ax.imshow(
        display_data.T,
        aspect="auto",
        cmap="RdBu_r",
        vmin=-3,
        vmax=3,
        interpolation="nearest",
    )

    # Add vertical lines for high-motion volumes
    if fd is not None:
        for vol in np.where(fd > fd_threshold)[0]:
            ax.axvline(vol, color="red", alpha=0.3, linewidth=0.5)

    ax.set_ylabel("Voxels (sorted by z)", fontsize=10)
    ax.set_xticklabels([])
    ax.spines["bottom"].set_visible(False)

    # Add colorbar as inset within the carpet plot to avoid width differences
    # with the FD/DVARS panels above
    cax = ax.inset_axes([0.98, 0.1, 0.015, 0.8])  # [x, y, width, height] in axes coords
    cbar = plt.colorbar(im, cax=cax)
    cbar.ax.tick_params(labelsize=7)
    cbar.set_label("Z", fontsize=8)


def _plot_global_signal_trace(
    ax: plt.Axes,
    global_signal: np.ndarray,
    n_time: int,
    style_dict: Dict[str, Any]
) -> None:
    """
    Plot global signal trace with raw and detrended versions.

    Parameters
    ----------
    ax : plt.Axes
        Axes to plot on
    global_signal : np.ndarray
        Global signal time series
    n_time : int
        Number of time points
    style_dict : dict
        Style configuration
    """
    gs_color = style_dict["gs_color"]
    gs_detrend_color = style_dict["gs_detrend_color"]

    # Detrend the signal
    t = np.arange(n_time)
    degree = min(2, max(n_time - 1, 0))
    gs_trend = np.polyval(np.polyfit(t, global_signal, degree), t) if degree >= 1 else np.full_like(global_signal, np.mean(global_signal))
    gs_detrended = global_signal - gs_trend

    ax.plot(global_signal, color=gs_color, linewidth=1, alpha=0.5, label="Raw")
    ax.plot(gs_detrended + np.mean(global_signal), color=gs_detrend_color, linewidth=1, label="Detrended")
    ax.set_ylabel("Global Signal", fontsize=10)
    ax.set_xlabel("Time (volumes)", fontsize=10)
    ax.set_xlim(0, n_time - 1)
    ax.legend(loc="upper right", fontsize=PlotStyle.FONT_SMALL)


def _add_carpet_summary_stats(
    fig: plt.Figure,
    n_voxels: int,
    n_time: int,
    fd: Optional[np.ndarray],
    outlier_frac: np.ndarray,
    fd_threshold: float,
) -> None:
    """
    Add summary statistics text to carpet plot.

    Parameters
    ----------
    fig : Figure
        Matplotlib figure
    n_voxels : int
        Number of voxels
    n_time : int
        Number of time points
    fd : np.ndarray, optional
        FD series
    outlier_frac : np.ndarray
        Outlier fraction per volume
    """
    stats_text = f"Voxels: {n_voxels:,} | Volumes: {n_time}"
    if fd is not None:
        stats_text += f" | Mean FD: {np.mean(fd):.3f}mm"
        stats_text += f" | High motion: {np.sum(fd > fd_threshold)}"
    stats_text += f" | Mean outlier: {np.mean(outlier_frac)*100:.1f}%"

    fig.text(0.5, 0.01, stats_text, ha="center", fontsize=9, style="italic", color="gray")


# ============================================================================
# Public API functions
# ============================================================================

def create_run_figure(
    info: RunInfo,
    maps: Dict[str, np.ndarray],
    series: Dict[str, np.ndarray],
    fd_series: Optional[np.ndarray],
    thresholds: Dict[str, float],
    output_path: Path,
    mask: Optional[np.ndarray] = None,
    slice_qc: Optional[Dict[str, np.ndarray]] = None,
    use_mosaic: bool = True,
) -> Path:
    """
    Create comprehensive QA figure for a single run (CIR-204 enhanced).

    Parameters
    ----------
    info : RunInfo
        Run metadata
    maps : dict
        Dictionary of 3D spatial maps.
    series : dict
        Dictionary of time series (dvars, dvars_std, global_signal, etc.)
    fd_series : np.ndarray or None
        Framewise displacement time series
    thresholds : dict
        Threshold values for flagging
    output_path : Path
        Output file path
    mask : np.ndarray, optional
        Brain mask for overlay
    slice_qc : dict, optional
        Slice-wise QC metrics
    use_mosaic : bool
        If True, show multi-view mosaic; if False, show single axial slice

    Returns
    -------
    Path
        Path to saved figure
    """
    # Setup figure
    n_rows = 4 if slice_qc is not None else 3
    fig = plt.figure(figsize=(PlotStyle.FULL_FIGURE_SIZE[0], 4.5 * n_rows))
    gs = gridspec.GridSpec(n_rows, 3, figure=fig, hspace=PlotStyle.SUBPLOT_SPACING, wspace=PlotStyle.MARGIN_VERTICAL)

    # Build and set title
    title_str = _build_run_summary_title(info, mask, maps, fd_series, thresholds)
    fig.suptitle(title_str, fontsize=PlotStyle.FONT_SUBTITLE, fontweight="bold", y=0.995)

    # Row 1: Primary spatial maps (Mean, Std, tSNR)
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = _display_spatial_map(ax1, maps["mean"], "Mean Intensity", use_mosaic, cmap="gray")
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar1.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    _add_value_annotation(ax1, maps["mean"], mask)

    ax2 = fig.add_subplot(gs[0, 1])
    im2 = _display_spatial_map(ax2, maps["std"], "Temporal Std", use_mosaic, cmap="magma")
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar2.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    _add_value_annotation(ax2, maps["std"], mask)

    ax3 = fig.add_subplot(gs[0, 2])
    im3 = _display_spatial_map(ax3, maps["tsnr"], "tSNR", use_mosaic, cmap="plasma", vmin=0, vmax=150)
    cbar3 = fig.colorbar(im3, ax=ax3, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar3.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    _add_value_annotation(ax3, maps["tsnr"], mask)

    # Row 2: Secondary spatial maps (temporal CoV, low-signal percentile, AR1)
    ax4 = fig.add_subplot(gs[1, 0])
    im4 = _display_spatial_map(ax4, maps["temporal_cov"], "Temporal CoV", use_mosaic, cmap="inferno", vmin=0, vmax=0.2)
    cbar4 = fig.colorbar(im4, ax=ax4, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar4.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    _add_value_annotation(ax4, maps["temporal_cov"], mask)

    ax5 = fig.add_subplot(gs[1, 1])
    im5 = _display_spatial_map(ax5, maps["low_signal"], "Low-Signal Percentile", use_mosaic, cmap="Reds", vmin=0, vmax=1)
    cbar5 = fig.colorbar(im5, ax=ax5, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar5.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    low_signal_pct = np.mean(maps["low_signal"][mask > 0] > 0.5) * 100 if mask is not None else 0
    ax5.text(0.5, -0.02, f"Low-signal voxels: {low_signal_pct:.1f}%", transform=ax5.transAxes,
             fontsize=PlotStyle.FONT_SMALL, ha="center", va="top", color="gray", style="italic")

    ax6 = fig.add_subplot(gs[1, 2])
    im6 = _display_spatial_map(ax6, maps["ar1"], "AR(1) Autocorrelation", use_mosaic, cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    cbar6 = fig.colorbar(im6, ax=ax6, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar6.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    _add_value_annotation(ax6, maps["ar1"], mask)

    # Row 3: Time series panels
    gs_row3 = gridspec.GridSpecFromSubplotSpec(1, 4, subplot_spec=gs[2, :], wspace=0.3)

    # Style configuration
    style_dict = {
        "dvars_color": PlotStyle.COLOR_NEUTRAL,
        "fd_color": PlotStyle.COLOR_WARNING,
        "gs_color": PlotStyle.COLOR_INFO,
        "psd_color": PlotStyle.COLOR_SUCCESS,
        "threshold_style": {"color": "gray", "linestyle": "--", "alpha": 0.6, "linewidth": 1}
    }

    ax_dvars = fig.add_subplot(gs_row3[0])
    _plot_dvars_panel(ax_dvars, series, style_dict)

    ax_fd = fig.add_subplot(gs_row3[1])
    _plot_fd_panel(ax_fd, fd_series, thresholds, style_dict)

    ax_gs = fig.add_subplot(gs_row3[2])
    _plot_global_signal_panel(ax_gs, series["global_signal"], style_dict)

    ax_psd = fig.add_subplot(gs_row3[3])
    _plot_psd_panel(ax_psd, series, style_dict)

    # Row 4: Slice QC (if available)
    if slice_qc is not None:
        _plot_slice_qc_panels(gs, 3, slice_qc, fig)

    fig.savefig(output_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def create_carpetplot(
    data: np.ndarray,
    mask: np.ndarray,
    fd: Optional[np.ndarray],
    output_path: Path,
    info: RunInfo,
    dvars: Optional[np.ndarray] = None,
    thresholds: Optional[Dict[str, float]] = None,
) -> Path:
    """
    Create enhanced carpetplot visualization (CIR-203).

    Features:
    - FD time series with threshold line and high-motion volume markers
    - DVARS time series (if provided)
    - Carpet plot with voxels sorted by z-coordinate
    - Global signal with detrended version
    - Outlier percentage per volume
    - Summary statistics annotation

    Parameters
    ----------
    data : np.ndarray
        4D fMRI data
    mask : np.ndarray
        3D brain mask
    fd : np.ndarray or None
        Framewise displacement series
    output_path : Path
        Output file path
    info : RunInfo
        Run information for title
    dvars : np.ndarray or None
        DVARS series (if available)
    thresholds : dict, optional
        Resolved threshold values for visual annotations.

    Returns
    -------
    Path
        Path to saved figure
    """
    # Prepare data
    masked_z, masked_raw, n_time, n_voxels = _prepare_carpet_data(data, mask)

    # Compute derived metrics
    outlier_frac = np.mean(np.abs(masked_z) > 3.0, axis=1)
    global_signal = np.mean(masked_raw, axis=1)
    fd_threshold = (thresholds or {}).get("fd", 0.3)

    # Create figure layout
    fig, gs, n_panels = _create_carpet_figure_layout(fd is not None, dvars is not None)

    # Style configuration
    style_dict = {
        "fd_color": PlotStyle.COLOR_WARNING,
        "dvars_color": PlotStyle.COLOR_NEUTRAL,
        "gs_color": PlotStyle.COLOR_INFO,
        "gs_detrend_color": PlotStyle.COLOR_SUCCESS,
        "outlier_color": "#f39c12",
        "threshold_style": {"color": "gray", "linestyle": "--", "alpha": 0.5, "linewidth": 1}
    }

    panel_idx = 0

    # Panel 1: FD (if available)
    if fd is not None:
        ax_fd = fig.add_subplot(gs[panel_idx])
        _plot_fd_trace(ax_fd, fd, info, style_dict, fd_threshold)
        panel_idx += 1

    # Panel 2: DVARS / Outlier fraction
    ax_dvars = fig.add_subplot(gs[panel_idx])
    _plot_dvars_outlier_trace(ax_dvars, dvars, outlier_frac, n_time, info, fd is not None, style_dict)
    panel_idx += 1

    # Panel 3: Carpet plot
    ax_carpet = fig.add_subplot(gs[panel_idx])
    _plot_carpet_main(ax_carpet, masked_z, fd, style_dict, fd_threshold)
    panel_idx += 1

    # Panel 4: Global signal
    ax_gs = fig.add_subplot(gs[panel_idx])
    _plot_global_signal_trace(ax_gs, global_signal, n_time, style_dict)

    # Add summary statistics
    _add_carpet_summary_stats(fig, n_voxels, n_time, fd, outlier_frac, fd_threshold)

    fig.savefig(output_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def create_aggregate_maps_figure(
    maps: Dict[str, np.ndarray], output_path: Path, use_mosaic: bool = True
) -> Path:
    """
    Create figure showing aggregate maps.

    Parameters
    ----------
    maps : dict
        Dictionary of 3D numpy arrays with aggregate QA maps.
    output_path : Path
        Where to save the figure
    use_mosaic : bool
        If True, show multi-view mosaic (sagittal, coronal, axial).
        If False, show single axial slice (legacy behavior).

    Returns
    -------
    Path
        Path to saved figure
    """
    if use_mosaic:
        # Multi-view mosaic layout: each map gets its own row with 3 orientations
        fig = plt.figure(figsize=(16, 20))
        fig.suptitle("Aggregate Maps (Sagittal | Coronal | Axial)", fontsize=14, fontweight="bold")

        map_configs = [
            ("mean", "Mean", "viridis", None, None),
            ("tsnr", "tSNR", "plasma", 0, 100),
            ("temporal_cov", "Temporal CoV", "inferno", 0, 0.2),
            ("low_signal", "Low-Signal Percentile", "binary", 0, 1),
            ("ar1", "AR(1)", "coolwarm", -0.5, 0.5),
        ]

        for idx, (key, title, cmap, vmin, vmax) in enumerate(map_configs):
            if key not in maps:
                continue
            ax = fig.add_subplot(len(map_configs), 1, idx + 1)
            im = display_mosaic(ax, maps[key], title, cmap=cmap, vmin=vmin, vmax=vmax, n_slices=5)
            fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02, shrink=0.8)

        fig.tight_layout(rect=[0, 0, 1, 0.97])
    else:
        # Legacy single-slice view
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        fig.suptitle("Aggregate Maps", fontsize=14, fontweight="bold")

        def display(ax, data, title, cmap="viridis"):
            _, _, axial = _mid_slices(data)
            im = ax.imshow(np.rot90(axial), cmap=cmap)
            ax.set_title(title, fontsize=PlotStyle.FONT_LABEL)
            ax.axis("off")
            return im

        im1 = display(axes[0, 0], maps["mean"], "Mean")
        im2 = display(axes[0, 1], maps["tsnr"], "tSNR", cmap="plasma")
        im3 = display(axes[0, 2], maps["temporal_cov"], "Temporal CoV", cmap="inferno")
        im4 = display(axes[1, 0], maps["low_signal"], "Low-Signal", cmap="binary")
        im5 = display(axes[1, 1], maps["ar1"], "AR(1)", cmap="coolwarm")
        axes[1, 2].axis("off")

        for im, ax in zip(
            [im1, im2, im3, im4, im5],
            [axes[0, 0], axes[0, 1], axes[0, 2], axes[1, 0], axes[1, 1]],
        ):
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        fig.tight_layout(rect=[0, 0, 1, 0.95])

    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return output_path


# ============================================================================
# Spatial map generation for flipbook viewer
# ============================================================================

# Default colormap and scale configurations for each map type
SPATIAL_MAP_CONFIGS = {
    'tsnr': {'cmap': 'plasma', 'vmin': 0, 'vmax': 150, 'label': 'tSNR'},
    'mean': {'cmap': 'gray', 'vmin': None, 'vmax': None, 'label': 'Mean'},
    'std': {'cmap': 'magma', 'vmin': None, 'vmax': None, 'label': 'Std Dev'},
    'temporal_cov': {'cmap': 'inferno', 'vmin': 0, 'vmax': 0.2, 'label': 'Temporal CoV'},
    'low_signal': {'cmap': 'Reds', 'vmin': 0, 'vmax': 1, 'label': 'Low-Signal Percentile'},
    'ar1': {'cmap': 'RdBu_r', 'vmin': -0.5, 'vmax': 0.5, 'label': 'AR(1)'},
}


def create_spatial_map_image(
    data: np.ndarray,
    output_path: Path,
    map_type: str = 'tsnr',
    mask: Optional[np.ndarray] = None,
    n_slices: int = 5,
    figsize: Tuple[float, float] = (8, 6),
    show_colorbar: bool = True,
) -> Path:
    """
    Create a multi-slice spatial map image for flipbook viewing.

    Generates a figure with sagittal, coronal, and axial views showing
    multiple slices for a single metric map.

    Parameters
    ----------
    data : np.ndarray
        3D volume to display
    output_path : Path
        Output file path for the image
    map_type : str
        Type of map ('tsnr', 'mean', 'std', 'temporal_cov', 'low_signal', 'ar1')
        Used to determine colormap and scaling
    mask : np.ndarray, optional
        Brain mask for masking non-brain regions
    n_slices : int
        Number of slices per orientation (default: 5)
    figsize : tuple
        Figure size (width, height) in inches
    show_colorbar : bool
        Whether to show colorbar

    Returns
    -------
    Path
        Path to saved figure
    """
    # Get configuration for this map type
    config = SPATIAL_MAP_CONFIGS.get(map_type, SPATIAL_MAP_CONFIGS['mean'])
    cmap = config['cmap']
    vmin = config['vmin']
    vmax = config['vmax']
    label = config['label']

    # Auto-scale if not specified
    valid_data = data[mask > 0] if mask is not None else data[data != 0]
    if len(valid_data) > 0:
        if vmin is None:
            vmin = np.percentile(valid_data, 2)
        if vmax is None:
            vmax = np.percentile(valid_data, 98)

    # Get slices
    slices = _multi_view_slices(data, n_slices)

    # Create figure: 3 rows for orientations
    fig, axes = plt.subplots(3, n_slices, figsize=figsize)

    orientation_labels = ['Sagittal', 'Coronal', 'Axial']
    orientation_keys = ['sagittal', 'coronal', 'axial']

    for row, (orientation, key) in enumerate(zip(orientation_labels, orientation_keys)):
        for col, slice_img in enumerate(slices[key]):
            ax = axes[row, col]
            rotated = np.rot90(slice_img)
            im = ax.imshow(rotated, cmap=cmap, vmin=vmin, vmax=vmax, aspect='auto')
            ax.axis('off')

            # Add orientation label on first column
            if col == 0:
                ax.set_ylabel(orientation, fontsize=10, fontweight='bold')
                ax.yaxis.set_visible(True)
                ax.set_yticks([])

    # Add title
    fig.suptitle(label, fontsize=12, fontweight='bold', y=0.98)

    # Adjust spacing
    fig.subplots_adjust(left=0.05, right=0.88 if show_colorbar else 0.98,
                        bottom=0.02, top=0.92, wspace=0.05, hspace=0.15)

    # Add colorbar
    if show_colorbar:
        cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.7])
        cbar = fig.colorbar(im, cax=cbar_ax)
        cbar.ax.tick_params(labelsize=8)

    fig.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return output_path


def create_run_spatial_maps(
    maps: Dict[str, np.ndarray],
    output_dir: Path,
    run_prefix: str,
    mask: Optional[np.ndarray] = None,
    n_slices: int = 5,
) -> Dict[str, Path]:
    """
    Generate all spatial map images for a run for the flipbook viewer.

    Creates separate image files for each available map type that can be loaded
    into the flipbook viewer.

    Parameters
    ----------
    maps : dict
        Dictionary of 3D numpy arrays with keys like 'tsnr', 'mean', 'std',
        'temporal_cov', 'low_signal', 'ar1'
    output_dir : Path
        Directory to save the images
    run_prefix : str
        Prefix for output filenames (e.g., 'sub-01_ses-01_run-01')
    mask : np.ndarray, optional
        Brain mask for masking
    n_slices : int
        Number of slices per orientation

    Returns
    -------
    dict
        Dictionary mapping map type keys to output file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    spatial_map_paths = {}

    # Generate images for each available map type
    for map_key in ['tsnr', 'std', 'temporal_cov', 'low_signal', 'ar1']:
        if map_key not in maps:
            continue

        output_path = output_dir / f"{run_prefix}_map_{map_key}.png"
        create_spatial_map_image(
            data=maps[map_key],
            output_path=output_path,
            map_type=map_key,
            mask=mask,
            n_slices=n_slices,
        )
        spatial_map_paths[map_key] = output_path

    return spatial_map_paths


def create_mean_mask_overlay(
    mean_img: np.ndarray,
    mask: np.ndarray,
    output_path: Path,
    n_slices: int = 5,
    figsize: Tuple[float, float] = (8, 6),
) -> Path:
    """
    Create a mean image with mask overlay for flipbook 'Mean + Mask' view.

    Shows the mean BOLD image with the brain mask overlaid as a semi-transparent
    color and contour to visualize coverage.

    Parameters
    ----------
    mean_img : np.ndarray
        3D mean BOLD volume
    mask : np.ndarray
        3D brain mask
    output_path : Path
        Output file path
    n_slices : int
        Number of slices per orientation
    figsize : tuple
        Figure size

    Returns
    -------
    Path
        Path to saved figure
    """
    slices = _multi_view_slices(mean_img, n_slices)
    mask_slices = _multi_view_slices(mask.astype(float), n_slices)

    fig, axes = plt.subplots(3, n_slices, figsize=figsize)

    orientation_labels = ['Sagittal', 'Coronal', 'Axial']
    orientation_keys = ['sagittal', 'coronal', 'axial']

    for row, (orientation, key) in enumerate(zip(orientation_labels, orientation_keys)):
        for col in range(n_slices):
            ax = axes[row, col]
            img_slice = np.rot90(slices[key][col])
            mask_slice = np.rot90(mask_slices[key][col])

            # Show mean image
            ax.imshow(img_slice, cmap='gray', interpolation='nearest')

            # Overlay mask as semi-transparent
            ax.imshow(
                np.ma.masked_where(mask_slice == 0, mask_slice),
                cmap='spring', alpha=0.25, interpolation='nearest'
            )

            # Add mask contour
            try:
                ax.contour(mask_slice, levels=[0.5], colors='magenta', linewidths=0.7)
            except Exception:
                pass

            ax.axis('off')

            if col == 0:
                ax.set_ylabel(orientation, fontsize=10, fontweight='bold')
                ax.yaxis.set_visible(True)
                ax.set_yticks([])

    fig.suptitle('Mean + Mask', fontsize=12, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    fig.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='white')
    plt.close(fig)

    return output_path


def create_subject_comparison_plot(
    study: StudyResults,
    metric_key: str,
    output_path: Path,
    title: str,
    ylabel: str,
) -> Path:
    """Create a violin plot comparing a metric across subjects."""
    data_per_subject = []
    subject_labels = []

    # Collect data
    for subject in study.subjects:
        subject_vals = []
        for session in subject.sessions:
            for run in session.runs:
                val = run.metrics.get(metric_key)
                # Try with _median suffix if direct match fails
                if val is None:
                    val = run.metrics.get(f"{metric_key}_median")

                if is_finite_number(val):
                    subject_vals.append(float(val))

        if subject_vals:
            data_per_subject.append(subject_vals)
            subject_labels.append(subject.subject)

    if not data_per_subject:
        return None

    fig, ax = plt.subplots(figsize=(max(10, len(subject_labels) * 0.8), 6))

    # Create violin plot
    parts = ax.violinplot(data_per_subject, showmeans=False, showmedians=True)

    # Customize styling
    for pc in parts['bodies']:
        pc.set_facecolor('#0f3460')
        pc.set_edgecolor('black')
        pc.set_alpha(0.7)

    # Add individual points with jitter
    for i, vals in enumerate(data_per_subject):
        jitter = np.random.normal(0, 0.04, size=len(vals))
        ax.scatter(np.array([i + 1] * len(vals)) + jitter, vals, alpha=0.5, s=15, color=PlotStyle.COLOR_WARNING, zorder=3)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_xticks(np.arange(1, len(subject_labels) + 1))
    ax.set_xticklabels(subject_labels, rotation=45, ha='right')
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    # Adjust layout
    fig.tight_layout()
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    return output_path
