/**
 * View management for subject reports (thumbnail view vs detail view)
 */

function setView(view) {
  const thumb = document.getElementById('thumbnail-view');
  const detail = document.getElementById('detail-view');
  const btnThumb = document.getElementById('viewThumbBtn');
  const btnDetail = document.getElementById('viewDetailBtn');

  if (view === 'thumb') {
    if (thumb) thumb.classList.remove('hidden');
    if (detail) detail.classList.add('hidden');
    if (btnThumb) btnThumb.classList.add('active');
    if (btnDetail) btnDetail.classList.remove('active');
  } else {
    if (detail) detail.classList.remove('hidden');
    if (thumb) thumb.classList.add('hidden');
    if (btnDetail) btnDetail.classList.add('active');
    if (btnThumb) btnThumb.classList.remove('active');
  }
}

function openDetailAndJump(runId) {
  setView('detail');
  const target = document.getElementById('run-details-' + runId);
  if (target) {
    target.setAttribute('open', 'true');
    target.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
}

function filterThumbs(session) {
  const cards = document.querySelectorAll('.thumb-card');
  cards.forEach(function(c) {
    if (session === 'all' || c.dataset.session === session) {
      c.classList.remove('hidden');
    } else {
      c.classList.add('hidden');
    }
  });

  const sections = document.querySelectorAll('.thumb-session');
  sections.forEach(function(sec) {
    const sess = sec.dataset.session;
    if (session === 'all' || sess === session) {
      sec.classList.remove('hidden');
    } else {
      sec.classList.add('hidden');
    }
  });

  document.querySelectorAll('.thumb-filters .pill').forEach(function(btn) {
    btn.classList.remove('active');
  });
  const activeBtn = document.querySelector('.thumb-filters .pill[data-session="' + session + '"]');
  if (activeBtn) activeBtn.classList.add('active');
}

function setThumbDensity(density, btn) {
  // Save preference
  localStorage.setItem('qa_thumb_density', density);

  // Update button states
  document.querySelectorAll('.density-btn').forEach(function(b) {
    b.classList.remove('active');
  });
  btn.classList.add('active');

  // Update all thumb grids
  document.querySelectorAll('.thumb-grid').forEach(function(grid) {
    grid.classList.remove('density-compact', 'density-spacious');
    if (density === 'compact') {
      grid.classList.add('density-compact');
    } else if (density === 'spacious') {
      grid.classList.add('density-spacious');
    }
  });
}

// Restore density preference on load
document.addEventListener('DOMContentLoaded', function() {
  const savedDensity = localStorage.getItem('qa_thumb_density');
  if (savedDensity) {
    const btn = document.querySelector('.density-btn[onclick*="' + savedDensity + '"]');
    if (btn) {
      setThumbDensity(savedDensity, btn);
    }
  }
});
