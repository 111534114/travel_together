(() => {
  // 系統導覽：點側邊欄的「系統導覽」，一步一步介紹網站有哪些功能。每一步會把畫面上對應的位置亮起來。
  // 步驟是依「這一頁實際有哪些導覽項目」動態組出來的，訪客跟會員看到的內容不一樣，找不到的項目就直接跳過。
  const NAV_STEPS = [
    ['公開行程', '看看其他人公開分享的行程，覺得不錯可以直接複製來改——這是我們最大的亮點，先逛逛大家都在排什麼行程吧！'],
    ['首頁', '回到首頁。上方的搜尋面板可以查住宿、機票、高鐵／火車票。'],
    ['我的旅程', '建立旅程、安排每天的行程、邀請旅伴一起編輯。'],
    ['我的收藏', '在住宿、機票、車票按愛心收藏的項目都會集中在這裡。'],
    ['探索景點', '瀏覽景點、看排行與評價，並能直接加入你的行程。'],
    ['探索餐廳', '找旅途中想吃的餐廳。'],
    ['探索住宿', '瀏覽站內收錄的住宿。'],
    ['公告事項', '網站的最新消息與公告。'],
    ['目的地天氣', '查看熱門目的地的天氣預報。'],
    ['尋找旅伴', '發起揪團或加入別人的行程，找到一起出發的朋友。'],
    ['旅遊相簿', '旅行回來後，把照片分享到相簿。'],
    ['個人資料', '修改個人資料、通知偏好與帳號設定。'],
    ['免費註冊', '註冊會員後可以建立旅程、收藏、揪團。'],
  ];

  let overlay = null;
  let steps = [];
  let index = 0;
  let playing = true;   // 自動播放：每一步停留幾秒就換下一步，可以暫停
  let timer = null;
  const stepDelay = (step) => 3500 + step.text.length * 70;  // 字多的步驟多停一下

  function visible(element) {
    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function buildSteps() {
    const list = [];
    const links = Array.from(document.querySelectorAll('.member-sidenav a.side-link'));
    const addedNames = new Set();
    function addNavStep(name) {
      const entry = NAV_STEPS.find(([stepName]) => stepName === name);
      if (!entry) return;
      const link = links.find((a) => a.textContent.trim() === name);
      if (link && visible(link)) { list.push({ target: link, title: name, text: entry[1] }); addedNames.add(name); }
    }
    // 「公開行程」是我們最大的亮點，不管這頁有沒有搜尋面板，都讓它當整個導覽的第一步
    addNavStep('公開行程');
    const searchTabs = document.querySelector('.search-tabs');
    if (searchTabs) list.push({ target: searchTabs, title: '搜尋面板', text: '在這裡切換「住宿」「機票」「高鐵／火車票」，填好條件就能查詢。' });
    const searchCard = document.querySelector('.booking-search-card');
    if (searchCard) list.push({ target: searchCard, title: '搜尋條件', text: '修改目的地、日期、人數後按「搜尋」。機票可以選單程或來回，住宿可以選房間數、大人與小孩。' });
    const sidebar = document.querySelector('.results-sidebar');
    if (sidebar) list.push({ target: sidebar, title: '篩選與排序', text: '用價格、星級、設施等條件縮小範圍。' });
    NAV_STEPS.forEach(([name, text]) => {
      if (addedNames.has(name)) return;
      const link = links.find((a) => a.textContent.trim() === name);
      if (link && visible(link)) list.push({ target: link, title: name, text });
    });
    const bell = document.getElementById('memberNotificationBell');
    if (bell && visible(bell)) list.push({ target: bell, title: '通知', text: '旅程邀請、留言回覆等通知會出現在這裡。' });
    const font = document.querySelector('.font-size-control');
    if (font && visible(font)) list.push({ target: font, title: '字體大小', text: '覺得字太小或太大，可以在這裡調整，下次打開網站會記住。' });
    const language = document.querySelector('.language-select');
    if (language && visible(language)) list.push({ target: language, title: '語言', text: '可以把網站切換成英文。' });
    if (!list.length) list.push({ target: null, title: '系統導覽', text: '請從左側選單開始探索網站的功能。' });
    return list;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function clearTimer() { if (timer) { clearTimeout(timer); timer = null; } }

  function schedule() {
    clearTimer();
    if (!overlay) return;
    const bar = overlay.querySelector('.tour-progress');
    bar.style.transition = 'none'; bar.style.width = '0';
    if (!playing) return;
    const delay = stepDelay(steps[index]);
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.transition = `width ${delay}ms linear`; bar.style.width = '100%'; }));
    timer = setTimeout(() => go(1), delay);  // 最後一步播完就自動結束
  }

  function setPlaying(value) {
    playing = value;
    if (overlay) overlay.querySelector('[data-tour-play]').textContent = playing ? '暫停' : '繼續播放';
    schedule();
  }

  function close() {
    clearTimer();
    if (overlay) overlay.remove();
    overlay = null;
    document.removeEventListener('keydown', onKey);
    window.removeEventListener('resize', place);
  }

  function onKey(event) {
    if (event.key === 'Escape') close();
    if (event.key === 'ArrowRight') go(1);
    if (event.key === 'ArrowLeft') go(-1);
    if (event.key === ' ') { event.preventDefault(); setPlaying(!playing); }
  }

  function go(step) {
    const next = index + step;
    if (next < 0) return;
    if (next >= steps.length) { close(); return; }
    index = next;
    render();
  }

  function place() {
    if (!overlay) return;
    const spot = overlay.querySelector('.tour-spot');
    const card = overlay.querySelector('.tour-card');
    const target = steps[index].target;
    if (!target || !visible(target)) {
      spot.style.display = 'none';
      card.style.left = '50%'; card.style.top = '50%'; card.style.transform = 'translate(-50%, -50%)';
      return;
    }
    const rect = target.getBoundingClientRect();
    const pad = 6;
    spot.style.display = 'block';
    spot.style.left = rect.left - pad + 'px';
    spot.style.top = rect.top - pad + 'px';
    spot.style.width = rect.width + pad * 2 + 'px';
    spot.style.height = rect.height + pad * 2 + 'px';
    card.style.transform = 'none';
    const cardWidth = card.offsetWidth;
    const cardHeight = card.offsetHeight;
    let left = rect.right + 16;
    let top = rect.top;
    if (left + cardWidth > window.innerWidth - 12) {  // 右邊放不下就放在下方(或上方)
      left = Math.max(12, Math.min(rect.left, window.innerWidth - cardWidth - 12));
      top = rect.bottom + 14;
      if (top + cardHeight > window.innerHeight - 12) top = Math.max(12, rect.top - cardHeight - 14);
    }
    top = Math.max(12, Math.min(top, window.innerHeight - cardHeight - 12));
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  }

  function render() {
    const step = steps[index];
    if (step.target) step.target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    overlay.querySelector('.tour-title').textContent = step.title;
    overlay.querySelector('.tour-text').textContent = step.text;
    overlay.querySelector('.tour-count').textContent = `${index + 1} / ${steps.length}`;
    overlay.querySelector('[data-tour-prev]').disabled = index === 0;
    overlay.querySelector('[data-tour-next]').textContent = index === steps.length - 1 ? '完成' : '下一步';
    requestAnimationFrame(place);
    schedule();
  }

  function start() {
    close();
    try { localStorage.setItem('siteTourSeen', '1'); } catch (error) { /* 無痕模式存不起來就每次都會再跳出，不影響使用 */ }
    document.body.classList.remove('nav-open');
    steps = buildSteps();
    index = 0;
    playing = true;
    overlay = el('div', 'tour-overlay');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', '系統導覽');
    const spot = el('div', 'tour-spot');
    const card = el('div', 'tour-card');
    card.append(el('b', 'tour-title'), el('p', 'tour-text'));
    const footer = el('div', 'tour-footer');
    footer.append(el('span', 'tour-count'));
    const actions = el('div', 'tour-actions');
    const skip = el('button', 'tour-btn', '結束'); skip.type = 'button'; skip.addEventListener('click', close);
    const play = el('button', 'tour-btn', '暫停'); play.type = 'button'; play.dataset.tourPlay = ''; play.addEventListener('click', () => setPlaying(!playing));
    const prev = el('button', 'tour-btn', '上一步'); prev.type = 'button'; prev.dataset.tourPrev = ''; prev.addEventListener('click', () => go(-1));
    const next = el('button', 'tour-btn tour-primary', '下一步'); next.type = 'button'; next.dataset.tourNext = ''; next.addEventListener('click', () => go(1));
    actions.append(play, prev, next);
    footer.appendChild(actions);
    card.appendChild(footer);
    const progress = el('div', 'tour-progress-track'); progress.appendChild(el('div', 'tour-progress'));
    card.appendChild(progress);
    // 隨時可以按的結束鈕：固定在畫面右上角，不跟著說明卡移動
    const exit = el('button', 'tour-exit', '✕ 結束導覽'); exit.type = 'button'; exit.addEventListener('click', close);
    overlay.append(spot, card, exit);
    overlay.addEventListener('mousedown', (event) => { if (event.target === overlay) close(); });
    document.body.appendChild(overlay);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', place);
    render();
  }

  // 第一次打開網站(這個瀏覽器還沒看過導覽)就自動跳出；看過之後不再出現，想再看可以點側邊欄的「重新導覽」
  let seen = true;
  try { seen = localStorage.getItem('siteTourSeen') === '1'; } catch (error) { seen = true; }
  if (!seen && document.querySelector('.member-sidenav')) setTimeout(start, 900);

  document.addEventListener('click', (event) => {
    if (event.target.closest && event.target.closest('[data-tour-start]')) { event.preventDefault(); start(); }
  });
})();
