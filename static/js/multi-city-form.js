(() => {
  // 多座城市結果頁的搜尋表單：新增/移除航班、出發地自動接上一段的目的地、切換行程類型
  // 每一段中間的 ⇄：交換這一段的出發地與目的地(交換後下一段的出發地不再是「自動帶入」，避免被蓋掉)
  document.addEventListener('click', (event) => {
    const swap = event.target.closest('[data-mc-swap], [data-swap-a]');
    if (!swap) return;
    let a, b;
    if (swap.dataset.swapA) { a = document.getElementById(swap.dataset.swapA); b = document.getElementById(swap.dataset.swapB); }
    else { const leg = swap.closest('.mc-leg'); a = leg.querySelector('.mc-from'); b = leg.querySelector('.mc-to'); }
    if (!a || !b) return;
    const t = a.value; a.value = b.value; b.value = t;
    if (b.classList.contains('mc-to')) b.dispatchEvent(new Event('change', { bubbles: true }));
  });

  const form = document.getElementById('mcForm');
  if (!form) return;
  const legsBox = document.getElementById('mcLegs');
  const addBtn = document.getElementById('mcAdd');
  const countInput = document.getElementById('mcLegsCount');
  const MAX_LEGS = 6;

  // 每一段的欄位名稱要跟後端對上(from1/to1/date1、from2⋯)，新增或刪除後重新編號
  const renumber = () => {
    const legs = legsBox.querySelectorAll('.mc-leg');
    legs.forEach((leg, i) => {
      leg.querySelector('.mc-badge').textContent = i + 1;
      leg.querySelector('.mc-from').name = 'from' + (i + 1);
      leg.querySelector('.mc-to').name = 'to' + (i + 1);
      leg.querySelector('.mc-date').name = 'date' + (i + 1);
      leg.querySelector('.mc-remove').hidden = legs.length <= 2;
    });
    countInput.value = legs.length;
    addBtn.disabled = legs.length >= MAX_LEGS;
  };
  const template = (() => {
    const all = legsBox.querySelectorAll('.mc-leg');
    const t = all[all.length - 1].cloneNode(true);
    t.querySelectorAll('input').forEach((input) => { input.value = ''; });
    return t;
  })();

  // 上一段的目的地填好(或換掉)，下一段的出發地跟著帶入；下一段的出發地如果是使用者自己填的，就不去動它
  legsBox.addEventListener('change', (event) => {
    if (!event.target.classList.contains('mc-to')) return;
    const all = Array.from(legsBox.querySelectorAll('.mc-leg'));
    const next = all[all.indexOf(event.target.closest('.mc-leg')) + 1];
    if (!next) return;
    const nextFrom = next.querySelector('.mc-from'), value = event.target.value.trim();
    if (value && (!nextFrom.value.trim() || nextFrom.dataset.auto === '1')) { nextFrom.value = value; nextFrom.dataset.auto = '1'; }
  });
  legsBox.addEventListener('input', (event) => { if (event.target.classList.contains('mc-from')) delete event.target.dataset.auto; });

  legsBox.addEventListener('click', (event) => {
    const button = event.target.closest('.mc-remove');
    if (!button) return;
    if (legsBox.querySelectorAll('.mc-leg').length <= 2) return;
    button.closest('.mc-leg').remove();
    renumber();
  });

  addBtn.addEventListener('click', () => {
    const legs = legsBox.querySelectorAll('.mc-leg');
    if (legs.length >= MAX_LEGS) return;
    const clone = template.cloneNode(true);
    // 新增的這一段，出發地直接接上一段的目的地
    const previousTo = legs[legs.length - 1].querySelector('.mc-to').value.trim();
    if (previousTo) { const f = clone.querySelector('.mc-from'); f.value = previousTo; f.dataset.auto = '1'; }
    legsBox.appendChild(clone);
    renumber();
    const next = clone.querySelector(previousTo ? '.mc-to' : '.mc-from');
    if (next) next.focus();
  });

  // 送出前：後面幾段沒填出發地，就用上一段的目的地
  form.addEventListener('submit', () => {
    const legs = legsBox.querySelectorAll('.mc-leg');
    legs.forEach((leg, i) => {
      const from = leg.querySelector('.mc-from');
      if (!from.value.trim() && i > 0) from.value = legs[i - 1].querySelector('.mc-to').value.trim();
    });
  });
  renumber();
})();
