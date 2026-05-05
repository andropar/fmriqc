/**
 * Review state management with JSON persistence
 */

let reviewsData = null;
function reviewsStorageKey() {
    const reportId = subjectData.reportId || subjectData.snapshotId || 'unknown';
    return `fmriqc_reviews_${reportId}_${subjectData.subject}`;
}

/**
 * Initialize the review system
 */
function initReviewSystem() {
    // Load existing reviews
    loadReviews();

    // Update UI
    updateAllReviewStates();
    updateReviewProgress();
    updateNoteIndicators();

    // Set up save on unload
    window.addEventListener('beforeunload', function() {
        // Reviews are saved immediately on change, but just in case
    });
}

/**
 * Load reviews from embedded data or localStorage fallback
 */
function loadReviews() {
    // First try to load from embedded data (from JSON file)
    if (typeof initialReviews !== 'undefined' && initialReviews) {
        reviewsData = initialReviews;
        return;
    }

    // Fallback to localStorage
    const stored = localStorage.getItem(reviewsStorageKey());
    if (stored) {
        try {
            reviewsData = JSON.parse(stored);
        } catch (e) {
            reviewsData = {};
        }
    } else {
        reviewsData = {};
    }
}

/**
 * Get current reviews
 */
function getReviews() {
    return reviewsData || {};
}

/**
 * Save reviews to localStorage and trigger download prompt if significant changes
 */
function saveReviews(reviews) {
    reviewsData = reviews;

    // Save to localStorage as backup
    localStorage.setItem(reviewsStorageKey(), JSON.stringify(reviews));

    // Update embedded data for potential download
    if (typeof window.reviewsChanged === 'function') {
        window.reviewsChanged(reviews);
    }
}

/**
 * Set review status for a run
 */
function setReviewStatus(runId, status) {
    const reviews = getReviews();

    if (!reviews[runId]) {
        reviews[runId] = {};
    }

    // Toggle off if clicking same status
    if (reviews[runId].status === status) {
        reviews[runId].status = null;
    } else {
        reviews[runId].status = status;
    }

    reviews[runId].updated_at = new Date().toISOString();

    saveReviews(reviews);
    updateAllReviewStates();
    updateReviewProgress();
}

/**
 * Update review buttons for a specific run
 */
function updateReviewButtons(runId) {
    const reviews = getReviews();
    const review = reviews[runId] || {};
    const status = review.status;

    // Update row buttons
    const row = document.querySelector(`tr[data-run-id="${runId}"]`);
    if (row) {
        row.classList.toggle('row-good', status === 'good');
        row.classList.toggle('row-exclude', status === 'exclude');

        const goodBtn = row.querySelector('.good-btn');
        const badBtn = row.querySelector('.bad-btn');
        if (goodBtn) goodBtn.classList.toggle('active', status === 'good');
        if (badBtn) badBtn.classList.toggle('active', status === 'exclude');
    }

    // Update modal buttons if open
    const modalGoodBtn = document.getElementById('modal-good-btn');
    const modalBadBtn = document.getElementById('modal-bad-btn');
    if (modalGoodBtn) modalGoodBtn.classList.toggle('active', status === 'good');
    if (modalBadBtn) modalBadBtn.classList.toggle('active', status === 'exclude');
}

/**
 * Update all review states in the UI
 */
function updateAllReviewStates() {
    const reviews = getReviews();

    subjectData.runs.forEach(run => {
        updateReviewButtons(run.id);
    });
}

/**
 * Update the review progress bar
 */
function updateReviewProgress() {
    const reviews = getReviews();
    const total = subjectData.runs.length;

    let goodCount = 0;
    let excludeCount = 0;

    subjectData.runs.forEach(run => {
        const review = reviews[run.id];
        if (review?.status === 'good') goodCount++;
        if (review?.status === 'exclude') excludeCount++;
    });

    const pendingCount = total - goodCount - excludeCount;
    const goodPercent = (goodCount / total) * 100;
    const excludePercent = (excludeCount / total) * 100;

    // Update progress bar
    const progressBar = document.querySelector('.review-progress-bar');
    if (progressBar) {
        progressBar.innerHTML = `
            <div class="good" style="width: ${goodPercent}%"></div>
            <div class="bad" style="width: ${excludePercent}%"></div>
        `;
    }

    // Update text
    const progressText = document.querySelector('.review-progress-text');
    if (progressText) {
        progressText.textContent = `${goodCount} good, ${excludeCount} marked review, ${pendingCount} pending`;
    }
}

/**
 * Update note indicators on rows
 */
function updateNoteIndicators() {
    const reviews = getReviews();

    document.querySelectorAll('tr[data-run-id]').forEach(row => {
        const runId = row.dataset.runId;
        const review = reviews[runId];
        const indicator = row.querySelector('.note-indicator');

        if (indicator) {
            if (review?.note && review.note.trim()) {
                indicator.style.display = 'inline';
                indicator.title = review.note;
            } else {
                indicator.style.display = 'none';
            }
        }
    });
}

/**
 * Download reviews as JSON file
 */
function downloadReviews() {
    const reviews = getReviews();
    const data = {
        schema_version: 2,
        snapshot_id: subjectData.snapshotId || 'unknown',
        subject: subjectData.subject,
        exported_at: new Date().toISOString(),
        reviews: reviews
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `qa_reviews_${subjectData.snapshotId || 'snapshot'}_${subjectData.subject}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Get summary of manual review flags for export
 */
function getReviewFlagSummary() {
    const reviews = getReviews();
    const flagged = [];

    subjectData.runs.forEach(run => {
        const review = reviews[run.id];
        if (review?.status === 'exclude') {
            flagged.push({
                run_id: run.id,
                reason: review.note || 'Manual review flag',
                flagged_at: review.updated_at
            });
        }
    });

    return flagged;
}

// Export functions
window.initReviewSystem = initReviewSystem;
window.getReviews = getReviews;
window.saveReviews = saveReviews;
window.setReviewStatus = setReviewStatus;
window.updateReviewButtons = updateReviewButtons;
window.downloadReviews = downloadReviews;
window.getReviewFlagSummary = getReviewFlagSummary;
