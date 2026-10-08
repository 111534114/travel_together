// 行程聊天室：每幾秒輪詢新訊息、已讀狀態與投票進度。
// 只有聊天室真的出現在畫面上（分頁在前景＋區塊捲到可見）才會回報「已讀」，避免沒看到也被算已讀。
(function () {
    var panel = document.getElementById('chat');
    if (!panel) return;

    var POLL_MS = 4000;
    var feedUrl = panel.dataset.feedUrl;
    var readUrl = panel.dataset.readUrl;
    var nudgeUrl = panel.dataset.nudgeUrl;
    var listEl = document.getElementById('chatMessages');
    var form = document.getElementById('chatForm');
    var input = form.querySelector('textarea');
    var errorEl = document.getElementById('chatError');
    var readStatusEl = document.getElementById('chatReadStatus');
    var voteStatusEl = document.getElementById('chatVoteStatus');
    var summaryEl = document.getElementById('chatSummary');

    var me = null;
    var lastId = 0;
    var latestId = 0;
    var myLastRead = 0;
    var members = [];
    var messageIds = [];
    var panelVisible = false;
    var polling = false;

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function showError(message) {
        errorEl.textContent = message || '';
        errorEl.hidden = !message;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {})
        }).then(function (res) {
            return res.json().catch(function () { return {}; }).then(function (data) {
                if (!res.ok) throw new Error(data.error || '操作失敗，請再試一次。');
                return data;
            });
        });
    }

    function isNearBottom() {
        return listEl.scrollHeight - listEl.scrollTop - listEl.clientHeight < 60;
    }

    // 看過某則訊息的人（不含發訊者本人）
    function readersOf(message) {
        return members.filter(function (m) {
            return m.user_id !== message.user_id && m.last_read >= message.id;
        });
    }

    function appendMessage(message) {
        var mine = message.user_id === me;
        var row = el('div', 'chat-message' + (mine ? ' mine' : ''));
        row.dataset.id = message.id;
        row.dataset.userId = message.user_id;
        if (!mine) row.appendChild(el('i', 'chat-avatar', message.name.slice(0, 1)));
        var bubbleWrap = el('div', 'chat-msg-body');
        if (!mine) bubbleWrap.appendChild(el('b', 'chat-name', message.name));
        bubbleWrap.appendChild(el('p', 'chat-text', message.content));
        var meta = el('small', 'chat-meta');
        meta.appendChild(el('span', 'chat-read'));
        meta.appendChild(el('span', '', message.time));
        bubbleWrap.appendChild(meta);
        row.appendChild(bubbleWrap);
        listEl.appendChild(row);
        messageIds.push(message.id);
    }

    function renderReceipts() {
        var others = members.length - 1;
        listEl.querySelectorAll('.chat-message').forEach(function (row) {
            var message = { id: Number(row.dataset.id), user_id: Number(row.dataset.userId) };
            var readers = readersOf(message);
            var audience = members.filter(function (m) { return m.user_id !== message.user_id; });
            var label = row.querySelector('.chat-read');
            if (!audience.length) { label.textContent = ''; return; }
            label.textContent = readers.length >= audience.length ? '全部已讀' : (readers.length ? '已讀 ' + readers.length + '/' + audience.length : '未讀');
            label.className = 'chat-read' + (readers.length >= audience.length ? ' all' : '');
            var unread = audience.filter(function (m) { return readers.indexOf(m) === -1; });
            label.title = (readers.length ? '已讀：' + readers.map(function (m) { return m.name; }).join('、') : '還沒有人讀') +
                (unread.length ? '\n未讀：' + unread.map(function (m) { return m.name; }).join('、') : '');
        });
        summaryEl.textContent = members.length + ' 位旅伴' + (others > 0 ? '' : '（邀請旅伴一起聊吧）');
    }

    function renderReadStatus() {
        readStatusEl.textContent = '';
        members.forEach(function (m) {
            var unreadCount = messageIds.filter(function (id) { return id > m.last_read; }).length;
            var row = el('div', 'chat-status-row');
            row.appendChild(el('i', 'chat-avatar small', m.name.slice(0, 1)));
            var info = el('div');
            info.appendChild(el('b', '', m.name + (m.user_id === me ? '（你）' : '')));
            var state;
            if (!latestId) state = m.last_seen ? '最近查看 ' + m.last_seen : '尚未進入聊天室';
            else if (m.last_read >= latestId) state = '✓ 已看到最新訊息';
            else if (!m.last_seen && !m.last_read) state = '尚未進入聊天室';
            else state = '未讀 ' + unreadCount + ' 則' + (m.last_seen ? '・最後查看 ' + m.last_seen : '');
            info.appendChild(el('small', m.last_read >= latestId && latestId ? 'ok' : (latestId ? 'warn' : ''), state));
            row.appendChild(info);
            readStatusEl.appendChild(row);
        });
    }

    function renderVotes(votes) {
        voteStatusEl.textContent = '';
        if (!votes.length) {
            voteStatusEl.appendChild(el('p', 'muted', '目前沒有進行中的投票。'));
            return;
        }
        votes.forEach(function (v) {
            var card = el('div', 'chat-vote-card');
            card.appendChild(el('b', '', v.title));
            var total = v.voted.length + v.pending.length;
            card.appendChild(el('small', '', '已投 ' + v.voted.length + '/' + total + '・截止 ' + v.deadline));
            var names = function (list) { return list.map(function (p) { return p.name; }).join('、'); };
            if (v.voted.length) card.appendChild(el('p', 'voted', '✓ ' + names(v.voted)));
            if (v.pending.length) {
                card.appendChild(el('p', 'pending', '⏳ 未投：' + names(v.pending)));
                var btn = el('button', 'member-btn ghost small', '📣 提醒未投票的人');
                btn.type = 'button';
                btn.addEventListener('click', function () {
                    btn.disabled = true;
                    postJson(nudgeUrl + v.vote_id).then(function () { showError(''); poll(); })
                        .catch(function (err) { showError(err.message); })
                        .then(function () { btn.disabled = false; });
                });
                card.appendChild(btn);
            } else {
                card.appendChild(el('p', 'voted', '大家都投完了 🎉'));
            }
            voteStatusEl.appendChild(card);
        });
    }

    function markRead() {
        if (!panelVisible || document.visibilityState !== 'visible' || latestId <= myLastRead) return;
        var target = latestId;
        myLastRead = target;
        postJson(readUrl, { last_read_message_id: target }).catch(function () { myLastRead = 0; });
    }

    function poll() {
        if (polling) return Promise.resolve();
        polling = true;
        return fetch(feedUrl + '?after=' + lastId, { headers: { 'Accept': 'application/json' } })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.error) throw new Error(data.error);
                var stick = lastId === 0 || isNearBottom();
                if (lastId === 0) listEl.textContent = '';
                me = data.me;
                members = data.members;
                latestId = data.latest_id;
                members.forEach(function (m) { if (m.user_id === me) myLastRead = Math.max(myLastRead, m.last_read); });
                data.messages.forEach(appendMessage);
                if (data.messages.length) lastId = data.messages[data.messages.length - 1].id;
                if (!messageIds.length && !listEl.querySelector('.muted')) listEl.appendChild(el('p', 'muted', '還沒有訊息，跟旅伴打聲招呼吧！'));
                if (messageIds.length) { var empty = listEl.querySelector('.muted'); if (empty) empty.remove(); }
                renderReceipts();
                renderReadStatus();
                renderVotes(data.votes);
                if (stick) listEl.scrollTop = listEl.scrollHeight;
                markRead();
            })
            .catch(function (err) { showError(err.message || '聊天室連線中斷，稍後自動重試。'); })
            .then(function () { polling = false; });
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var content = input.value.trim();
        if (!content) return;
        var button = form.querySelector('button');
        button.disabled = true;
        postJson(form.action, { content: content })
            .then(function () { input.value = ''; showError(''); return poll(); })
            .then(function () { listEl.scrollTop = listEl.scrollHeight; })
            .catch(function (err) { showError(err.message); })
            .then(function () { button.disabled = false; input.focus(); });
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            panelVisible = entries[0].isIntersecting;
            markRead();
        }, { threshold: 0.3 }).observe(listEl);
    } else {
        panelVisible = true;
    }
    document.addEventListener('visibilitychange', markRead);

    poll();
    setInterval(function () { if (document.visibilityState === 'visible') poll(); }, POLL_MS);
})();
