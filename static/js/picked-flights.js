(() => {
  // 多座城市：每一段挑一班，下方累計「已選航班」與合計；每段各自去航空公司/比價網站訂票
  const box = document.getElementById('pickedSummary');
  if (!box) return;
  const list = document.getElementById('pickedList'), totalEl = document.getElementById('pickedTotal'), countEl = document.getElementById('pickedCount');
  const legsTotal = new Set(Array.from(document.querySelectorAll('[data-pick-leg]')).map((c) => c.dataset.pickLeg)).size;
  const picked = new Map();  // 段 -> 卡片
  const fmt = (n) => (window.siteCurrency ? window.siteCurrency.fmt(n) : 'NT$ ' + Math.round(n).toLocaleString('zh-TW'));
  const render = () => {
    list.textContent = '';
    let total = 0;
    Array.from(picked.keys()).sort((a, b) => a - b).forEach((leg) => {
      const d = picked.get(leg).dataset, price = Number(d.pickPrice) || 0;
      total += price;
      const li = document.createElement('li');
      const info = document.createElement('div'); info.className = 'picked-info';
      const route = document.createElement('b'); route.textContent = '第 ' + leg + ' 段　' + d.pickRoute + (d.pickDate ? '｜' + d.pickDate : '');
      const label = document.createElement('span'); label.textContent = d.pickLabel;
      info.append(route, label);
      const price_ = document.createElement('span'); price_.className = 'picked-price'; price_.textContent = fmt(price);
      li.append(info, price_);
      if (d.pickHref) {
        const a = document.createElement('a'); a.className = 'picked-book'; a.href = d.pickHref; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '前往訂票';
        if (d.pickFlights) a.dataset.flights = d.pickFlights;  // 訂完回到這個頁面時，會問「是否加入旅程」
        li.appendChild(a);
      }
      list.appendChild(li);
    });
    totalEl.textContent = fmt(total);
    countEl.textContent = '已選 ' + picked.size + ' / ' + legsTotal + ' 段' + (picked.size < legsTotal ? '，還有 ' + (legsTotal - picked.size) + ' 段沒選' : '');
    box.hidden = picked.size === 0;
  };
  const mark = (card, on) => {
    card.classList.toggle('is-picked', on);
    const b = card.querySelector('[data-pick-toggle]');
    b.setAttribute('aria-pressed', String(on));
    b.textContent = on ? '重新選擇' : '加入已選航班';
    // 這一段選好了就只留選中的那班，其他收起來；按「重新選擇」才會全部展開
    const legBox = card.closest('.flight-leg');
    if (legBox) legBox.classList.toggle('leg-picked', on);
  };
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-pick-toggle]');
    if (!btn) return;
    const card = btn.closest('[data-pick-leg]'), leg = card.dataset.pickLeg;
    const prev = picked.get(leg);
    if (prev) mark(prev, false);
    if (prev === card) picked.delete(leg); else { picked.set(leg, card); mark(card, true); }
    render();
    if (picked.get(leg) === card) {
      // 選好後直接帶到下一個還沒選的航段，不用自己往下滑
      const legBoxes = Array.from(document.querySelectorAll('.flight-leg'));
      const next = legBoxes.slice(legBoxes.indexOf(card.closest('.flight-leg')) + 1).find((el) => !el.classList.contains('leg-picked'));
      if (next) next.scrollIntoView({ block: 'start', behavior: 'smooth' });
    } else {
      card.closest('.flight-leg').scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
  });
  document.getElementById('pickedClear').addEventListener('click', () => { picked.forEach((c) => mark(c, false)); picked.clear(); render(); });
  if (window.siteCurrency && window.siteCurrency.onChange) window.siteCurrency.onChange(render);
})();
