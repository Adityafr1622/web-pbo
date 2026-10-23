/* Fluenglo: hanya Light / Dark; preferensi lokal per akun di browser ini. */
(function () {
  'use strict';
  const root = document.documentElement;
  const storageKey = 'fluenglo-theme-v1:' + (root.dataset.themeUser || 'guest');
  const themeButtons = document.querySelectorAll('[data-theme-choice]');

  function showSelection() {
    const current = root.dataset.theme === 'dark' ? 'dark' : 'light';
    themeButtons.forEach(button => {
      const selected = button.dataset.themeChoice === current;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-pressed', String(selected));
    });
  }
  themeButtons.forEach(button => {
    button.addEventListener('click', () => {
      const next = button.dataset.themeChoice === 'dark' ? 'dark' : 'light';
      root.dataset.theme = next;
      try { localStorage.setItem(storageKey, next); localStorage.setItem('fluenglo-theme-v1:browser', next); } catch (_) { /* privat: tetap aktif sampai refresh */ }
      showSelection();
    });
  });
  showSelection();
}());
