(() => {
  // 愛心收藏改成不重新載入頁面：按下去只更新愛心本身，頁面不會跳回最上面、搜尋結果也不會重跑(重跑機票會用掉 API 額度)。
  function paint(button, saved) {
    button.classList.toggle('is-saved', saved);
    const label = saved ? '取消收藏' : '加入我的收藏';
    button.setAttribute('aria-label', label);
    button.title = label;
    const glyph = button.querySelector('span');
    if (glyph) glyph.textContent = saved ? '♥' : '♡';
  }

  async function post(url, options) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || '收藏失敗，請稍後再試。');
    return data;
  }

  // 資料庫裡的住宿／機票／火車：原本就是表單，攔下來改成背景送出
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest && event.target.closest('.booking-save-form');
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector('.booking-heart');
    const actionInput = form.querySelector('input[name="action"]');
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      const data = await post(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'fetch' } });
      paint(button, data.saved);
      if (data.favorite_id) {
        // 剛收藏的即時(TDX)車次：後端存好之後有了車次 id，之後這顆愛心就能走一般的「取消收藏」
        form.action = '/member/booking-favorites/train/' + data.favorite_id;
        let action = form.querySelector('input[name="action"]');
        if (!action) { action = document.createElement('input'); action.type = 'hidden'; action.name = 'action'; form.appendChild(action); }
        action.value = 'remove';
      } else if (actionInput) {
        actionInput.value = data.saved ? 'remove' : 'save';
      }
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
    }
  });

  // 即時查詢結果(Google 機票／住宿)：沒有資料庫 id，直接把摘要送出去存
  document.addEventListener('click', async (event) => {
    const button = event.target.closest && event.target.closest('[data-live-fav]');
    if (!button || button.disabled) return;
    event.preventDefault();
    event.stopPropagation();
    const saved = button.dataset.saved === '1';
    button.disabled = true;
    try {
      const fav = JSON.parse(button.dataset.fav);
      const data = await post('/member/booking-favorites/live', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...fav, csrf: button.dataset.csrf, action: saved ? 'remove' : 'save' }),
      });
      button.dataset.saved = data.saved ? '1' : '0';
      paint(button, data.saved);
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
    }
  }, true);
})();
