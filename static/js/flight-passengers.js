(() => {
  // 乘客與艙等小視窗：成人 ≥1、成人+兒童 ≤9、嬰兒 ≤ 成人；經濟艙(預設)不送 cabin 參數
  const MAX = 9;
  const NAMES = { '': '經濟艙' };
  function init(root) {
    if (root._fp) return root._fp;
    const q = (sel) => root.querySelector(sel);
    const hid = (name) => q('input[name="' + name + '"]');
    const state = {
      adults: Math.max(1, parseInt(root.dataset.adults, 10) || 1),
      children: Math.max(0, parseInt(root.dataset.children, 10) || 0),
      infants: Math.max(0, parseInt(root.dataset.infants, 10) || 0),
      cabin: root.dataset.cabin || '',
    };
    const panel = q('.fp-panel'), toggle = q('.fp-toggle'), note = q('.fp-note'), cabinSel = q('.fp-cabin');
    const clamp = () => {
      state.adults = Math.min(Math.max(state.adults, 1), MAX);
      state.children = Math.min(Math.max(state.children, 0), MAX - state.adults);
      state.infants = Math.min(Math.max(state.infants, 0), state.adults);
    };
    const render = () => {
      clamp();
      ['adults', 'children', 'infants'].forEach((k) => {
        q('[data-fp-val="' + k + '"]').textContent = state[k];
        hid(k).value = state[k];
      });
      hid('pax').value = state.adults + state.children;
      const cabin = hid('cabin');
      cabin.value = state.cabin; cabin.disabled = !state.cabin;
      cabinSel.value = state.cabin;
      const total = state.adults + state.children;
      q('[data-fp-plus="adults"]').disabled = total >= MAX;
      q('[data-fp-plus="children"]').disabled = total >= MAX;
      q('[data-fp-plus="infants"]').disabled = state.infants >= state.adults;
      q('[data-fp-minus="adults"]').disabled = state.adults <= 1;
      q('[data-fp-minus="children"]').disabled = state.children <= 0;
      q('[data-fp-minus="infants"]').disabled = state.infants <= 0;
      note.hidden = total < MAX;
      let text = state.adults + ' 位成人';
      if (state.children) text += '、' + state.children + ' 位兒童';
      if (state.infants) text += '、' + state.infants + ' 位嬰兒';
      q('.fp-summary').textContent = text + '・' + (NAMES[state.cabin] || state.cabin);
    };
    root.addEventListener('click', (e) => {
      const plus = e.target.closest('[data-fp-plus]'), minus = e.target.closest('[data-fp-minus]');
      if (plus) { state[plus.dataset.fpPlus] += 1; render(); }
      else if (minus) { state[minus.dataset.fpMinus] -= 1; render(); }
    });
    cabinSel.addEventListener('change', () => { state.cabin = cabinSel.value; render(); });
    toggle.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      toggle.setAttribute('aria-expanded', String(!panel.hidden));
    });
    document.addEventListener('click', (e) => {
      if (!root.contains(e.target) && !panel.hidden) { panel.hidden = true; toggle.setAttribute('aria-expanded', 'false'); }
    });
    root.addEventListener('keydown', (e) => { if (e.key === 'Escape') { panel.hidden = true; toggle.focus(); } });
    root._fp = {
      state,
      set(next) { Object.assign(state, next); render(); },
      params() {
        const p = { pax: String(state.adults + state.children), adults: String(state.adults), children: String(state.children), infants: String(state.infants) };
        if (state.cabin) p.cabin = state.cabin;
        return p;
      },
    };
    render();
    return root._fp;
  }
  const initAll = () => document.querySelectorAll('[data-fp]').forEach(init);
  window.flightPassengers = { init, initAll };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll); else initAll();
})();
