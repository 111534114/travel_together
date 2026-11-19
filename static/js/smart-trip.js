// 行程頁的 AI 功能：
// 1. 每一天標題列的「✨ AI 排順序」：預覽 AI 建議的順序、時間與交通，確認後才套用。
// 2. 新增費用表單的截圖辨識：上傳機票／訂房／收據截圖，AI 填入名稱、金額、日期，並可一併加入每日行程。
(function () {
  var script = document.currentScript;
  var previewUrl = script ? script.dataset.previewUrl : '';
  var applyUrl = script ? script.dataset.applyUrl : '';

  function escapeHtml(value) {
    var el = document.createElement('div');
    el.textContent = value == null ? '' : String(value);
    return el.innerHTML;
  }

  function postJson(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || '伺服器忙碌中，請稍後再試。');
        return data;
      });
    });
  }

  // ---------- 智慧排程 ----------
  var modal = document.getElementById('smartModal');
  if (modal && previewUrl) {
    var body = modal.querySelector('[data-smart-body]');
    var applyBtn = modal.querySelector('[data-smart-apply]');
    var current = null;
    var lastFocus = null;

    function openModal() {
      lastFocus = document.activeElement;
      modal.hidden = false;
      document.body.classList.add('smart-modal-open');
      modal.querySelector('.smart-modal-close').focus();
    }
    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove('smart-modal-open');
      current = null;
      if (lastFocus) lastFocus.focus();
    }
    modal.addEventListener('click', function (e) {
      if (e.target === modal || e.target.closest('[data-smart-close]')) closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !modal.hidden) closeModal();
    });

    function legText(leg) {
      if (!leg) return '';
      var parts = [leg.method];
      if (leg.minutes) parts.push('約 ' + leg.minutes + ' 分鐘');
      if (leg.distance_label) parts.push(leg.distance_label);
      if (leg.cost) parts.push('每人約 NT$ ' + leg.cost);
      return parts.join(' · ') + (leg.estimated_by === 'ai' ? '（AI 估算）' : '');
    }

    function render(data) {
      var html = '<p class="smart-source ' + (data.source === 'ai' ? 'is-ai' : '') + '">' +
        (data.source === 'ai' ? '🤖 AI 依動線、營業時間與用餐時段排序' : '📍 依各站距離排出最順路的順序') + '</p>';
      if (data.note) html += '<p class="smart-note">' + escapeHtml(data.note) + '</p>';
      if (data.reason) html += '<p class="smart-reason">' + escapeHtml(data.reason) + '</p>';
      if (!data.changed) html += '<p class="smart-note">目前的順序已經很順路，只更新建議時間與交通。</p>';
      html += '<ol class="smart-list">';
      data.items.forEach(function (item) {
        if (item.leg) html += '<li class="smart-leg">↓ ' + escapeHtml(legText(item.leg)) + '</li>';
        html += '<li class="smart-stop"><span class="smart-time">' + escapeHtml(item.is_all_day ? '整天' : (item.start_time || '—')) +
          '</span><b>' + escapeHtml(item.title) + '</b>' + (item.has_coords ? '' : '<small>（沒有座標，交通時間為估計）</small>') + '</li>';
      });
      html += '</ol>';
      if (data.tips && data.tips.length) {
        html += '<ul class="smart-tips">' + data.tips.map(function (tip) { return '<li>💡 ' + escapeHtml(tip) + '</li>'; }).join('') + '</ul>';
      }
      html += '<p class="smart-disclaimer">套用後會更新這一天的順序、開始時間（保留原本停留長度）與交通方式，之後仍可手動拖曳或編輯。</p>';
      body.innerHTML = html;
      applyBtn.hidden = false;
    }

    document.querySelectorAll('[data-smart-day]').forEach(function (button) {
      button.addEventListener('click', function () {
        var day = button.dataset.smartDay;
        body.innerHTML = '<p class="smart-loading">AI 正在幫你排 ' + escapeHtml(day) + ' 的順序，約需 5–15 秒…</p>';
        applyBtn.hidden = true;
        openModal();
        postJson(previewUrl, { itinerary_date: day }).then(function (data) {
          current = data;
          render(data);
        }).catch(function (error) {
          body.innerHTML = '<p class="smart-error">' + escapeHtml(error.message) + '</p>';
        });
      });
    });

    applyBtn.addEventListener('click', function () {
      if (!current) return;
      applyBtn.disabled = true;
      applyBtn.textContent = '套用中…';
      postJson(applyUrl, {
        itinerary_date: current.itinerary_date,
        items: current.items.map(function (item) {
          return {
            itinerary_id: item.itinerary_id,
            start_time: item.is_all_day ? '' : item.start_time,
            transport_method: item.leg ? item.leg.method : '',
            transport_minutes: item.leg ? item.leg.minutes : ''
          };
        })
      }).then(function () {
        location.hash = 'itinerary';
        location.reload();
      }).catch(function (error) {
        applyBtn.disabled = false;
        applyBtn.textContent = '套用這個順序';
        body.insertAdjacentHTML('afterbegin', '<p class="smart-error">' + escapeHtml(error.message) + '</p>');
      });
    });
  }

  // ---------- 截圖辨識 ----------
  var scan = document.querySelector('[data-ai-scan]');
  if (scan) {
    var form = scan.closest('form');
    var input = scan.querySelector('[data-ai-scan-input]');
    var result = scan.querySelector('[data-ai-scan-result]');

    function setField(name, value) {
      var field = form.querySelector('[name="' + name + '"]');
      if (!field || value == null || value === '') return;
      field.value = value;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.classList.add('ai-filled');
    }

    input.addEventListener('change', function () {
      var file = input.files[0];
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) {
        result.innerHTML = '<p class="smart-error">圖片超過 8MB，請裁切或壓縮後再上傳。</p>';
        return;
      }
      var data = new FormData();
      data.append('image', file);
      result.innerHTML = '<p class="smart-loading">AI 辨識中，約需 5–10 秒…</p>';
      fetch(scan.dataset.scanUrl, { method: 'POST', body: data }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (json) {
          if (!res.ok) throw new Error(json.error || '辨識失敗，請手動填寫。');
          return json;
        });
      }).then(function (data) {
        setField('expense_name', data.expense_name || data.merchant);
        setField('amount', data.amount);
        setField('expense_date', data.date || (data.itinerary && data.itinerary.date));
        var note = [data.kind_label, data.merchant, data.details].filter(Boolean).join('｜');
        setField('note', note);
        var html = '<p class="ai-scan-ok">✅ 已辨識為「' + escapeHtml(data.kind_label) + '」並填入下方欄位' +
          (data.amount != null ? '：' + escapeHtml(data.currency || '') + ' ' + escapeHtml(data.amount) : '') + '</p>';
        html += data.warnings.map(function (w) { return '<p class="ai-scan-warn">⚠️ ' + escapeHtml(w) + '</p>'; }).join('');
        if (data.itinerary && scan.dataset.canEdit === '1') {
          var it = data.itinerary;
          html += '<div class="ai-scan-itinerary">也要加到 ' + escapeHtml(it.date) + ' 的每日行程嗎？「' + escapeHtml(it.title) + '」' +
            (it.start_time ? ' ' + escapeHtml(it.start_time) : '') +
            ' <button type="button" class="member-btn outline small" data-ai-scan-add>加入每日行程</button></div>';
        }
        result.innerHTML = html;
        var addBtn = result.querySelector('[data-ai-scan-add]');
        if (addBtn) {
          addBtn.addEventListener('click', function () {
            // 用背景送出，避免離開頁面時，還沒儲存的費用表單內容不見
            var it = data.itinerary;
            var fields = new FormData();
            fields.append('title', it.title);
            fields.append('item_type', it.item_type);
            fields.append('itinerary_date', it.date);
            fields.append('time_mode', it.start_time ? 'start_only' : 'all_day');
            fields.append('start_time', it.start_time || '');
            fields.append('notes', [data.merchant, data.details].filter(Boolean).join('｜'));
            addBtn.disabled = true;
            addBtn.textContent = '加入中…';
            fetch(scan.dataset.itineraryUrl, { method: 'POST', body: fields }).then(function (res) {
              if (!res.ok) throw new Error();
              addBtn.replaceWith(Object.assign(document.createElement('b'), { textContent: '✅ 已加入（儲存費用後重新整理即可看到）' }));
            }).catch(function () {
              addBtn.disabled = false;
              addBtn.textContent = '加入每日行程';
              alert('加入每日行程失敗，請稍後再試。');
            });
          });
        }
      }).catch(function (error) {
        result.innerHTML = '<p class="smart-error">' + escapeHtml(error.message) + '</p>';
      }).finally(function () {
        input.value = '';
      });
    });
  }
})();
