(() => {
  // 點「選擇」後訂票頁在新分頁打開，這個分頁跳出「訂完了嗎？」。
  // 使用者自己按「我已訂票」才會把這班機票寫進旅程，避免誤點就污染行程。
  let panel = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function closePanel() {
    if (panel) panel.remove();
    panel = null;
  }

  function openPanel(title) {
    closePanel();
    panel = el('div', 'ftc-panel');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', title);
    panel.appendChild(el('b', 'ftc-title', title));
    document.body.appendChild(panel);
    return panel;
  }

  function flightLines(flights) {
    const list = el('ul', 'ftc-flights');
    flights.forEach((f) => {
      const time = f.start_time ? `${f.start_time}${f.end_time ? '–' + f.end_time : ''}` : '';
      list.appendChild(el('li', '', `${f.date}　${f.title}${time ? '　' + time : ''}`));
    });
    return list;
  }

  function button(label, className, onClick) {
    const btn = el('button', className, label);
    btn.type = 'button';
    btn.addEventListener('click', onClick);
    return btn;
  }

  function showMessage(title, message, link) {
    const box = openPanel(title);
    box.appendChild(el('p', 'ftc-text', message));
    const actions = el('div', 'ftc-actions');
    if (link) {
      const a = el('a', 'ftc-btn ftc-primary', link.label);
      a.href = link.href;
      a.target = link.newTab ? '_blank' : '_self';
      a.rel = 'noopener';
      actions.appendChild(a);
    }
    actions.appendChild(button('關閉', 'ftc-btn', closePanel));
    box.appendChild(actions);
  }

  function showAsk(flights) {
    const box = openPanel('訂票頁面已在新分頁打開');
    box.appendChild(el('p', 'ftc-text', '訂完了嗎？只有你按下「我已訂票」，才會把下面的航班加入旅程。'));
    box.appendChild(flightLines(flights));
    const actions = el('div', 'ftc-actions');
    actions.appendChild(button('我已訂票，加入旅程', 'ftc-btn ftc-primary', () => chooseTrip(flights)));
    actions.appendChild(button('還沒，之後再說', 'ftc-btn', closePanel));
    box.appendChild(actions);
  }

  async function chooseTrip(flights) {
    const dates = [...new Set(flights.map((f) => f.date))].join(',');
    let response;
    try {
      response = await fetch('/member/api/flight-trips?dates=' + encodeURIComponent(dates), {
        credentials: 'same-origin', headers: { Accept: 'application/json' },
      });
    } catch (error) {
      showMessage('無法連線', '網路發生問題，請稍後再試。');
      return;
    }
    if (response.status === 401) {
      showMessage('請先登入會員', '加入旅程需要會員登入。登入後回到這個頁面，再按一次「選擇」並確認訂票即可。',
        { label: '前往登入', href: '/login', newTab: true });
      return;
    }
    if (!response.ok) {
      showMessage('讀取旅程失敗', '請稍後再試。');
      return;
    }
    const { trips } = await response.json();
    if (!trips.length) {
      showMessage('還沒有可編輯的旅程', '你目前沒有可以編輯的旅程，請先建立一個旅程再回來加入。',
        { label: '建立旅程', href: '/member/trips/new', newTab: true });
      return;
    }

    const box = openPanel('加入哪一趟旅程？');
    box.appendChild(flightLines(flights));
    const select = el('select', 'ftc-select');
    trips.forEach((trip) => {
      const option = el('option', '', `${trip.trip_name}（${trip.start_date} ～ ${trip.end_date}）${trip.fits ? '' : '　日期不在旅程內'}`);
      option.value = trip.trip_id;
      option.disabled = !trip.fits;
      select.appendChild(option);
    });
    const firstFit = trips.findIndex((trip) => trip.fits);
    if (firstFit === -1) {
      box.appendChild(el('p', 'ftc-text', '你的旅程日期都沒有涵蓋這班機票的日期，請先調整旅程日期。'));
    } else {
      select.selectedIndex = firstFit;
      box.appendChild(select);
    }
    const actions = el('div', 'ftc-actions');
    if (firstFit !== -1) {
      const confirm = button('確認加入', 'ftc-btn ftc-primary', async () => {
        confirm.disabled = true;
        await addToTrip(flights, Number(select.value));
      });
      actions.appendChild(confirm);
    }
    actions.appendChild(button('取消', 'ftc-btn', closePanel));
    box.appendChild(actions);
  }

  async function addToTrip(flights, tripId) {
    try {
      const response = await fetch('/member/api/flights/add-to-trip', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ trip_id: tripId, flights }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showMessage('加入失敗', data.error || '請稍後再試。');
        return;
      }
      const message = data.added
        ? `已將 ${data.added} 筆航班加入「${data.trip_name}」${data.skipped ? `（另有 ${data.skipped} 筆已存在，略過）` : ''}。`
        : '這些航班已經在這趟旅程裡了，沒有重複加入。';
      showMessage('完成', message, { label: '查看旅程', href: data.trip_url });
    } catch (error) {
      showMessage('無法連線', '網路發生問題，請稍後再試。');
    }
  }

  document.addEventListener('click', (event) => {
    const link = event.target instanceof Element ? event.target.closest('a[data-flights]') : null;
    if (!link) return;
    let flights;
    try { flights = JSON.parse(link.dataset.flights); } catch (error) { return; }
    if (!Array.isArray(flights) || !flights.length) return;
    setTimeout(() => showAsk(flights), 400);
  });
})();
