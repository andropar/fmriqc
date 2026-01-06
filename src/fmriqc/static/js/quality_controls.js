/**
 * Quality control state management for subject reports
 */

function getStorageKey(id) {
  return 'qa_quality_' + id;
}

function loadQualityState(id) {
  const key = getStorageKey(id);
  const stored = localStorage.getItem(key);
  return stored === 'good' ? 'good' : (stored === 'bad' ? 'bad' : null);
}

function saveQualityState(id, quality) {
  const key = getStorageKey(id);
  localStorage.setItem(key, quality);
}

function setQualityIndicator(element, quality) {
  if (quality === 'good') {
    element.className = 'quality-indicator quality-good';
    element.textContent = '✓ Good';
  } else {
    element.className = 'quality-indicator quality-bad';
    element.textContent = '✗ Bad';
  }
}

function handleRunQuality(runId, sessionId, event) {
  event.stopPropagation();
  const indicator = document.getElementById('run-' + runId);
  if (!indicator) return;

  const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';
  const newQuality = currentQuality === 'good' ? 'bad' : 'good';
  setQualityIndicator(indicator, newQuality);
  saveQualityState(runId, newQuality);
  updateSessionQuality(sessionId);
  updateReviewProgress();
}

function handleSessionQuality(sessionId, event) {
  event.stopPropagation();
  const indicator = document.getElementById('session-' + sessionId);
  if (!indicator) return;

  const currentQuality = indicator.classList.contains('quality-good') ? 'good' : 'bad';
  const newQuality = currentQuality === 'good' ? 'bad' : 'good';
  setQualityIndicator(indicator, newQuality);
  saveQualityState(sessionId, newQuality);

  // Update all runs in this session
  const runIndicators = document.querySelectorAll('.quality-indicator[id^="run-"][data-session-id="' + sessionId + '"]');
  runIndicators.forEach(function(runIndicator) {
    const runId = runIndicator.id.replace('run-', '');
    setQualityIndicator(runIndicator, newQuality);
    saveQualityState(runId, newQuality);
  });
  updateReviewProgress();
}

function updateSessionQuality(sessionId) {
  const sessionIndicator = document.getElementById('session-' + sessionId);
  if (!sessionIndicator) return;

  const runIndicators = document.querySelectorAll('.quality-indicator[id^="run-"][data-session-id="' + sessionId + '"]');
  if (runIndicators.length === 0) return;

  const allGood = Array.from(runIndicators).every(function(ind) {
    return ind.classList.contains('quality-good');
  });
  const allBad = Array.from(runIndicators).every(function(ind) {
    return ind.classList.contains('quality-bad');
  });

  if (allGood) {
    setQualityIndicator(sessionIndicator, 'good');
    saveQualityState(sessionId, 'good');
  } else if (allBad) {
    setQualityIndicator(sessionIndicator, 'bad');
    saveQualityState(sessionId, 'bad');
  }
}

function updateReviewProgress() {
  const total = document.querySelectorAll('.nav-run').length;
  let reviewed = 0;
  document.querySelectorAll('.nav-run').forEach(function(item) {
    const runId = item.dataset.run;
    if (loadQualityState(runId)) reviewed++;
  });

  const reviewCount = document.getElementById('reviewCount');
  if (reviewCount) reviewCount.textContent = reviewed;

  const pct = total > 0 ? (reviewed / total * 100) : 0;
  const progressFill = document.getElementById('progressFill');
  if (progressFill) progressFill.style.width = pct + '%';

  // Update nav item dots based on quality state
  document.querySelectorAll('.nav-run').forEach(function(item) {
    const runId = item.dataset.run;
    const quality = loadQualityState(runId);
    const dot = item.querySelector('.nav-item-dot');
    if (dot) {
      if (quality === 'good') {
        dot.classList.remove('flagged', 'bad');
        dot.classList.add('good');
      } else if (quality === 'bad') {
        dot.classList.remove('flagged', 'good');
        dot.classList.add('bad');
      }
    }
  });
}

// Initialize quality state from localStorage
document.addEventListener('DOMContentLoaded', function() {
  const allIndicators = document.querySelectorAll('.quality-indicator[id^="run-"], .quality-indicator[id^="session-"]');
  allIndicators.forEach(function(indicator) {
    const id = indicator.id.replace(/^(run-|session-)/, '');
    const storedQuality = loadQualityState(id);
    if (storedQuality) {
      setQualityIndicator(indicator, storedQuality);
    }
  });

  // Update all session indicators
  const sessionIndicators = document.querySelectorAll('.quality-indicator[id^="session-"]');
  sessionIndicators.forEach(function(sessionIndicator) {
    const sessionId = sessionIndicator.id.replace('session-', '');
    updateSessionQuality(sessionId);
  });

  updateReviewProgress();
});
