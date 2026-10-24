/* Fluenglo UTS — pencarian + pagination ringan. Semua data tetap difilter dahulu,
   baru dibagi per delapan; tidak memotong hasil pencarian ke halaman aktif. */
(() => {
  'use strict';
  const PAGE_SIZE = 8;
  const norm = s => (s || '').toLocaleLowerCase('id').trim();
  const $all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function mount(root, globalInput = null) {
    const isTable = root.matches('[data-table-page]');
    const container = isTable ? root.querySelector('tbody') : root;
    if (!container) return null;
    const rows = isTable ? $all(':scope > tr:not(.row-empty)', container) :
      $all(':scope > [data-list-item]', container);
    if (!rows.length) return null;
    const localSearch = root.querySelector('.table-search') ||
      (root.previousElementSibling && root.previousElementSibling.matches('[data-search-panel]') ?
        root.previousElementSibling.querySelector('.table-search') : null);
    const input = globalInput || localSearch;
    let page = 1;
    const footer = document.createElement('div'); footer.className = 'pagination-bar';
    const info = document.createElement('span'); info.className = 'pagination-info';
    const controls = document.createElement('div'); controls.className = 'pagination-controls';
    const previous = document.createElement('button'); previous.type = 'button';
    previous.className = 'btn btn-light btn-sm'; previous.textContent = '‹ Sebelumnya';
    const next = document.createElement('button'); next.type = 'button';
    next.className = 'btn btn-light btn-sm'; next.textContent = 'Berikutnya ›';
    const pageLabel = document.createElement('span'); pageLabel.className = 'pagination-current';
    controls.append(previous, pageLabel, next); footer.append(info, controls);
    root.append(footer);
    const empty = document.createElement('p'); empty.className = 'search-empty';
    empty.textContent = 'Tidak ada data yang sesuai dengan pencarian.';
    root.append(empty);

    const render = (reset = false) => {
      if (reset) page = 1;
      const query = norm(input ? input.value : '');
      const matches = rows.filter(row => norm(row.textContent).includes(query));
      const pages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
      page = Math.min(page, pages);
      const from = (page - 1) * PAGE_SIZE;
      const selected = new Set(matches.slice(from, from + PAGE_SIZE));
      rows.forEach(row => { row.hidden = !selected.has(row); });
      info.textContent = matches.length ? `Menampilkan ${from + 1}–${Math.min(from + PAGE_SIZE, matches.length)} dari ${matches.length} data` : '0 data ditemukan';
      pageLabel.textContent = `${page} / ${pages}`;
      previous.disabled = page === 1; next.disabled = page === pages;
      controls.hidden = matches.length <= PAGE_SIZE;
      empty.hidden = matches.length !== 0;
      if (root.dataset.listGroup === 'jadwal') {
        const section = root.closest('.jadwal-group');
        if (section) section.hidden = matches.length === 0 && !!query;
      }
    };
    previous.addEventListener('click', () => { if (page > 1) { page--; render(); } });
    next.addEventListener('click', () => { page++; render(); });
    if (input && !globalInput) input.addEventListener('input', () => render(true));
    render();
    return { render };
  }

  $all('[data-table-page]:not([data-list-group]), [data-list-page]').forEach(root => mount(root));
  $all('[data-search-global]').forEach(panel => {
    const input = panel.querySelector('.table-search');
    if (!input) return;
    const name = panel.dataset.searchGlobal;
    const pagers = $all(`[data-table-page][data-list-group="${name}"]`).map(root => mount(root, input)).filter(Boolean);
    input.addEventListener('input', () => pagers.forEach(p => p.render(true)));
  });
  // File lampiran saat ini terlihat saat modal Edit dibuka dari tombol pensil.
  document.addEventListener('click', event => {
    const edit = event.target.closest('[data-edit="modal-edit-tugas"]');
    if (!edit) return;
    const label = document.querySelector('#modal-edit-tugas [data-current-attachment]');
    if (!label) return;
    try { label.textContent = JSON.parse(edit.dataset.fill || '{}').lampiran_lama || 'Belum ada lampiran'; }
    catch (_) { label.textContent = 'Belum ada lampiran'; }
  });
  document.querySelectorAll('form[data-confirm-submit]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirmSubmit)) event.preventDefault();
    });
  });
})();
