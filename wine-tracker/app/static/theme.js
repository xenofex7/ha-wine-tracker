// Theme: 3-state cycle → system → dark → light
const THEME_MODES = ['system', 'dark', 'light'];
const THEME_ICONS = { dark: '<i class="mdi mdi-weather-night"></i>', light: '<i class="mdi mdi-weather-sunny"></i>', system: '<i class="mdi mdi-laptop"></i>' };

function getSystemPreference() {
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(mode) {
  const effective = mode === 'system' ? getSystemPreference() : mode;
  document.documentElement.classList.toggle('light', effective === 'light');
  const btn = document.querySelector('.theme-icon');
  if (btn) btn.innerHTML = THEME_ICONS[mode];
  if (typeof window._onThemeApplied === 'function') window._onThemeApplied();
}

function cycleTheme() {
  const current = localStorage.getItem('wine-theme') || 'system';
  const idx = THEME_MODES.indexOf(current);
  const next = THEME_MODES[(idx + 1) % THEME_MODES.length];
  localStorage.setItem('wine-theme', next);
  applyTheme(next);
}

// OS theme change listener (initial apply already done by inline <head> script)
window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
  if ((localStorage.getItem('wine-theme') || 'system') === 'system') applyTheme('system');
});
// Set icon for theme button once DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const mode = localStorage.getItem('wine-theme') || 'system';
  const btn = document.querySelector('.theme-icon');
  if (btn) btn.innerHTML = THEME_ICONS[mode];
});
