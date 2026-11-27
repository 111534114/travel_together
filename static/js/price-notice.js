(() => {
  // 按下「搜尋」時跳出的提醒：網站上的價格只是參考，付款前要到官網或訂票網站做最後確認。
  // 使用者按「我知道了」之後才繼續搜尋；每次按搜尋都會先提醒，勾「不再顯示」才不會再跳出。
  const TEXT = {
    hotel: {
      title: '住宿價格僅供參考',
      lead: '這裡顯示的價格是從 Google 等來源整理的參考報價，不是最終的訂房價格。',
      points: [
        '房價、早餐與取消政策會依房型、人數、日期不同而改變，也可能隨時調整。',
        '價格不一定已含稅費(稅金、服務費、住宿稅)，是否包含依各訂房網站而定，結帳時的最終金額可能更高。',
        '房間數量有限，顯示有房不代表一定訂得到。',
        '請務必點進訂房網站或飯店官網，確認最新價格與房況後再付款。',
      ],
    },
    flight: {
      title: '機票價格僅供參考',
      lead: '這裡顯示的票價是從 Google 等來源整理的參考報價，不是最終的購票價格。',
      points: [
        '票價與座位會隨時變動，行李、稅金、手續費與退改規定也可能不同。',
        '請務必點進航空公司官網或訂票網站，確認最新價格與航班資訊後再付款。',
      ],
    },
  };
  const sessionKeyOf = (kind) => 'priceNoticeShown:' + kind, foreverKeyOf = (kind) => 'priceNoticeHidden:' + kind;
  const read = (storage, key) => { try { return storage.getItem(key); } catch (e) { return null; } };
  const write = (storage, key, value) => { try { storage.setItem(key, value); } catch (e) { /* 無痕模式存不起來就每次都提醒，不影響使用 */ } };
  const el = (tag, className, text) => { const n = document.createElement(tag); if (className) n.className = className; if (text !== undefined) n.textContent = text; return n; };

  function ask(kind, proceed) {
    const info = TEXT[kind];
    const overlay = el('div', 'pn-overlay');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'pnTitle');
    const box = el('div', 'pn-box');
    const title = el('h2', 'pn-title', info.title); title.id = 'pnTitle';
    const list = el('ul', 'pn-list');
    info.points.forEach((t) => list.appendChild(el('li', '', t)));
    const hide = el('label', 'pn-hide');
    const check = el('input'); check.type = 'checkbox';
    hide.append(check, document.createTextNode(' 不再顯示這個提醒'));
    const ok = el('button', 'pn-ok', '我知道了，繼續搜尋'); ok.type = 'button';
    box.append(title, el('p', 'pn-lead', info.lead), list, hide, ok);
    overlay.appendChild(box);
    const close = (go) => {
      if (check.checked) write(window.localStorage, foreverKeyOf(kind), '1');
      overlay.remove();
      document.removeEventListener('keydown', onKey);
      if (go) proceed();
    };
    const onKey = (e) => { if (e.key === 'Escape') close(false); };  // 按 Esc 或點旁邊只是關閉，不送出搜尋
    ok.addEventListener('click', () => close(true));
    overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(false); });
    document.body.appendChild(overlay);
    document.addEventListener('keydown', onKey);
    ok.focus();
  }

  // 這個搜尋按鈕是機票還是住宿(火車票不用提醒)：首頁看目前選的分頁，結果頁看表單的種類
  function kindOf(button) {
    const form = button.closest('form');
    if (form && form.classList.contains('booking-search-form--hotel')) return 'hotel';
    if (form && (form.classList.contains('booking-search-form--flight') || form.classList.contains('booking-search-form--multicity'))) return 'flight';
    const tab = document.querySelector('.search-tab.active');
    const name = tab && tab.dataset.tab;
    return name === 'hotel' || name === 'flight' ? name : null;
  }

  let bypass = false;
  // 用 capture 階段搶在原本的送出邏輯之前：先問，使用者同意後再把同一次點擊放行
  document.addEventListener('click', (event) => {
    if (bypass) return;
    const button = event.target instanceof Element ? event.target.closest('.search-submit, .booking-search-submit, #mcSubmit') : null;
    if (!button || button.disabled) return;
    const kind = kindOf(button);
    if (!kind) return;
    if (read(window.localStorage, foreverKeyOf(kind)) === '1') return;  // 每次按搜尋都先問，除非使用者勾了「不再顯示」
    event.preventDefault();
    event.stopImmediatePropagation();
    ask(kind, () => { bypass = true; try { button.click(); } finally { bypass = false; } });
  }, true);
})();
