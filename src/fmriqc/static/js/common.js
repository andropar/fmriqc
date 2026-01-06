/**
 * Common utilities - dark mode, konami code, search, tooltips
 */

// Dark mode toggle
function toggleDarkMode() {
  document.body.classList.toggle('dark-mode');
  const isDark = document.body.classList.contains('dark-mode');
  localStorage.setItem('qa_dark_mode', isDark);
  const btn = document.querySelector('.dark-mode-toggle');
  if (btn) {
    btn.textContent = isDark ? '☀️ Light' : '🌙 Dark';
  }
}

// Konami code easter egg
let konamiCode = [];
const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'KeyB', 'KeyA'];

function checkKonamiCode(key) {
  konamiCode.push(key);
  if (konamiCode.length > konamiSequence.length) {
    konamiCode.shift();
  }
  if (konamiCode.length === konamiSequence.length) {
    let match = true;
    for (let i = 0; i < konamiSequence.length; i++) {
      if (konamiCode[i] !== konamiSequence[i]) {
        match = false;
        break;
      }
    }
    if (match) {
      const egg = document.getElementById('easterEgg');
      if (egg) egg.classList.add('active');
      konamiCode = [];
    }
  }
}

function closeEasterEgg() {
  const egg = document.getElementById('easterEgg');
  if (egg) egg.classList.remove('active');
}

// Sidebar toggle
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.querySelector('.sidebar-overlay');
  if (sidebar) sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('active');
}

// Tooltip positioning
function initTooltips() {
  document.querySelectorAll('.metric-name').forEach(function(el) {
    const tooltip = el.querySelector('.tooltip-text');
    if (!tooltip) return;
    el.addEventListener('mouseenter', function(e) {
      const rect = el.getBoundingClientRect();
      const tooltipWidth = 300;
      let left = rect.left;
      let top = rect.bottom + 8;
      // Keep tooltip in viewport
      if (left + tooltipWidth > window.innerWidth - 16) {
        left = window.innerWidth - tooltipWidth - 16;
      }
      if (top + 100 > window.innerHeight) {
        top = rect.top - 8;
        tooltip.style.transform = 'translateY(-100%)';
      } else {
        tooltip.style.transform = 'translateY(0)';
      }
      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
    });
  });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
  // Load dark mode preference
  const darkMode = localStorage.getItem('qa_dark_mode') === 'true';
  if (darkMode) {
    document.body.classList.add('dark-mode');
    const btn = document.querySelector('.dark-mode-toggle');
    if (btn) btn.textContent = '☀️ Light';
  }

  // Initialize tooltips
  initTooltips();
});

// Global keydown handler for konami code
document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  checkKonamiCode(e.code);
});
