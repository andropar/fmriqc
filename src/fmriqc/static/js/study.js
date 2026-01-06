/**
 * Study report specific functionality
 */

function filterSubjects() {
  const searchTerm = document.getElementById('searchInput').value.toLowerCase();
  const allCards = document.querySelectorAll('.subject-card');
  allCards.forEach(function(card) {
    const text = card.textContent.toLowerCase();
    if (text.includes(searchTerm)) {
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
    }
  });
}

// Study report keyboard shortcuts
document.addEventListener('keydown', function(e) {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === '/' && e.target.tagName !== 'INPUT') {
    e.preventDefault();
    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.focus();
  }
});
