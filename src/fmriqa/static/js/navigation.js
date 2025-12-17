/**
 * Keyboard navigation and nav panel management for subject reports
 */

let currentRunIndex = -1;
let allRuns = [];

function initKeyboardNavigation() {
  // Only select run details, not session details
  allRuns = Array.from(document.querySelectorAll('details[id^="run-details-"]'));
}

function navigateRuns(direction) {
  if (allRuns.length === 0) initKeyboardNavigation();
  if (allRuns.length === 0) return;

  if (currentRunIndex < 0) currentRunIndex = direction > 0 ? 0 : allRuns.length - 1;
  else currentRunIndex += direction;

  if (currentRunIndex < 0) currentRunIndex = allRuns.length - 1;
  if (currentRunIndex >= allRuns.length) currentRunIndex = 0;

  const runDetail = allRuns[currentRunIndex];
  // Close all other runs first
  allRuns.forEach(function(d) { if (d !== runDetail) d.open = false; });

  // Open parent session first
  const parentSession = runDetail.closest('details[id^="session-details-"]');
  if (parentSession) parentSession.open = true;

  runDetail.open = true;
  runDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Update nav highlight
  const runId = runDetail.id.replace('run-details-', '');
  updateActiveNavItem(runId);
}

function navigateToRun(runId) {
  const detail = document.getElementById('run-details-' + runId);
  if (detail) {
    // Close all other runs first
    document.querySelectorAll('details[id^="run-details-"]').forEach(function(d) {
      if (d !== detail) d.open = false;
    });
    // Open parent session first
    const parent = detail.closest('details[id^="session-details-"]');
    if (parent) parent.open = true;
    detail.open = true;
    detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    updateActiveNavItem(runId);
    // Sync keyboard navigation index
    if (allRuns.length === 0) initKeyboardNavigation();
    currentRunIndex = allRuns.indexOf(detail);
  }
}

function updateActiveNavItem(runId) {
  document.querySelectorAll('.nav-item').forEach(function(item) {
    item.classList.remove('active');
  });
  const navItem = document.querySelector('.nav-run[data-run="' + runId + '"]');
  if (navItem) {
    navItem.classList.add('active');
    // Scroll nav item into view within the nav panel
    navItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

function toggleNavPanel() {
  const panel = document.getElementById('navPanel');
  const content = document.querySelector('.content-with-nav');
  if (panel) panel.classList.toggle('collapsed');
  if (content) content.classList.toggle('content-with-nav');
}

function filterNav(filter) {
  document.querySelectorAll('.nav-filter-btn').forEach(function(btn) {
    btn.classList.remove('active');
  });
  const activeBtn = document.getElementById('filter' + filter.charAt(0).toUpperCase() + filter.slice(1));
  if (activeBtn) activeBtn.classList.add('active');

  const navRuns = document.querySelectorAll('.nav-run');
  navRuns.forEach(function(item) {
    if (filter === 'all') {
      item.style.display = '';
    } else if (filter === 'flagged') {
      item.style.display = item.dataset.flagged === 'true' ? '' : 'none';
    }
  });
}

function expandAll() {
  document.querySelectorAll('details').forEach(function(d) { d.open = true; });
}

function collapseAll() {
  document.querySelectorAll('details').forEach(function(d) { d.open = false; });
}

function nextFlagged() {
  const flaggedRuns = document.querySelectorAll('.nav-run[data-flagged="true"]');
  if (flaggedRuns.length === 0) return;
  const activeRun = document.querySelector('.nav-run.active');
  let nextIndex = 0;
  if (activeRun) {
    for (let i = 0; i < flaggedRuns.length; i++) {
      if (flaggedRuns[i] === activeRun) {
        nextIndex = (i + 1) % flaggedRuns.length;
        break;
      }
    }
  }
  navigateToRun(flaggedRuns[nextIndex].dataset.run);
}

// Search/filter runs
function filterRuns() {
  const searchTerm = document.getElementById('searchInput').value.toLowerCase();
  const allDetails = document.querySelectorAll('details[id^="run-details-"], details[id^="session-details-"]');
  allDetails.forEach(function(detail) {
    const text = detail.textContent.toLowerCase();
    if (text.includes(searchTerm)) {
      detail.classList.remove('hidden');
    } else {
      detail.classList.add('hidden');
    }
  });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

  if (e.key === 'j' || e.key === 'J') {
    e.preventDefault();
    navigateRuns(1);
  } else if (e.key === 'k' || e.key === 'K') {
    e.preventDefault();
    navigateRuns(-1);
  } else if (e.key === ' ' && e.target.tagName !== 'INPUT') {
    e.preventDefault();
    // Toggle good/bad on current run
    if (currentRunIndex >= 0 && currentRunIndex < allRuns.length) {
      const runDetail = allRuns[currentRunIndex];
      const runId = runDetail.id.replace('run-details-', '');
      const indicator = document.getElementById('run-' + runId);
      if (indicator) {
        const sessionId = indicator.dataset.sessionId;
        const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';
        const newQuality = currentQuality === 'good' ? 'bad' : 'good';
        setQualityIndicator(indicator, newQuality);
        saveQualityState(runId, newQuality);
        if (sessionId) updateSessionQuality(sessionId);
        updateReviewProgress();
      }
    }
  } else if (e.key === '/' && e.target.tagName !== 'INPUT') {
    e.preventDefault();
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.focus();
  } else if (e.key === 'f' || e.key === 'F') {
    e.preventDefault();
    nextFlagged();
  } else if (e.key === 'e' || e.key === 'E') {
    e.preventDefault();
    expandAll();
  } else if (e.key === 'c' || e.key === 'C') {
    e.preventDefault();
    collapseAll();
  }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
  initKeyboardNavigation();
});
