(() => {
  const bell = document.getElementById('memberNotificationBell');
  if (!bell) return;
  const launcher = document.getElementById('memberNotificationLauncher');
  const hideButton = document.getElementById('memberNotificationHide');
  const drawer = document.getElementById('memberNotificationDrawer');
  const backdrop = document.getElementById('memberNotificationBackdrop');
  const closeButton = document.getElementById('memberNotificationClose');
  const count = document.getElementById('memberNotificationCount');
  const summary = document.getElementById('memberNotificationSummary');
  const list = document.getElementById('memberNotificationList');
  const readAll = document.getElementById('memberNotificationReadAll');
  let dismissedKey = 'member-notifications-dismissed';
  let hideKey = null;
  let notifications = [];
  let total = 0;
  let lastFocus = null;

  function dismissedIds() {
    try { return new Set(JSON.parse(sessionStorage.getItem(dismissedKey) || '[]')); }
    catch { return new Set(); }
  }
  function rememberDismissed() {
    try {
      const ids = dismissedIds();
      notifications.forEach(item => ids.add(item.notification_id));
      sessionStorage.setItem(dismissedKey, JSON.stringify([...ids].slice(-100)));
    } catch { /* Storage may be unavailable; closing still works. */ }
  }
  function openDrawer() {
    if (!drawer.hidden) return;
    lastFocus = document.activeElement;
    drawer.hidden = false;
    backdrop.hidden = false;
    bell.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => drawer.classList.add('is-open'));
    closeButton.focus();
  }
  function closeDrawer() {
    if (drawer.hidden) return;
    rememberDismissed();
    drawer.classList.remove('is-open');
    drawer.hidden = true;
    backdrop.hidden = true;
    bell.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    (lastFocus || bell).focus();
  }
  async function markRead(id) {
    const response = await fetch(`/member/notifications/${id}/read`, {
      method: 'POST', headers: { Accept: 'application/json' }, credentials: 'same-origin'
    });
    if (!response.ok) throw new Error('無法更新通知，請稍後再試。');
    await refresh(false);
  }
  function render() {
    count.hidden = total === 0;
    count.textContent = total > 99 ? '99+' : String(total);
    summary.textContent = `未讀通知 ${total} 則`;
    readAll.disabled = total === 0;
    list.replaceChildren();
    if (!notifications.length) {
      const empty = document.createElement('p');
      empty.className = 'member-notification-empty';
      empty.textContent = '目前沒有新通知';
      list.append(empty);
      return;
    }
    notifications.forEach(item => {
      const article = document.createElement('article');
      article.className = 'member-notification-item';
      const title = document.createElement('h3'); title.textContent = item.title;
      const message = document.createElement('p'); message.textContent = item.message;
      const time = document.createElement('time'); time.textContent = item.created_at;
      const actions = document.createElement('div'); actions.className = 'member-notification-actions';
      const read = document.createElement('button'); read.type = 'button'; read.textContent = '標為已讀';
      read.addEventListener('click', async () => {
        try { await markRead(item.notification_id); }
        catch (error) { alert(error.message); }
      });
      actions.append(read);
      if (item.target_url && item.target_url.startsWith('/') && !item.target_url.startsWith('//')) {
        const view = document.createElement('button'); view.type = 'button'; view.textContent = '查看';
        view.addEventListener('click', async () => {
          try { await markRead(item.notification_id); window.location.assign(item.target_url); }
          catch (error) { alert(error.message); }
        });
        actions.append(view);
      }
      article.append(title, message, time, actions);
      list.append(article);
    });
  }
  // 按叉叉後鈴鐺收到右邊邊緣，只露出一小截，點一下就會回來
  function isTucked() { return launcher.classList.contains('is-tucked'); }
  function setTucked(tucked) {
    launcher.classList.toggle('is-tucked', tucked);
    bell.setAttribute('aria-label', tucked ? '顯示通知按鈕' : '查看通知');
    bell.title = tucked ? '顯示通知按鈕' : '查看通知';
  }
  async function refresh(autoOpen) {
    const response = await fetch('/member/notifications/unread', { credentials: 'same-origin', cache: 'no-store' });
    if (!response.ok) throw new Error('無法讀取通知。');
    const data = await response.json();
    dismissedKey = `member-notifications-dismissed:${data.login_id}`;
    hideKey = `member-notification-button-hidden:${data.login_id}`;
    try { setTucked(sessionStorage.getItem(hideKey) === '1'); }
    catch { setTucked(false); }
    launcher.hidden = false;
    notifications = data.notifications;
    total = data.total;
    render();
    if (autoOpen && !isTucked() && drawer.hidden && notifications.some(item => !dismissedIds().has(item.notification_id))) openDrawer();
  }
  bell.addEventListener('click', async () => {
    if (isTucked()) {
      setTucked(false);
      try { sessionStorage.removeItem(hideKey); } catch { /* Storage may be unavailable; the button still comes back. */ }
      return;
    }
    try { await refresh(false); openDrawer(); }
    catch (error) { alert(error.message); }
  });
  hideButton.addEventListener('click', () => {
    closeDrawer();
    try { sessionStorage.setItem(hideKey, '1'); } catch { /* The button can still hide until navigation. */ }
    setTucked(true);
    bell.focus();
  });
  closeButton.addEventListener('click', closeDrawer);
  backdrop.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeDrawer(); });
  readAll.addEventListener('click', async () => {
    try {
      const response = await fetch('/member/notifications/read-all', {
        method: 'POST', headers: { Accept: 'application/json' }, credentials: 'same-origin'
      });
      if (!response.ok) throw new Error('無法更新通知，請稍後再試。');
      await refresh(false);
      closeDrawer();
    } catch (error) { alert(error.message); }
  });
  refresh(true).catch(() => {});
  setInterval(() => refresh(true).catch(() => {}), 30000);
})();

