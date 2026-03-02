// Theme system: named themes × light/dark mode
var THEME_MODES = ['system', 'dark', 'light'];

// Theme definitions with preview colors [bg-dark, accent, gold]
var THEMES = [
  { key: 'classic',   colors: ['#1a0a0f', '#c0392b', '#d4a843'] },
  { key: 'vineyard',  colors: ['#0f1a12', '#4caf50', '#c9a84c'] },
  { key: 'champagne', colors: ['#1a1508', '#c9a84c', '#d4a843'] },
  { key: 'slate',     colors: ['#12151c', '#5c7cfa', '#c9a84c'] },
  { key: 'burgundy',  colors: ['#180a1c', '#ab47bc', '#d4a843'] },
  { key: 'homeassistant', colors: ['#111111', '#009ac7', '#ff9800'] }
];

function getSystemPreference() {
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(mode) {
  var effective = mode === 'system' ? getSystemPreference() : mode;
  document.documentElement.classList.toggle('light', effective === 'light');
  if (typeof window._onThemeApplied === 'function') window._onThemeApplied();
}

function applyThemeName(name) {
  if (!name || name === 'classic') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', name);
  }
}

function setThemeName(name) {
  localStorage.setItem('wine-theme-name', name);
  applyThemeName(name);
  updateThemeDropdown();
}

function setThemeMode(mode) {
  localStorage.setItem('wine-theme', mode);
  applyTheme(mode);
  updateThemeSegmented();
}

function cycleTheme() {
  var current = localStorage.getItem('wine-theme') || 'system';
  var idx = THEME_MODES.indexOf(current);
  var next = THEME_MODES[(idx + 1) % THEME_MODES.length];
  setThemeMode(next);
}

function updateThemeSegmented() {
  var current = localStorage.getItem('wine-theme') || 'system';
  document.querySelectorAll('.theme-seg-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.theme === current);
  });
}

function updateThemeDropdown() {
  var current = localStorage.getItem('wine-theme-name') || 'classic';
  // Update button display
  var btn = document.querySelector('.theme-dropdown-btn');
  if (btn) {
    var t = THEMES.find(function(t) { return t.key === current; }) || THEMES[0];
    var label = btn.querySelector('.dd-label');
    var dots = btn.querySelector('.theme-dots');
    if (label) label.textContent = getThemeLabel(current);
    if (dots) dots.innerHTML = t.colors.map(function(c) {
      return '<span class="theme-dot" style="background:' + c + '"></span>';
    }).join('');
  }
  // Update list items
  document.querySelectorAll('.theme-dropdown-item').forEach(function(item) {
    var isActive = item.dataset.theme === current;
    item.classList.toggle('active', isActive);
    var check = item.querySelector('.dd-check');
    if (check) check.style.display = isActive ? '' : 'none';
  });
}

function getThemeLabel(key) {
  // Try to get translated label from DOM data attribute, fallback to capitalized key
  var el = document.querySelector('[data-theme-labels]');
  if (el) {
    try {
      var labels = JSON.parse(el.dataset.themeLabels);
      if (labels[key]) return labels[key];
    } catch(e) {}
  }
  return key.charAt(0).toUpperCase() + key.slice(1);
}

function toggleThemeDropdown(e) {
  if (e) e.stopPropagation();
  var dd = document.querySelector('.theme-dropdown');
  if (dd) dd.classList.toggle('open');
}

// Close dropdown when clicking outside
document.addEventListener('click', function(e) {
  var dd = document.querySelector('.theme-dropdown');
  if (dd && !dd.contains(e.target)) dd.classList.remove('open');
});

// Apply theme name on load (mode is handled by inline script + OS listener)
(function() {
  var name = localStorage.getItem('wine-theme-name') || 'classic';
  applyThemeName(name);
})();

// OS theme change listener
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function() {
  if ((localStorage.getItem('wine-theme') || 'system') === 'system') applyTheme('system');
});

// Initialize UI controls when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  updateThemeSegmented();
  updateThemeDropdown();
});
