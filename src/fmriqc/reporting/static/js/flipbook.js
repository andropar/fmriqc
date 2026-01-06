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

    const metricsToShow = ['tsnr_median', 'fd_median', 'dvars_std_median', 'coverage', 'gcor', 'smoothness_fwhm'];

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
        { key: 'cov', label: 'CoV' },
        { key: 'dropout', label: 'Dropout' },
        { key: 'ar1', label: 'AR1' }
    ];

    // Create buttons
    buttons.innerHTML = '';
    maps.forEach(map => {
        const btn = document.createElement('button');
        btn.className = 'flipbook-btn' + (map.default ? ' active' : '');
        btn.textContent = map.label;
        btn.dataset.map = map.key;
        btn.onclick = () => switchFlipbookMap(run, map.key);
        buttons.appendChild(btn);
    });

    // Show default map
    const defaultMap = maps.find(m => m.default);
    switchFlipbookMap(run, defaultMap.key);
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

    // Debug: log what we're looking for
    console.log('switchFlipbookMap:', mapKey, 'spatialMaps:', run.spatialMaps, 'found:', imagePath);

    if (imagePath) {
        img.src = imagePath;
        img.alt = mapKey;
    } else {
        // No spatial map available - show placeholder or hide
        img.alt = `${mapKey} not available`;
        console.warn(`Spatial map '${mapKey}' not found for run ${run.id}`);
    }
}

/**
 * Update carpet plot display
 */
function updateCarpetPlot(run) {
    const img = document.getElementById('carpet-image');
    if (!img) return;

    if (run.carpetPath) {
        img.src = run.carpetPath;
        img.style.display = 'block';
    } else {
        img.style.display = 'none';
    }
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
