/**
 * Flipbook brain viewer for spatial maps
 */

let currentRunId = null;

/**
 * Open the detail modal for a specific run
 */
function openRunDetail(runId) {
    currentRunId = runId;
    const runs = subjectData.runs;
    const run = runs.find(r => r.id === runId);
    if (!run) return;

    // Update modal title
    document.getElementById('detail-modal-title').textContent = run.id;

    // Update nav button state
    const currentIndex = runs.findIndex(r => r.id === runId);
    updateNavButtonState(currentIndex, runs.length);

    // Update review buttons
    updateReviewButtons(runId);

    // Update metrics grid
    updateDetailMetrics(run);
    updateDetailProvenance(run);

    // Update overview figure
    updateRunFigure(run);

    // Update flipbook
    initFlipbook(run);

    // Update carpet plot
    updateCarpetPlot(run);

    // Update notes
    updateNotes(runId);

    // Show modal
    openModal('detail-modal');
}

/**
 * Update the metrics display in detail modal
 */
function updateDetailMetrics(run) {
    const grid = document.getElementById('detail-metrics-grid');
    if (!grid) return;

    grid.innerHTML = '';

    const metricsToShow = ['tsnr_median', 'fd_median', 'dvars_std_median', 'coverage_signal_fraction', 'gcor', 'apparent_smoothness_fwhm'];

    metricsToShow.forEach(key => {
        const value = run.metrics[key];
        if (value == null) return;

        const metricInfo = subjectData.metricInfo[key] || { label: key };

        // Check if this metric has a related flag
        let isFlagged = false;
        if (run.flags) {
            if (key === 'tsnr_median' && run.flags.tsnr_low) isFlagged = true;
            if (key === 'fd_median' && run.flags.motion_high) isFlagged = true;
            if (key === 'dvars_std_median' && run.flags.dvars_high) isFlagged = true;
        }

        const item = document.createElement('div');
        item.className = 'detail-item' + (isFlagged ? ' flagged' : '');
        item.innerHTML = `
            <div class="label">${metricInfo.label}</div>
            <div class="value">${value.toFixed(3)}</div>
        `;
        grid.appendChild(item);
    });

    // Show active flags
    if (run.flags) {
        const activeFlags = Object.entries(run.flags).filter(([k, v]) => v);
        if (activeFlags.length > 0) {
            const flagsDiv = document.createElement('div');
            flagsDiv.className = 'detail-item flagged';
            flagsDiv.style.gridColumn = '1 / -1';
            flagsDiv.innerHTML = `
                <div class="label">Quality Flags</div>
                <div class="value">${activeFlags.map(([k]) => k.replace(/_/g, ' ')).join(', ')}</div>
            `;
            grid.appendChild(flagsDiv);
        }
    }
}

function updateDetailProvenance(run) {
    const grid = document.getElementById('detail-provenance-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const provenance = run.provenance || {};
    const maskInfo = provenance.mask_info || {};
    const motionInfo = provenance.motion_info || {};
    const rows = [
        ['BOLD', provenance.bold_path || ''],
        ['Mask source', maskInfo.source || 'missing'],
        ['Mask path', maskInfo.path || ''],
        ['Mask resampled', maskInfo.resampled ? 'yes' : 'no'],
        ['Motion source', motionInfo.source || 'missing'],
        ['Motion path', motionInfo.path || ''],
        ['Motion diagnostic', motionInfo.diagnostic_only ? 'yes' : 'no'],
        ['Warnings', (run.warnings || []).join('; ')]
    ];

    rows.forEach(([label, value]) => {
        const item = document.createElement('div');
        item.className = 'detail-item';
        item.innerHTML = `<div class="label">${label}</div><div class="value">${value || '-'}</div>`;
        grid.appendChild(item);
    });
}

/**
 * Show or hide an image panel with an empty state.
 */
function updateImageWithEmptyState(imageId, emptyId, imagePath, altText) {
    const img = document.getElementById(imageId);
    const empty = document.getElementById(emptyId);
    if (!img) return;

    if (imagePath) {
        img.src = imagePath;
        img.alt = altText || '';
        img.style.display = 'block';
        if (empty) empty.style.display = 'none';
    } else {
        img.removeAttribute('src');
        img.alt = altText || '';
        img.style.display = 'none';
        if (empty) empty.style.display = 'flex';
    }
}

/**
 * Update the run overview figure.
 */
function updateRunFigure(run) {
    updateImageWithEmptyState(
        'run-figure-image',
        'run-figure-empty',
        run.figurePath,
        `${run.id} overview figure`
    );
}

/**
 * Initialize the flipbook viewer for a run
 */
function initFlipbook(run) {
    const container = document.getElementById('flipbook-container');
    const buttons = document.getElementById('flipbook-buttons');
    if (!container || !buttons) return;

    // Available maps
    const maps = [
        { key: 'mean_mask', label: 'Mean + Mask', default: true },
        { key: 'tsnr', label: 'tSNR' },
        { key: 'std', label: 'Std Dev' },
        { key: 'temporal_cov', label: 'Temporal CoV' },
        { key: 'low_signal', label: 'Low Signal' },
        { key: 'ar1', label: 'AR1' }
    ].filter(map => run.spatialMaps?.[map.key]);

    // Create buttons
    buttons.innerHTML = '';
    updateImageWithEmptyState('flipbook-image', 'flipbook-empty', null, 'Brain map');

    if (maps.length === 0) {
        buttons.style.display = 'none';
        return;
    }

    buttons.style.display = 'flex';
    maps.forEach(map => {
        const btn = document.createElement('button');
        btn.className = 'flipbook-btn' + (map.default ? ' active' : '');
        btn.textContent = map.label;
        btn.dataset.map = map.key;
        btn.onclick = () => switchFlipbookMap(run, map.key);
        buttons.appendChild(btn);
    });

    // Show default map
    const defaultMap = maps.find(m => m.default) || maps[0];
    if (defaultMap) switchFlipbookMap(run, defaultMap.key);
}

/**
 * Switch the displayed map in the flipbook
 */
function switchFlipbookMap(run, mapKey) {
    // Update button states
    document.querySelectorAll('.flipbook-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.map === mapKey);
    });

    // Update image
    const img = document.getElementById('flipbook-image');
    if (!img) return;

    // Get the appropriate image path from spatialMaps
    let imagePath = run.spatialMaps?.[mapKey];

    if (imagePath) {
        updateImageWithEmptyState('flipbook-image', 'flipbook-empty', imagePath, mapKey);
    } else {
        updateImageWithEmptyState('flipbook-image', 'flipbook-empty', null, `${mapKey} not available`);
    }
}

