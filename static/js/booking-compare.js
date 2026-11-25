// 機票＋住宿比價：送出後在背景查詢(大約 1 分鐘)，這裡每 4 秒問一次進度，完成就重新整理到「住宿與預算」。
(function () {
    var root = document.querySelector('[data-booking-compare]');
    if (!root) return;
    var STEPS = ['正在查詢機票／火車…', '正在查詢住宿…', '比較價錢、評分和時間…', '組合三個方案…', '快好了，再等一下…'];

    function post(url, body) {
        return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body || {}) })
            .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { d._status = r.status; return d; }); });
    }
    function statusUrl(id) { return root.dataset.statusUrl.replace(/\/0$/, '/' + id); }
    function reloadToStay() { location.hash = 'stay'; location.reload(); }

    function poll(id, progress) {
        var step = 0;
        var started = Date.now();
        var timer = setInterval(function () {
            step = Math.min(step + 1, STEPS.length - 1);
            if (progress) progress.textContent = '⏳ ' + STEPS[step] + '（大約 1 分鐘，可以先去看別的分頁）';
        }, 12000);
        (function check() {
            fetch(statusUrl(id), { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (data) {
                if (data.status === 'running' && Date.now() - started < 6 * 60 * 1000) { setTimeout(check, 4000); return; }
                clearInterval(timer);
                reloadToStay();
            }).catch(function () { setTimeout(check, 6000); });
        })();
    }

    var form = root.querySelector('[data-bc-form]');

    // 要比什麼：可以多選；只比住宿時不需要出發地
    var scopeChips = form ? Array.prototype.slice.call(form.querySelectorAll('[data-bc-scope]')) : [];
    var choicesEl = root.querySelector('[data-bc-choices]');
    var CHOICES = choicesEl ? JSON.parse(choicesEl.textContent) : { origins: {}, requests: {} };
    var TRANSPORTS = ['flight', 'thsr', 'tra'];
    function esc(text) { var d = document.createElement('div'); d.textContent = text; return d.innerHTML; }
    function scope() {
        return scopeChips.filter(function (c) { return c.getAttribute('aria-pressed') === 'true'; }).map(function (c) { return c.dataset.bcScope; });
    }
    function needsOrigin() {
        return scope().some(function (key) { return key !== 'hotel'; });
    }

    // 出發地選項：依選的交通方式顯示最熱門的(機場／高鐵站／台鐵站)，選兩種以上就分組，不會混在一起
    function renderOrigins() {
        var box = form.querySelector('[data-bc-origin-chips]');
        var chosen = TRANSPORTS.filter(function (key) { return scope().indexOf(key) !== -1; });
        var value = form.elements.origin.value.trim();
        box.innerHTML = chosen.map(function (key) {
            var group = CHOICES.origins[key];
            var chips = group.items.map(function (item) {
                return '<button type="button" class="bc-chip" data-bc-origin="' + esc(item[0]) + '" aria-pressed="' + (item[0] === value ? 'true' : 'false') + '">' + esc(item[1]) + '</button>';
            }).join('');
            return '<div class="bc-chip-group">' + (chosen.length > 1 ? '<span class="bc-chip-group-title">' + group.title + '</span>' : '') +
                '<div class="bc-chips" role="group" aria-label="' + esc(group.title) + '">' + chips + '</div></div>';
        }).join('');
    }

    // 其他要求選項：依選的項目(住宿、機票、高鐵、台鐵)顯示相關的，重複的只出現一次
    function requestParts() {
        return form.elements.request.value.split(/[、,，]/).map(function (s) { return s.trim(); }).filter(Boolean);
    }
    function renderRequests() {
        var box = form.querySelector('[data-bc-request-chips]');
        var current = requestParts();
        var list = [];
        ['hotel'].concat(TRANSPORTS).forEach(function (key) {
            if (scope().indexOf(key) === -1) return;
            (CHOICES.requests[key] || []).forEach(function (text) { if (list.indexOf(text) === -1) list.push(text); });
        });
        box.innerHTML = list.map(function (text) {
            return '<button type="button" class="bc-chip" data-bc-request="' + esc(text) + '" aria-pressed="' + (current.indexOf(text) !== -1 ? 'true' : 'false') + '">' + esc(text) + '</button>';
        }).join('');
    }

    function syncScope() {
        var field = form.querySelector('[data-bc-origin-field]');
        var need = needsOrigin();
        field.classList.toggle('is-optional', !need);
        form.elements.origin.required = need;
        form.querySelector('[data-bc-origin-mark]').textContent = need ? '*' : '（只比住宿不用填，住宿是在目的地訂的）';
        renderOrigins();
        renderRequests();
    }
    scopeChips.forEach(function (chip) {
        chip.addEventListener('click', function () {
            chip.setAttribute('aria-pressed', chip.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
            syncScope();
        });
    });

    if (form) {
        // 點出發地選項就填好(只能選一個)；點其他要求可以點好幾個，點一下加入、再點一下拿掉
        form.addEventListener('click', function (e) {
            var origin = e.target.closest('[data-bc-origin]');
            var request = e.target.closest('[data-bc-request]');
            if (origin) {
                form.elements.origin.value = origin.dataset.bcOrigin;
                renderOrigins();
            } else if (request) {
                var current = requestParts();
                var index = current.indexOf(request.dataset.bcRequest);
                if (index === -1) current.push(request.dataset.bcRequest); else current.splice(index, 1);
                form.elements.request.value = current.join('、');
                renderRequests();
            }
        });
        form.elements.origin.addEventListener('input', renderOrigins);
        form.elements.request.addEventListener('input', renderRequests);
        if (scopeChips.length) syncScope();
    }

    if (form) form.addEventListener('submit', function (e) {
        e.preventDefault();
        var button = form.querySelector('[data-bc-submit]');
        var progress = form.querySelector('[data-bc-progress]');
        var origin = form.elements.origin.value.trim();
        var progressBox = form.querySelector('[data-bc-progress]');
        if (!scope().length) {
            progressBox.hidden = false; progressBox.classList.add('is-error');
            progressBox.textContent = '⚠️ 請至少選一個要比的項目（住宿、機票、高鐵或台鐵）';
            return;
        }
        if (needsOrigin() && !origin) { form.elements.origin.focus(); return; }
        button.disabled = true;
        button.textContent = '比價中…';
        progress.hidden = false;
        progress.classList.remove('is-error');
        progress.textContent = '⏳ ' + STEPS[0] + '（大約 1 分鐘，可以先去看別的分頁）';
        post(root.dataset.startUrl, { origin: origin, request: form.elements.request.value.trim(), scope: scope() }).then(function (data) {
            if (data._status !== 200) {
                progress.textContent = '⚠️ ' + (data.error || '比價沒有成功，請再試一次');
                progress.classList.add('is-error');
                button.disabled = false; button.textContent = '開始比價';
                return;
            }
            var remaining = root.querySelector('[data-bc-remaining]');
            if (remaining) remaining.textContent = data.remaining;
            poll(data.compare_id, progress);
        });
    });

    // 別人(或剛剛)正在比價的結果：自動等它完成
    var running = root.querySelector('[data-bc-status="running"]');
    if (running) poll(running.dataset.bcResult, null);

    // 把方案裡的飯店加進行程：先讓使用者勾選要住哪幾晚(還沒有住宿的晚上預設勾選)
    var nightsEl = document.querySelector('[data-bc-nights]');
    var NIGHTS = nightsEl ? JSON.parse(nightsEl.textContent) : [];
    var dialog = document.querySelector('[data-bc-nights-dialog]');
    if (dialog) document.body.appendChild(dialog);  // 移到最外層：分頁被隱藏時視窗才不會跟著看不到
    var pending = null;

    function nightBoxes() { return Array.prototype.slice.call(dialog.querySelectorAll('input[type=checkbox]')); }
    function updateOk() {
        var count = nightBoxes().filter(function (box) { return box.checked; }).length;
        var ok = dialog.querySelector('[data-bc-nights-ok]');
        ok.disabled = !count;
        ok.textContent = count ? '加入 ' + count + ' 晚' : '請勾選晚上';
    }
    function openNights(button) {
        pending = button;
        var perNight = Number(button.dataset.perNight || 0);
        dialog.querySelector('[data-bc-nights-hotel]').textContent =
            button.dataset.title + (perNight ? '（每晚約 NT$ ' + perNight.toLocaleString() + '）' : '');
        dialog.querySelector('[data-bc-nights-list]').innerHTML = NIGHTS.length ? NIGHTS.map(function (night) {
            return '<label class="bc-night"><input type="checkbox" value="' + night.date + '"' + (night.booked ? '' : ' checked') + '>' +
                '<span>' + esc(night.label) + ' 晚上</span>' +
                (night.booked ? '<small>已經有住宿：' + esc(night.booked) + '</small>' : '') + '</label>';
        }).join('') : '<p class="bc-muted">這趟是當天來回，不需要住宿。</p>';
        updateOk();
        if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
    }
    function closeNights() {
        if (dialog.close) dialog.close(); else dialog.removeAttribute('open');
        pending = null;
    }
    if (dialog) {
        dialog.addEventListener('change', updateOk);
        dialog.querySelector('[data-bc-nights-all]').addEventListener('click', function () { nightBoxes().forEach(function (b) { b.checked = true; }); updateOk(); });
        dialog.querySelector('[data-bc-nights-none]').addEventListener('click', function () { nightBoxes().forEach(function (b) { b.checked = false; }); updateOk(); });
        dialog.querySelector('[data-bc-nights-cancel]').addEventListener('click', closeNights);
        dialog.querySelector('[data-bc-nights-ok]').addEventListener('click', function () {
            if (!pending) return;
            var button = pending;
            var dates = nightBoxes().filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
            var ok = dialog.querySelector('[data-bc-nights-ok]');
            ok.disabled = true; ok.textContent = '加入中…';
            post(root.dataset.addUrl.replace(/\/0\/add-hotel$/, '/' + button.dataset.bcAdd + '/add-hotel'),
                 { kind: button.dataset.kind, dates: dates }).then(function (data) {
                closeNights();
                alert(data.message || data.error || '加入失敗，請再試一次');
                if (data._status === 200) reloadToStay();
            });
        });
    }

    root.addEventListener('click', function (e) {
        var button = e.target.closest('[data-bc-add]');
        if (button && dialog) openNights(button);
    });
})();
