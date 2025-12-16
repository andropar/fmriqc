"""Visualization functions for QA reports."""

import base64
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np

from .constants import PlotStyle, MotionConstants
from .structures import RunInfo, StudyResults


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
    if mask is not None:
        mask_slices = _multi_view_slices(mask.astype(float), n_slices)

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
    figsize: Tuple[float, float] = (4.5, 1.8),
) -> Path:
    """
    Create a compact 3-view thumbnail (sagittal/coronal/axial) of mean BOLD with mask overlay.
    Mask is shown as semi-transparent fill plus contour so holes are visible.
    """
    mask_bool = mask.astype(bool)
    cx, cy, cz = _center_slices_from_mask(mask_bool)

    slices = [
        (mean_img[cx, :, :], mask_bool[cx, :, :], "Sagittal"),
        (mean_img[:, cy, :], mask_bool[:, cy, :], "Coronal"),
        (mean_img[:, :, cz], mask_bool[:, :, cz], "Axial"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=figsize, constrained_layout=True)
    for ax, (img_slice, mask_slice, title) in zip(axes, slices):
        _plot_slice_with_mask(ax, img_slice, mask_slice, title)

    fig.savefig(output_path, dpi=100)
    plt.close(fig)
    return output_path


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
        Dictionary of 3D spatial maps (mean, std, tsnr, cov, dropout, ar1)
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
    n_rows = 4 if slice_qc is not None else 3

    # Larger figure for better detail
    fig = plt.figure(figsize=(PlotStyle.FULL_FIGURE_SIZE[0], 4.5 * n_rows))
    gs = gridspec.GridSpec(n_rows, 3, figure=fig, hspace=PlotStyle.SUBPLOT_SPACING, wspace=PlotStyle.MARGIN_VERTICAL)

    # Build summary stats string for title
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

    fig.suptitle(title_str, fontsize=PlotStyle.FONT_SUBTITLE, fontweight="bold", y=0.995)

    def display_map(ax, data, title, cmap="viridis", vmin=None, vmax=None):
        """Display a spatial map with optional mosaic or single slice."""
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

    def add_value_annotation(ax, data, mask_arr=None, unit=""):
        """Add min/median/max annotation below plot."""
        if mask_arr is not None:
            vals = data[mask_arr > 0]
        else:
            vals = data[data != 0] if np.any(data != 0) else data.ravel()
        if len(vals) > 0:
            med = np.median(vals)
            mn, mx = np.min(vals), np.max(vals)
            text = f"min:{mn:.1f} med:{med:.1f} max:{mx:.1f}{unit}"
            ax.text(0.5, -0.02, text, transform=ax.transAxes, fontsize=PlotStyle.FONT_SMALL,
                    ha="center", va="top", color="gray", style="italic")

    # Row 1: Primary spatial maps (Mean, Std, tSNR)
    ax1 = fig.add_subplot(gs[0, 0])
    im1 = display_map(ax1, maps["mean"], "Mean Intensity", cmap="gray")
    cbar1 = fig.colorbar(im1, ax=ax1, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar1.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    add_value_annotation(ax1, maps["mean"], mask)

    ax2 = fig.add_subplot(gs[0, 1])
    im2 = display_map(ax2, maps["std"], "Temporal Std", cmap="magma")
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar2.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    add_value_annotation(ax2, maps["std"], mask)

    ax3 = fig.add_subplot(gs[0, 2])
    im3 = display_map(ax3, maps["tsnr"], "tSNR", cmap="plasma", vmin=0, vmax=150)
    cbar3 = fig.colorbar(im3, ax=ax3, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar3.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    add_value_annotation(ax3, maps["tsnr"], mask)

    # Row 2: Secondary spatial maps (CoV, Dropout, AR1)
    ax4 = fig.add_subplot(gs[1, 0])
    im4 = display_map(ax4, maps["cov"], "Coefficient of Variation", cmap="inferno", vmin=0, vmax=0.2)
    cbar4 = fig.colorbar(im4, ax=ax4, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar4.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    add_value_annotation(ax4, maps["cov"], mask)

    ax5 = fig.add_subplot(gs[1, 1])
    im5 = display_map(ax5, maps["dropout"], "Signal Dropout", cmap="Reds", vmin=0, vmax=1)
    cbar5 = fig.colorbar(im5, ax=ax5, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar5.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    dropout_pct = np.mean(maps["dropout"][mask > 0] > 0.5) * 100 if mask is not None else 0
    ax5.text(0.5, -0.02, f"Dropout voxels: {dropout_pct:.1f}%", transform=ax5.transAxes,
             fontsize=PlotStyle.FONT_SMALL, ha="center", va="top", color="gray", style="italic")

    ax6 = fig.add_subplot(gs[1, 2])
    im6 = display_map(ax6, maps["ar1"], "AR(1) Autocorrelation", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    cbar6 = fig.colorbar(im6, ax=ax6, fraction=PlotStyle.MARGIN_HORIZONTAL, pad=0.02)
    cbar6.ax.tick_params(labelsize=PlotStyle.FONT_SMALL)
    add_value_annotation(ax6, maps["ar1"], mask)

    # Row 3: Time series panels
    gs_row3 = gridspec.GridSpecFromSubplotSpec(1, 4, subplot_spec=gs[2, :], wspace=0.3)

    # Color scheme
    dvars_color = PlotStyle.COLOR_NEUTRAL
    fd_color = PlotStyle.COLOR_WARNING
    gs_color = PlotStyle.COLOR_INFO
    psd_color = PlotStyle.COLOR_SUCCESS
    threshold_style = {"color": "gray", "linestyle": "--", "alpha": 0.6, "linewidth": 1}

    # DVARS panel
    ax_dvars = fig.add_subplot(gs_row3[0])
    time = np.arange(series["dvars"].shape[0])
    valid_time = time[1:]

    # Plot standardized DVARS
    if "dvars_std" in series:
        dvars_vals = series["dvars_std"][1:]
        ax_dvars.fill_between(valid_time, dvars_vals, alpha=0.3, color=dvars_color)
        ax_dvars.plot(valid_time, dvars_vals, color=dvars_color, linewidth=1, label="DVARS (std)")

        # Shade high DVARS volumes
        dvars_thresh = series.get("dvars_threshold", 2.5)
        high_dvars = dvars_vals > dvars_thresh
        if np.any(high_dvars):
            ax_dvars.fill_between(valid_time, 0, dvars_vals, where=high_dvars,
                                  alpha=0.4, color="red", label=f">{dvars_thresh:.1f}")
    else:
        ax_dvars.plot(valid_time, series["dvars"][1:], color=dvars_color, linewidth=1, label="DVARS")

    dvars_thresh = series.get("dvars_threshold", 2.5)
    ax_dvars.axhline(dvars_thresh, **threshold_style, label=f"Thresh ({dvars_thresh:.1f})")
    ax_dvars.set_title("DVARS", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax_dvars.legend(fontsize=7, loc="upper right")
    ax_dvars.set_xlabel("Volume", fontsize=9)
    ax_dvars.set_ylabel("DVARS (std)", fontsize=9)
    ax_dvars.set_xlim(0, len(time) - 1)

    # FD panel
    ax_fd = fig.add_subplot(gs_row3[1])
    if fd_series is not None:
        ax_fd.fill_between(range(len(fd_series)), fd_series, alpha=0.3, color=fd_color)
        ax_fd.plot(fd_series, color=fd_color, linewidth=1, label="FD")

        fd_thresh = thresholds.get("fd", 0.2)
        ax_fd.axhline(fd_thresh, **threshold_style, label=f"Thresh ({fd_thresh}mm)")

        # Shade high-motion volumes
        high_motion = fd_series > fd_thresh
        if np.any(high_motion):
            ax_fd.fill_between(range(len(fd_series)), 0, fd_series, where=high_motion,
                               alpha=0.4, color="darkred", label=f"High ({np.sum(high_motion)})")

        ax_fd.set_title("Framewise Displacement", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax_fd.legend(fontsize=7, loc="upper right")
        ax_fd.set_xlabel("Volume", fontsize=9)
        ax_fd.set_ylabel("FD (mm)", fontsize=9)
        ax_fd.set_xlim(0, len(fd_series) - 1)
        ax_fd.set_ylim(0, max(0.5, np.percentile(fd_series, 99) * 1.1))
    else:
        ax_fd.text(0.5, 0.5, "FD not available", ha="center", va="center", fontsize=10, color="gray")
        ax_fd.set_title("Framewise Displacement", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax_fd.axis("off")

    # Global Signal panel
    ax_gs = fig.add_subplot(gs_row3[2])
    gs_sig = series["global_signal"]
    ax_gs.fill_between(range(len(gs_sig)), gs_sig, alpha=0.3, color=gs_color)
    ax_gs.plot(gs_sig, color=gs_color, linewidth=1, label="Raw")

    # Add detrended version
    t = np.arange(len(gs_sig))
    gs_trend = np.polyval(np.polyfit(t, gs_sig, 2), t)
    gs_detrended = gs_sig - gs_trend + np.mean(gs_sig)
    ax_gs.plot(gs_detrended, color=PlotStyle.COLOR_SUCCESS, linewidth=1, alpha=0.8, label="Detrended")

    ax_gs.set_title("Global Signal", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
    ax_gs.legend(fontsize=7, loc="upper right")
    ax_gs.set_xlabel("Volume", fontsize=9)
    ax_gs.set_ylabel("Signal (a.u.)", fontsize=9)
    ax_gs.set_xlim(0, len(gs_sig) - 1)

    # PSD panel
    ax_psd = fig.add_subplot(gs_row3[3])
    if "freq" in series and "psd" in series:
        freq = series["freq"]
        psd = series["psd"]
        ax_psd.fill_between(freq, psd, alpha=0.3, color=psd_color)
        ax_psd.plot(freq, psd, color=psd_color, linewidth=1)
        ax_psd.set_title("Power Spectrum (GS)", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax_psd.set_xlabel("Frequency (Hz)", fontsize=9)
        ax_psd.set_ylabel("Power", fontsize=9)
        ax_psd.set_xlim(0, min(0.5, freq[-1]))

        # Shade physiological bands
        ax_psd.axvspan(0.15, 0.4, alpha=0.15, color="blue", label="Respiratory")
        ax_psd.axvspan(0.8, 1.5, alpha=0.15, color="red", label="Cardiac")
        ax_psd.legend(fontsize=7, loc="upper right")
    else:
        ax_psd.text(0.5, 0.5, "PSD not available", ha="center", va="center", fontsize=10, color="gray")
        ax_psd.set_title("Power Spectrum (GS)", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax_psd.axis("off")

    # Row 4: Slice QC (if available)
    if slice_qc is not None:
        ax_slice1 = fig.add_subplot(gs[3, 0])
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

        ax_slice2 = fig.add_subplot(gs[3, 1])
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

        ax_slice3 = fig.add_subplot(gs[3, 2])
        ax_slice3.fill_between(range(len(slice_qc["slice_outliers"])),
                               slice_qc["slice_outliers"] * 100, alpha=0.3, color="#f39c12")
        ax_slice3.plot(slice_qc["slice_outliers"] * 100, "o-", markersize=3,
                       color="#f39c12", linewidth=1)
        ax_slice3.set_title("Slice Outlier Fraction", fontsize=PlotStyle.FONT_LABEL, fontweight="bold")
        ax_slice3.set_xlabel("Slice", fontsize=9)
        ax_slice3.set_ylabel("Outlier %", fontsize=9)
        ax_slice3.axhline(5.0, **threshold_style, label="5% threshold")
        ax_slice3.legend(fontsize=PlotStyle.FONT_SMALL)

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

    Returns
    -------
    Path
        Path to saved figure
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

    # Compute outlier fraction per volume
    outlier_frac = np.mean(np.abs(masked_z) > 3.0, axis=1)

    # Global signal and detrended version
    global_signal = np.mean(masked, axis=1)
    t = np.arange(n_time)
    gs_trend = np.polyval(np.polyfit(t, global_signal, 2), t)
    gs_detrended = global_signal - gs_trend

    # Figure setup with improved layout
    n_panels = 4 if fd is not None else 3
    height_ratios = [1, 1, 5, 1.5] if fd is not None else [1, 5, 1.5]

    fig = plt.figure(figsize=PlotStyle.CARPETPLOT_SIZE)
    gs = gridspec.GridSpec(n_panels, 1, height_ratios=height_ratios, hspace=0.08)

    # Style constants
    fd_color = PlotStyle.COLOR_WARNING
    dvars_color = PlotStyle.COLOR_NEUTRAL
    gs_color = PlotStyle.COLOR_INFO
    gs_detrend_color = PlotStyle.COLOR_SUCCESS
    outlier_color = "#f39c12"
    threshold_style = {"color": "gray", "linestyle": "--", "alpha": 0.5, "linewidth": 1}

    panel_idx = 0

    # Panel 1: FD (if available)
    if fd is not None:
        ax_fd = fig.add_subplot(gs[panel_idx])
        ax_fd.fill_between(range(len(fd)), fd, alpha=0.3, color=fd_color)
        ax_fd.plot(fd, color=fd_color, linewidth=1, label="FD")
        ax_fd.axhline(0.2, **threshold_style, label="Threshold (0.2mm)")

        # Mark high-motion volumes
        high_motion = fd > 0.5
        if np.any(high_motion):
            ax_fd.scatter(
                np.where(high_motion)[0], fd[high_motion],
                color="darkred", s=20, zorder=5, label=f"High motion ({np.sum(high_motion)})"
            )

        ax_fd.set_ylabel("FD (mm)", fontsize=10)
        ax_fd.set_xlim(0, len(fd) - 1)
        ax_fd.set_ylim(0, max(0.5, np.percentile(fd, 99) * 1.1))
        ax_fd.legend(loc="upper right", fontsize=PlotStyle.FONT_SMALL)
        ax_fd.set_xticklabels([])
        ax_fd.spines["bottom"].set_visible(False)
        ax_fd.set_title(
            f"Carpetplot - sub-{info.subject} ses-{info.session} run-{info.run}",
            fontsize=12, fontweight="bold"
        )
        panel_idx += 1

    # Panel 2: DVARS / Outlier fraction
    ax_dvars = fig.add_subplot(gs[panel_idx])
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
    if fd is None:
        ax_dvars.set_title(
            f"Carpetplot - sub-{info.subject} ses-{info.session} run-{info.run}",
            fontsize=12, fontweight="bold"
        )
    panel_idx += 1

    # Panel 3: Carpet plot
    ax_carpet = fig.add_subplot(gs[panel_idx])

    # Downsample voxels if necessary
    max_voxels = 5000
    if masked_z.shape[1] > max_voxels:
        step = masked_z.shape[1] // max_voxels
        display_data = masked_z[:, ::step]
    else:
        display_data = masked_z

    im = ax_carpet.imshow(
        display_data.T,
        aspect="auto",
        cmap="RdBu_r",  # Better colormap for deviations
        vmin=-3,
        vmax=3,
        interpolation="nearest",
    )

    # Add vertical lines for high-motion volumes
    if fd is not None:
        for vol in np.where(fd > 0.5)[0]:
            ax_carpet.axvline(vol, color="red", alpha=0.3, linewidth=0.5)

    ax_carpet.set_ylabel("Voxels (sorted by z)", fontsize=10)
    ax_carpet.set_xticklabels([])
    ax_carpet.spines["bottom"].set_visible(False)

    # Colorbar
    cbar = plt.colorbar(im, ax=ax_carpet, fraction=0.015, pad=0.01)
    cbar.set_label("Z-score", fontsize=9)
    panel_idx += 1

    # Panel 4: Global signal
    ax_gs = fig.add_subplot(gs[panel_idx])
    ax_gs.plot(global_signal, color=gs_color, linewidth=1, alpha=0.5, label="Raw")
    ax_gs.plot(gs_detrended + np.mean(global_signal), color=gs_detrend_color, linewidth=1, label="Detrended")
    ax_gs.set_ylabel("Global Signal", fontsize=10)
    ax_gs.set_xlabel("Time (volumes)", fontsize=10)
    ax_gs.set_xlim(0, n_time - 1)
    ax_gs.legend(loc="upper right", fontsize=PlotStyle.FONT_SMALL)

    # Add summary statistics as text annotation
    stats_text = f"Voxels: {n_voxels:,} | Volumes: {n_time}"
    if fd is not None:
        stats_text += f" | Mean FD: {np.mean(fd):.3f}mm"
        stats_text += f" | High motion: {np.sum(fd > 0.5)}"
    stats_text += f" | Mean outlier: {np.mean(outlier_frac)*100:.1f}%"

    fig.text(0.5, 0.01, stats_text, ha="center", fontsize=9, style="italic", color="gray")

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
        Dictionary of 3D numpy arrays with keys 'mean', 'tsnr', 'cov', 'dropout', 'ar1'
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
            ("cov", "CoV", "inferno", 0, 0.2),
            ("dropout", "Dropout", "binary", 0, 1),
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
        im3 = display(axes[0, 2], maps["cov"], "CoV", cmap="inferno")
        im4 = display(axes[1, 0], maps["dropout"], "Dropout", cmap="binary")
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

                if val is not None and not np.isnan(val):
                    subject_vals.append(val)

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
