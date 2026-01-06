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
  if (panel) {
    panel.classList.toggle('collapsed');
    // Save state to localStorage
    const isCollapsed = panel.classList.contains('collapsed');
    localStorage.setItem('nav_panel_collapsed', isCollapsed ? 'true' : 'false');
  }
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

function previousFlagged() {
  const flaggedRuns = document.querySelectorAll('.nav-run[data-flagged="true"]');
  if (flaggedRuns.length === 0) return;
  const activeRun = document.querySelector('.nav-run.active');
  let prevIndex = flaggedRuns.length - 1;
  if (activeRun) {
    for (let i = 0; i < flaggedRuns.length; i++) {
      if (flaggedRuns[i] === activeRun) {
        prevIndex = i - 1;
        if (prevIndex < 0) prevIndex = flaggedRuns.length - 1;
        break;
      }
    }
  }
  navigateToRun(flaggedRuns[prevIndex].dataset.run);
}

// Phase 6: Show keyboard shortcuts overlay
function showKeyboardHelp() {
  const existingOverlay = document.getElementById('keyboardHelpOverlay');
  if (existingOverlay) {
    existingOverlay.remove();
    return;
  }

  const overlay = document.createElement('div');
  overlay.id = 'keyboardHelpOverlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    animation: fadeIn 0.2s ease-out;
  `;

  const helpBox = document.createElement('div');
  helpBox.style.cssText = `
    background: var(--paper, white);
    color: var(--ink, #222);
    padding: 2rem;
    border-radius: 8px;
    max-width: 500px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s ease-out;
  `;

  helpBox.innerHTML = `
    <h3 style="margin-top: 0; margin-bottom: 1.5rem; font-size: 1.25rem;">Keyboard Shortcuts</h3>
    <div style="display: grid; grid-template-columns: auto 1fr; gap: 0.75rem 1.5rem;">
      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">J</kbd>
      <span>Next run</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">K</kbd>
      <span>Previous run</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">F</kbd>
      <span>Next flagged run</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">P</kbd>
      <span>Previous flagged run</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">E</kbd>
      <span>Expand all sections</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">C</kbd>
      <span>Collapse all sections</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">Space</kbd>
      <span>Toggle quality (good/bad)</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">/</kbd>
      <span>Focus search</span>

      <kbd style="background: #f0f0f0; padding: 0.25rem 0.5rem; border-radius: 3px; font-family: monospace;">?</kbd>
      <span>Toggle this help</span>
    </div>
    <button onclick="document.getElementById('keyboardHelpOverlay').remove()"
            style="margin-top: 1.5rem; padding: 0.5rem 1rem; background: var(--accent, #0066cc); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem;">
      Close
    </button>
  `;

  overlay.appendChild(helpBox);
  document.body.appendChild(overlay);

  // Close on click outside
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      overlay.remove();
    }
  });

  // Close on Escape
  const escapeHandler = function(e) {
    if (e.key === 'Escape') {
      overlay.remove();
      document.removeEventListener('keydown', escapeHandler);
    }
  };
  document.addEventListener('keydown', escapeHandler);
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
  } else if (e.key === 'p' || e.key === 'P') {
    e.preventDefault();
    previousFlagged();
  } else if (e.key === 'e' || e.key === 'E') {
    e.preventDefault();
    expandAll();
  } else if (e.key === 'c' || e.key === 'C') {
    e.preventDefault();
    collapseAll();
  } else if (e.key === '?') {
    e.preventDefault();
    showKeyboardHelp();
  }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
  initKeyboardNavigation();

  // Restore nav panel collapsed state from localStorage
  const savedNavState = localStorage.getItem('nav_panel_collapsed');
  if (savedNavState === 'true') {
    const panel = document.getElementById('navPanel');
    const content = document.querySelector('.content-with-nav');
    if (panel) panel.classList.add('collapsed');
    if (content) content.classList.remove('content-with-nav');
  }
});