/**
 * Update carpet plot display
 */
function updateCarpetPlot(run) {
    updateImageWithEmptyState(
        'carpet-image',
        'carpet-empty',
        run.carpetPath,
        `${run.id} carpet plot`
    );
}

/**
 * Update notes textarea for current run
 */
function updateNotes(runId) {
    const textarea = document.getElementById('run-notes');
    if (!textarea) return;

    const reviews = getReviews();
    const review = reviews[runId] || {};
    textarea.value = review.note || '';
}

/**
 * Save notes for current run
 */
function saveNotes() {
    if (!currentRunId) return;

    const textarea = document.getElementById('run-notes');
    if (!textarea) return;

    const reviews = getReviews();
    if (!reviews[currentRunId]) {
        reviews[currentRunId] = {};
    }
    reviews[currentRunId].note = textarea.value;
    reviews[currentRunId].updated_at = new Date().toISOString();

    saveReviews(reviews);
    updateNoteIndicators();
}

// Auto-save notes on blur
document.addEventListener('DOMContentLoaded', function() {
    const textarea = document.getElementById('run-notes');
    if (textarea) {
        textarea.addEventListener('blur', saveNotes);
    }
});

/**
 * Navigate to previous/next run in modal
 */
function navigateRunModal(direction) {
    if (!currentRunId || !subjectData || !subjectData.runs) return;
    saveNotes();

    const runs = subjectData.runs;
    const currentIndex = runs.findIndex(r => r.id === currentRunId);
    if (currentIndex === -1) return;

    const newIndex = currentIndex + direction;
    if (newIndex >= 0 && newIndex < runs.length) {
        openRunDetail(runs[newIndex].id);
        updateNavButtonState(newIndex, runs.length);
    }
}

/**
 * Update nav button disabled state
 */
function updateNavButtonState(index, total) {
    const buttons = document.querySelectorAll('.run-nav-buttons .run-nav-btn');
    if (buttons.length >= 2) {
        buttons[0].disabled = index <= 0;
        buttons[1].disabled = index >= total - 1;
    }
}

// Keyboard navigation for modal
document.addEventListener('keydown', function(e) {
    // Check if modal is open
    const modal = document.getElementById('detail-modal');
    if (!modal || !modal.classList.contains('active')) return;

    // Don't capture if typing in input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

    if (e.key === 'ArrowLeft') {
        e.preventDefault();
        navigateRunModal(-1);
    } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        navigateRunModal(1);
    } else if (e.key === 'Escape') {
        e.preventDefault();
        closeModal('detail-modal');
    }
});

// Export
window.openRunDetail = openRunDetail;
window.switchFlipbookMap = switchFlipbookMap;
window.saveNotes = saveNotes;
window.navigateRunModal = navigateRunModal;
