// Fluenglo: interaksi umum (modal, tab, dropdown, multi-select, toggle password)
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const openM = m => { if (m) { m.hidden = false; document.body.classList.add('no-scroll'); } };
  const closeM = m => { m.hidden = true; if (!$('.modal:not([hidden])')) document.body.classList.remove('no-scroll'); };

  const syncMulti = w => {
    const on = $$('input[type=checkbox]:checked', w), lab = $('[data-label]', w);
    $$('input[type=hidden]', w).forEach((h, i) => h.value = on[i] ? on[i].value : '');
    lab.textContent = on.length ? on.map(c => c.dataset.name).join(', ') : lab.dataset.ph;
    $('.multi-btn', w).classList.toggle('has-value', on.length > 0);
  };

  document.addEventListener('click', e => {
    const t = e.target, up = s => t.closest(s);
    let el;

    if (!up('.usermenu')) { const dd = $('.user-dropdown'); if (dd) dd.hidden = true; }
    if (!up('.multi')) $$('.multi-list').forEach(l => l.hidden = true);

    if ((el = up('[data-open]'))) return openM($('#' + el.dataset.open));
    if (up('[data-close]')) return closeM(up('.modal'));
    if (t.classList.contains('modal')) return closeM(t);

    if ((el = up('[data-edit]'))) {            // isi form edit dari data-fill (JSON)
      const m = $('#' + el.dataset.edit), f = $('form', m), d = JSON.parse(el.dataset.fill || '{}');
      f.reset(); f.action = el.dataset.action;
      Object.entries(d).forEach(([k, v]) => { const i = f.elements[k]; if (i && i.type !== 'file') i.value = v ?? ''; });
      $$('[data-multi]', f).forEach(w => {
        $$('input[type=checkbox]', w).forEach(c => c.checked = (d.pengajar_ids || []).includes(+c.value));
        syncMulti(w);
      });
      $$('[data-del-btn]', m).forEach(b => { b.dataset.confirm = el.dataset.del || ''; b.dataset.text = el.dataset.delText || ''; });
      return openM(m);
    }
    if ((el = up('[data-confirm]'))) {         // konfirmasi hapus
      $$('.modal:not([hidden])').forEach(m => closeM(m));
      $('#confirm-text').textContent = el.dataset.text || 'Yakin ingin menghapus data ini?';
      $('#confirm-ok').href = el.dataset.confirm;
      return openM($('#modal-confirm'));
    }
    if ((el = up('[data-tab]'))) {             // tab Siswa / Pengajar
      const v = el.dataset.tab;
      $$('[data-tab]').forEach(b => b.classList.toggle('is-active', b === el));
      $$('[data-panel]').forEach(p => p.hidden = p.dataset.panel !== v);
      $$('[data-for]').forEach(b => b.hidden = b.dataset.for !== v);
      return;
    }
    if ((el = up('[data-pane]'))) {            // tab Halaman Login / Tentang Kami
      $$('[data-pane]').forEach(b => b.classList.toggle('is-active', b === el));
      $$('[data-pane-id]').forEach(p => p.hidden = p.dataset.paneId !== el.dataset.pane);
      return;
    }
    if (up('[data-lupa]')) { const h = $('#lupa-hint'); h.hidden = !h.hidden; return; }
    if ((el = up('.pw-toggle'))) {
      const i = $('input', el.parentElement), show = i.type === 'password';
      i.type = show ? 'text' : 'password'; el.classList.toggle('is-shown', show); return;
    }
    if ((el = up('[data-menu]'))) {
      const dd = $('.user-dropdown'); dd.hidden = !dd.hidden;
      el.setAttribute('aria-expanded', String(!dd.hidden)); return;
    }
    if ((el = up('.multi-btn'))) {
      const l = $('.multi-list', el.parentElement); l.hidden = !l.hidden;
      el.setAttribute('aria-expanded', String(!l.hidden)); return;
    }
    if ((el = up('[data-flash-x]'))) el.closest('.flash').remove();
  });

  document.addEventListener('change', e => {
    const t = e.target, w = t.closest('[data-multi]');
    if (w && t.type === 'checkbox') {          // maksimal 2 pengajar per kelas
      if ($$('input:checked', w).length > 2) t.checked = false;
      syncMulti(w);
    }
    if (t.matches('[data-auto-hari]') && t.value && t.form.elements.hari) {   // hari otomatis dari tanggal
      t.form.elements.hari.value = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'][new Date(t.value + 'T00:00').getDay()];
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') $$('.modal:not([hidden])').forEach(closeM);
  });
  setTimeout(() => $$('.flash').forEach(f => f.remove()), 6000);
})();