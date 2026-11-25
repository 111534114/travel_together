// 行程頁右側：「🤖 行程助理／🗺️ 地圖」分頁，以及行程助理聊天框。
(function () {
    // ---------- 分頁 ----------
    var tabs = Array.prototype.slice.call(document.querySelectorAll('[data-side-tab]'));
    var TAB_KEY = 'tripSideTab';
    function showTab(name) {
        tabs.forEach(function (tab) {
            var on = tab.dataset.sideTab === name;
            tab.classList.toggle('is-active', on);
            tab.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        document.querySelectorAll('[data-side-pane]').forEach(function (pane) { pane.hidden = pane.dataset.sidePane !== name; });
        if (name === 'map' && window.refreshItineraryMap) setTimeout(window.refreshItineraryMap, 30);
        try { localStorage.setItem(TAB_KEY, name); } catch (e) {}
    }
    tabs.forEach(function (tab) { tab.addEventListener('click', function () { showTab(tab.dataset.sideTab); }); });
    if (tabs.length) {
        var saved = null;
        try { saved = localStorage.getItem(TAB_KEY); } catch (e) {}
        showTab(saved === 'map' ? 'map' : 'assistant');
    }

    // ---------- 聊天框 ----------
    var root = document.querySelector('[data-trip-assistant]');
    if (!root) return;
    var list = root.querySelector('[data-ta-messages]');
    var welcome = root.querySelector('[data-ta-welcome]');
    var form = root.querySelector('[data-ta-form]');
    var input = root.querySelector('[data-ta-input]');
    var send = root.querySelector('[data-ta-send]');
    var foot = root.querySelector('[data-ta-foot]');
    var state = { canApply: false, undoId: null, remaining: 0, limit: 10, busy: false };
    var THINKING = ['正在看你的行程…', '在網站裡找適合的地方…', '查查天氣和交通時間…', '想想怎麼排比較順…', '快好了，再等一下…'];

    function esc(text) { var d = document.createElement('div'); d.textContent = text == null ? '' : String(text); return d.innerHTML; }
    function post(url, body) {
        return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body || {}) })
            .then(function (r) { return r.json().catch(function () { return {}; }).then(function (data) { data._status = r.status; return data; }); });
    }
    function scrollDown() { list.scrollTop = list.scrollHeight; }
    function setFoot() {
        foot.textContent = state.aiReady === false ? '伺服器還沒設定 AI 服務，暫時不能使用' : '今天還可以問 ' + state.remaining + ' 次（每天 ' + state.limit + ' 次）';
        var blocked = state.busy || state.remaining <= 0 || state.aiReady === false;
        send.disabled = blocked;
        input.disabled = state.aiReady === false || state.remaining <= 0;
    }

    function planHtml(message) {
        if (!message.changes || !message.changes.length) {
            return message.rejected && message.rejected.length ? '<ul class="ta-rejected">' + message.rejected.map(function (r) { return '<li>' + esc(r) + '</li>'; }).join('') + '</ul>' : '';
        }
        var rows = message.changes.map(function (c) {
            return '<li><span>' + esc(c.label) + '</span>' + (c.reason ? '<small>' + esc(c.reason) + '</small>' : '') + '</li>';
        }).join('');
        var rejected = (message.rejected || []).map(function (r) { return '<li>' + esc(r) + '</li>'; }).join('');
        var actions = '';
        if (message.status === 'pending') {
            actions = state.canApply
                ? '<button type="button" class="ta-apply" data-ta-apply="' + message.id + '">✅ 套用</button><button type="button" class="ta-dismiss" data-ta-dismiss="' + message.id + '">不要</button>'
                : '<p class="ta-note">只有建立者和共同編輯者可以套用。你可以把這個建議告訴他們！</p>';
        } else if (message.status === 'applied') {
            actions = '<span class="ta-done">✓ 已套用</span>' + (state.canApply && state.undoId === message.id ? '<button type="button" class="ta-undo" data-ta-undo="' + message.id + '">↩ 復原</button>' : '');
        } else if (message.status === 'undone') {
            actions = '<span class="ta-muted">已復原</span>';
        } else if (message.status === 'dismissed') {
            actions = '<span class="ta-muted">已略過</span>';
        } else if (message.status === 'stale') {
            actions = '<span class="ta-muted">行程被改過，這份建議已過期</span>';
        }
        return '<div class="ta-plan"><p class="ta-plan-title">建議的改動</p><ul>' + rows + '</ul>' +
            (rejected ? '<ul class="ta-rejected">' + rejected + '</ul>' : '') +
            '<div class="ta-plan-actions" data-ta-actions="' + message.id + '">' + actions + '</div></div>';
    }

    function bubble(message) {
        var el = document.createElement('div');
        el.className = 'ta-msg ' + (message.role === 'user' ? 'is-user' : 'is-bot');
        el.dataset.id = message.id || '';
        el.innerHTML = '<div class="ta-bubble">' + esc(message.content).replace(/\n/g, '<br>') + '</div>' + (message.role === 'user' ? '' : planHtml(message));
        return el;
    }

    function render(messages) {
        list.querySelectorAll('.ta-msg').forEach(function (el) { el.remove(); });
        welcome.hidden = messages.length > 0;
        state.messages = messages;
        messages.forEach(function (m) { list.appendChild(bubble(m)); });
        scrollDown();
    }

    function load() {
        return fetch(root.dataset.url, { credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (data) { data._status = r.status; return data; }); })
            .then(function (data) {
                if (data._status !== 200) { foot.textContent = data.error || '行程助理暫時不能使用'; input.disabled = send.disabled = true; return; }
                state.canApply = data.can_apply; state.undoId = data.undo_id; state.remaining = data.remaining;
                state.limit = data.limit; state.aiReady = data.ai_ready;
                render(data.messages || []);
                setFoot();
            })
            .catch(function () { foot.textContent = '行程助理暫時連不上，請重新整理'; });
    }

    function ask(text) {
        text = (text || '').trim();
        if (!text || state.busy || state.remaining <= 0) return;
        state.busy = true; setFoot();
        welcome.hidden = true;
        list.appendChild(bubble({ role: 'user', content: text }));
        var thinking = document.createElement('div');
        thinking.className = 'ta-msg is-bot is-thinking';
        thinking.innerHTML = '<div class="ta-bubble"><span class="ta-dots"><i></i><i></i><i></i></span> <span data-ta-step>' + THINKING[0] + '</span></div>';
        list.appendChild(thinking);
        scrollDown();
        var step = 0;
        var timer = setInterval(function () {
            step = Math.min(step + 1, THINKING.length - 1);
            var el = thinking.querySelector('[data-ta-step]');
            if (el) el.textContent = THINKING[step];
        }, 4000);
        input.value = '';
        post(root.dataset.askUrl, { message: text }).then(function (data) {
            clearInterval(timer);
            thinking.remove();
            if (data._status !== 200) {
                list.appendChild(bubble({ role: 'assistant', content: '⚠️ ' + (data.error || '助理暫時出了點問題，請再試一次') }));
            } else {
                state.remaining = data.remaining;
                state.messages = (state.messages || []).concat([data.message]);
                list.appendChild(bubble(data.message));
            }
        }).catch(function () {
            clearInterval(timer);
            thinking.remove();
            list.appendChild(bubble({ role: 'assistant', content: '⚠️ 連線中斷了，請再試一次' }));
        }).then(function () {
            state.busy = false; setFoot(); scrollDown(); input.focus();
        });
    }

    function setActions(id, html) {
        var box = list.querySelector('[data-ta-actions="' + id + '"]');
        if (box) box.innerHTML = html;
    }

    list.addEventListener('click', function (e) {
        var apply = e.target.closest('[data-ta-apply]');
        var dismiss = e.target.closest('[data-ta-dismiss]');
        var undo = e.target.closest('[data-ta-undo]');
        var example = e.target.closest('[data-ta-example]');
        if (example) { ask(example.dataset.taExample); return; }
        if (apply) {
            var id = Number(apply.dataset.taApply);
            if (!confirm('確定要套用這些改動嗎？套用後會通知其他旅伴。')) return;
            apply.disabled = true; apply.textContent = '套用中…';
            post(root.dataset.applyUrl, { message_id: id }).then(function (data) {
                if (data._status === 200) {
                    setActions(id, '<span class="ta-done">✓ ' + esc(data.message) + '，正在更新行程…</span>');
                    setTimeout(function () { location.reload(); }, 1200);
                } else {
                    setActions(id, '<p class="ta-error">' + esc(data.error || '套用失敗，請再試一次') + '</p>');
                }
            });
        } else if (dismiss) {
            var dismissId = Number(dismiss.dataset.taDismiss);
            post(root.dataset.dismissUrl, { message_id: dismissId }).then(function () { setActions(dismissId, '<span class="ta-muted">已略過</span>'); });
        } else if (undo) {
            var undoId = Number(undo.dataset.taUndo);
            if (!confirm('確定要把行程改回套用前的樣子嗎？')) return;
            undo.disabled = true; undo.textContent = '復原中…';
            post(root.dataset.undoUrl, { message_id: undoId }).then(function (data) {
                if (data._status === 200) {
                    setActions(undoId, '<span class="ta-done">✓ ' + esc(data.message) + '</span>');
                    setTimeout(function () { location.reload(); }, 1200);
                } else {
                    undo.disabled = false; undo.textContent = '↩ 復原';
                    setActions(undoId, '<span class="ta-done">✓ 已套用</span><p class="ta-error">' + esc(data.error || '復原失敗') + '</p>');
                }
            });
        }
    });

    form.addEventListener('submit', function (e) { e.preventDefault(); ask(input.value); });
    input.addEventListener('keydown', function (e) {  // Enter 送出、Shift+Enter 換行(中文選字時不要送出)
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); }
    });
    root.querySelector('[data-ta-clear]').addEventListener('click', function () {
        if (!confirm('要清除你和助理的對話紀錄嗎？（已套用的改動不會被復原）')) return;
        post(root.dataset.clearUrl).then(load);
    });

    load();

    // ---------- 出發前檢查卡片 ----------
    // 「🤖 請助理幫忙」：切到行程助理分頁，把問題交給助理(一樣會先列改動清單，按套用才改)
    document.querySelectorAll('[data-precheck-ask]').forEach(function (button) {
        button.addEventListener('click', function () {
            showTab('assistant');
            root.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (state.busy || state.remaining <= 0 || state.aiReady === false) {
                input.value = button.dataset.precheckAsk;  // 現在不能問：先把問題填好
                input.focus();
                return;
            }
            ask(button.dataset.precheckAsk);
        });
    });
    var toggle = document.querySelector('[data-precheck-toggle]');
    if (toggle) toggle.addEventListener('click', function () {
        var open = toggle.getAttribute('aria-expanded') !== 'true';
        document.querySelectorAll('[data-precheck-extra]').forEach(function (li) { li.hidden = !open; });
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        toggle.textContent = open ? '收起來' : '看全部';
    });
})();
