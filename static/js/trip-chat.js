// 行程聊天室：每幾秒輪詢新訊息、已讀狀態與投票進度。
// 只有聊天室真的出現在畫面上（分頁在前景＋區塊捲到可見）才會回報「已讀」，避免沒看到也被算已讀。
(function () {
    var panel = document.getElementById('chat');
    if (!panel) return;

    var POLL_MS = 4000;
    var feedUrl = panel.dataset.feedUrl;
    var readUrl = panel.dataset.readUrl;
    var nudgeUrl = panel.dataset.nudgeUrl;
    var removeUrl = panel.dataset.removeUrl;
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
    var canModerate = false;
    var canReply = false;
    var replyTo = null;          // 正在回覆的那則訊息 {id, name, content}
    var firstLoad = true;
    var replyBar = document.getElementById('chatReplyBar');
    // 新訊息提示卡要在任何分頁都看得到，所以搬到 body 底下(聊天室分頁隱藏時也不會跟著藏起來)
    var toast = document.getElementById('chatToast');
    if (toast) document.body.appendChild(toast);
    var toastTimer = null;
    var toastCount = 0;
    var baseTitle = document.title;

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

    // 這則訊息有沒有 @ 我(或 @ALL)
    function mentionsMe(content) {
        if (!content || content.indexOf('@') === -1) return false;
        if (/@(ALL|所有人)(?![A-Za-z0-9_])/i.test(content)) return true;
        var mine = members.filter(function (m) { return m.user_id === me; })[0];
        return !!mine && content.indexOf('@' + mine.name) !== -1;
    }

    function jumpTo(id) {
        var row = listEl.querySelector('.chat-message[data-id="' + id + '"]');
        if (!row) { showError('原訊息太舊了，沒有顯示在畫面上。'); return; }
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        row.classList.remove('flash');
        void row.offsetWidth;
        row.classList.add('flash');
    }

    function startReply(message) {
        replyTo = { id: message.id };
        replyBar.querySelector('[data-reply-name]').textContent = message.user_id === me ? '自己' : message.name;
        replyBar.querySelector('[data-reply-text]').textContent = message.content.length > 40 ? message.content.slice(0, 40) + '…' : message.content;
        replyBar.hidden = false;
        input.focus();
    }

    function cancelReply() {
        replyTo = null;
        if (replyBar) replyBar.hidden = true;
    }
    if (replyBar) replyBar.querySelector('[data-reply-cancel]').addEventListener('click', function () { cancelReply(); input.focus(); });

    // ---------- 新訊息提示(顯眼一點) ----------
    function chatOnScreen() {
        return panelVisible && document.visibilityState === 'visible' && !panel.hidden;
    }

    function hideToast() {
        if (!toast) return;
        toast.hidden = true;
        toast.classList.remove('show', 'for-me');
        toastCount = 0;
        clearTimeout(toastTimer);
    }

    function openChat() {
        if (window.openTripTab) window.openTripTab('chat');
        hideToast();
        setTimeout(function () {
            panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            listEl.scrollTop = listEl.scrollHeight;
            input.focus({ preventScroll: true });
        }, 50);
    }

    function showToast(newMessages) {
        if (!toast || !newMessages.length) return;
        var last = newMessages[newMessages.length - 1];
        var forMe = newMessages.some(function (m) { return mentionsMe(m.content) || (m.reply && m.reply.user_id === me); });
        toastCount += newMessages.length;
        toast.querySelector('[data-toast-avatar]').textContent = last.name.slice(0, 1);
        var lastForMe = newMessages.filter(function (m) { return mentionsMe(m.content) || (m.reply && m.reply.user_id === me); }).pop();
        if (lastForMe) last = lastForMe;  // 有跟我有關的訊息就優先顯示那一則
        toast.querySelector('[data-toast-title]').textContent = forMe ? last.name + (last.reply && last.reply.user_id === me ? ' 回覆了你' : ' 提到你') :
            last.name + (toastCount > 1 ? ' 等 ' + toastCount + ' 則新訊息' : ' 傳了新訊息');
        toast.querySelector('[data-toast-text]').textContent = last.content.length > 60 ? last.content.slice(0, 60) + '…' : last.content;
        if (forMe) toast.classList.add('for-me');
        toast.hidden = false;
        void toast.offsetWidth;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(hideToast, toast.classList.contains('for-me') ? 15000 : 8000);  // 提到你的停久一點
    }
    if (toast) {
        toast.querySelector('[data-toast-open]').addEventListener('click', openChat);
        toast.querySelector('[data-toast-close]').addEventListener('click', hideToast);
    }

    function appendMessage(message) {
        var mine = message.user_id === me;
        var row = el('div', 'chat-message' + (mine ? ' mine' : ''));
        row.dataset.id = message.id;
        row.dataset.userId = message.user_id;
        if (!mine) row.appendChild(el('i', 'chat-avatar', message.name.slice(0, 1)));
        var bubbleWrap = el('div', 'chat-msg-body');
        if (!mine) bubbleWrap.appendChild(el('b', 'chat-name', message.name));
        if (message.reply) {
            // 引用的原訊息：點一下跳回那一則
            var quote = el('button', 'chat-quote');
            quote.type = 'button';
            quote.title = '跳到原訊息';
            quote.appendChild(el('b', '', '↩ ' + (message.reply.name || '原訊息')));
            quote.appendChild(el('span', '', message.reply.content));
            quote.addEventListener('click', function () { jumpTo(message.reply.id); });
            bubbleWrap.appendChild(quote);
        }
        var forMe = mine ? '' : (message.reply && message.reply.user_id === me ? ' · 回覆你' : (mentionsMe(message.content) ? ' · 提到你' : ''));
        if (forMe) { row.classList.add('for-me'); bubbleWrap.querySelector('.chat-name').dataset.forMe = forMe; }
        var text = el('p', 'chat-text');
        // @提及標示由 trip_detail.html 提供；沒有的話就當純文字
        text.appendChild(window.highlightMentions ? window.highlightMentions(message.content) : document.createTextNode(message.content));
        bubbleWrap.appendChild(text);
        var meta = el('small', 'chat-meta');
        meta.appendChild(el('span', 'chat-read'));
        meta.appendChild(el('span', '', message.time));
        if (canReply && !message.removed) {
            var replyBtn = el('button', 'chat-reply-button', '↩ 回覆');
            replyBtn.type = 'button';
            replyBtn.addEventListener('click', function () { startReply(message); });
            meta.appendChild(replyBtn);
        }
        bubbleWrap.appendChild(meta);
        if (canModerate && !message.removed) {  // 團長的「移除」放在時間那一行，不另外佔一行
            var remove = el('button', 'chat-remove-button', '移除');
            remove.type = 'button';
            remove.title = '移除不當訊息';
            remove.addEventListener('click', function () {
                if (!confirm('確定要移除這則訊息嗎？')) return;
                postJson(removeUrl.replace('/0/remove', '/' + message.id + '/remove'))
                    .then(function () { showError(''); return poll(); })
                    .catch(function (err) { showError(err.message); });
            });
            meta.appendChild(remove);
        }
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
        updateUnreadBadge();
        postJson(readUrl, { last_read_message_id: target }).catch(function () { myLastRead = 0; });
    }

    // 頁面上方「聊天室」快捷按鈕的未讀數（別人傳的、我還沒看到的訊息）
    var unreadBadge = document.querySelector('[data-chat-unread]');
    function updateUnreadBadge() {
        if (!unreadBadge) return;
        var count = [].filter.call(listEl.querySelectorAll('.chat-message:not(.mine)'), function (row) {
            return Number(row.dataset.id) > myLastRead;
        }).length;
        unreadBadge.textContent = count > 99 ? '99+' : count;
        unreadBadge.hidden = !count;
        // 瀏覽器分頁標題也顯示未讀數，切到別的網頁也看得到
        document.title = (count ? '(' + (count > 99 ? '99+' : count) + ') 💬 ' : '') + baseTitle;
        var tab = unreadBadge.closest('.trip-tab');
        if (tab) tab.classList.toggle('has-unread', !!count);
    }

    function poll() {
        if (polling) return Promise.resolve();
        polling = true;
        return fetch(feedUrl + '?after=' + lastId, { headers: { 'Accept': 'application/json' } })
            .then(function (res) {
                return res.json().catch(function () {
                    throw new Error('聊天室暫時無法載入，請稍後再試。');
                }).then(function (data) {
                    if (!res.ok) throw new Error(data.error || '聊天室暫時無法載入，請稍後再試。');
                    return data;
                });
            })
            .then(function (data) {
                if (data.error) throw new Error(data.error);
                var stick = lastId === 0 || isNearBottom();
                if (lastId === 0) listEl.textContent = '';
                me = data.me;
                canModerate = !!data.can_moderate;
                canReply = !!data.can_reply;
                members = data.members;
                latestId = data.latest_id;
                members.forEach(function (m) { if (m.user_id === me) myLastRead = Math.max(myLastRead, m.last_read); });
                data.messages.forEach(appendMessage);
                var fromOthers = data.messages.filter(function (m) { return m.user_id !== me && m.id > myLastRead && !m.removed; });
                if (!firstLoad && fromOthers.length && !chatOnScreen()) showToast(fromOthers);
                firstLoad = false;
                (data.removed_ids || []).forEach(function (id) {
                    var row = listEl.querySelector('.chat-message[data-id="' + id + '"]');
                    if (!row) return;
                    var text = row.querySelector('.chat-text');
                    if (text) text.textContent = '訊息已由團長移除';
                    var remove = row.querySelector('.chat-remove-button');
                    if (remove) remove.remove();
                });
                if (data.messages.length) lastId = data.messages[data.messages.length - 1].id;
                if (!messageIds.length && !listEl.querySelector('.muted')) listEl.appendChild(el('p', 'muted', '還沒有訊息，跟旅伴打聲招呼吧！'));
                if (messageIds.length) { var empty = listEl.querySelector('.muted'); if (empty) empty.remove(); }
                renderReceipts();
                renderReadStatus();
                renderVotes(data.votes);
                updateUnreadBadge();
                if (stick) listEl.scrollTop = listEl.scrollHeight;
                markRead();
                if (chatOnScreen()) hideToast();
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
        var body = { content: content };
        if (replyTo) body.reply_to = replyTo.id;
        postJson(form.action, body)
            .then(function () { input.value = ''; cancelReply(); showError(''); return poll(); })
            .then(function () { listEl.scrollTop = listEl.scrollHeight; })
            .catch(function (err) { showError(err.message); })
            .then(function () { button.disabled = false; input.focus(); });
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && replyTo) { cancelReply(); return; }
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            panelVisible = entries[0].isIntersecting;
            markRead();
            if (chatOnScreen()) hideToast();
        }, { threshold: 0.3 }).observe(listEl);
    } else {
        panelVisible = true;
    }
    document.addEventListener('visibilitychange', markRead);

    poll();
    setInterval(function () { if (document.visibilityState === 'visible') poll(); }, POLL_MS);
})();
