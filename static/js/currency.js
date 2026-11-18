(() => {
  // 幣別選單：價格預設是台幣；選了別的貨幣，頁面上標了 data-twd 的金額會用匯率換算成那種貨幣顯示(約略價，實際以訂房／訂票網站為準)。
  const KEY = 'siteCurrency';
  const COMMON = ['TWD', 'USD', 'JPY', 'EUR', 'KRW', 'CNY', 'HKD', 'GBP', 'SGD', 'THB', 'AUD', 'MYR'];
  const state = { code: 'TWD', rates: { TWD: 1 }, names: { TWD: '新台幣' }, loaded: false, listeners: [] };
  try { state.code = localStorage.getItem(KEY) || 'TWD'; } catch (error) { state.code = 'TWD'; }

  function formatter(code, value) {
    const digits = value < 100 && !['JPY', 'KRW', 'VND', 'IDR', 'CLP', 'PYG', 'UGX', 'ISK', 'HUF'].includes(code) ? 2 : 0;
    try {
      return new Intl.NumberFormat('zh-TW', { style: 'currency', currency: code, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
    } catch (error) {
      return `${code} ${Math.round(value).toLocaleString('zh-TW')}`;
    }
  }

  // 把台幣金額 twd 換成目前選的貨幣；沒有匯率或選台幣就維持 NT$
  function fmt(twd) {
    const rate = state.rates[state.code];
    if (state.code === 'TWD' || !rate) return `NT$ ${Math.round(twd).toLocaleString('zh-TW')}`;
    return '約 ' + formatter(state.code, twd * rate);
  }

  function convertPage() {
    document.querySelectorAll('[data-twd]').forEach((node) => {
      const twd = Number(node.dataset.twd);
      if (Number.isFinite(twd)) node.textContent = fmt(twd);
    });
  }

  function updateButtons() {
    document.querySelectorAll('[data-currency-open]').forEach((button) => {
      button.textContent = `幣別　${state.code}`;
    });
  }

  function setCurrency(code) {
    state.code = code;
    try { localStorage.setItem(KEY, code); } catch (error) { /* 無痕模式存不起來就只在這一頁有效 */ }
    convertPage();
    updateButtons();
    state.listeners.forEach((fn) => fn());
  }

  async function load() {
    if (state.loaded) return;
    try {
      const cached = JSON.parse(sessionStorage.getItem('siteCurrencyData') || 'null');
      if (cached && Date.now() - cached.at < 6 * 3600 * 1000) { Object.assign(state, { rates: cached.rates, names: cached.names, loaded: true }); return; }
    } catch (error) { /* 忽略壞掉的快取 */ }
    try {
      const response = await fetch('/api/currencies', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('匯率載入失敗');
      const data = await response.json();
      Object.assign(state, { rates: data.rates, names: data.names, loaded: true });
      try { sessionStorage.setItem('siteCurrencyData', JSON.stringify({ at: Date.now(), rates: data.rates, names: data.names })); } catch (error) { /* ignore */ }
    } catch (error) {
      state.loaded = false;
    }
  }

  // 視窗：「常用貨幣」+「所有貨幣」三欄排列，上面有搜尋框
  let overlay = null;
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function closeModal() {
    if (overlay) overlay.remove();
    overlay = null;
  }
  async function openModal() {
    closeModal();
    await load();
    overlay = el('div', 'cur-backdrop');
    overlay.addEventListener('mousedown', (event) => { if (event.target === overlay) closeModal(); });
    const dialog = el('div', 'cur-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-label', '選擇幣別');
    const head = el('div', 'cur-head');
    head.appendChild(el('b', 'cur-title', '幣別'));
    const close = el('button', 'cur-close', '×');
    close.type = 'button'; close.setAttribute('aria-label', '關閉'); close.addEventListener('click', closeModal);
    head.appendChild(close);
    const search = el('input', 'cur-search');
    search.type = 'search'; search.placeholder = '搜尋貨幣名稱或代碼（例如 日圓、USD）'; search.setAttribute('aria-label', '搜尋貨幣');
    const body = el('div', 'cur-body');
    const note = el('p', 'cur-note', '價格預設是台幣；選其他貨幣會用匯率換算，只是參考價，實際金額以訂房、訂票網站收款為準。');

    const codes = Object.keys(state.rates).sort();
    const row = (code) => {
      const button = el('button', 'cur-item' + (code === state.code ? ' active' : ''));
      button.type = 'button';
      button.dataset.search = (code + ' ' + (state.names[code] || '')).toLowerCase();
      button.appendChild(el('b', '', code));
      button.append(` - ${state.names[code] || code}`);
      button.addEventListener('click', () => { setCurrency(code); closeModal(); });
      return button;
    };
    const section = (title, list) => {
      const box = el('div', 'cur-section');
      box.appendChild(el('h3', '', title));
      const grid = el('div', 'cur-grid');
      list.forEach((code) => grid.appendChild(row(code)));
      box.appendChild(grid);
      return box;
    };
    const common = section('常用貨幣', COMMON.filter((code) => state.rates[code]));
    const all = section('所有貨幣', ['TWD', ...codes.filter((code) => code !== 'TWD')]);
    body.append(common, all);
    search.addEventListener('input', () => {
      const keyword = search.value.trim().toLowerCase();
      common.hidden = keyword !== '';
      all.querySelectorAll('.cur-item').forEach((item) => { item.hidden = keyword !== '' && !item.dataset.search.includes(keyword); });
    });
    dialog.append(head, search, note, body);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    search.focus();
  }

  document.addEventListener('click', (event) => {
    if (event.target.closest && event.target.closest('[data-currency-open]')) { event.preventDefault(); openModal(); }
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeModal(); });

  window.siteCurrency = { fmt, onChange: (fn) => state.listeners.push(fn), get code() { return state.code; } };

  load().then(() => { convertPage(); updateButtons(); });
  updateButtons();
})();
