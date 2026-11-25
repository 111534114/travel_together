(() => {
  // 首頁搜尋面板的分頁切換：點分頁按鈕時換 active 樣式，並顯示對應的欄位列。
  // 要放在最前面，才會比後面那段更新 #searchNote 文字的 click 監聽器先註冊、先執行。
  document.querySelectorAll('.search-tab[data-tab]').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.search-tab[data-tab]').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('[data-tab-fields]').forEach((row) => {
        row.hidden = row.dataset.tabFields !== tab.dataset.tab;
      });
    });
  });

  // 側邊欄自己可以捲動；整個頁面捲回最上面時，側邊欄也跟著回到最上面，不然「排序」這一欄會被捲到看不見。
  (() => {
    const sidebar = document.querySelector('.results-sidebar');
    if (!sidebar) return;
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        if (window.scrollY <= 40 && sidebar.scrollTop > 0) sidebar.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }, { passive: true });
  })();

  // 航空公司篩選的搜尋框：純前端文字篩選，不用重新送出表單查一次，輸入時即時隱藏不符合的選項。
  document.querySelectorAll('[data-facet-search]').forEach((input) => {
    const list = document.querySelector(`[data-facet-list="${input.dataset.facetSearch}"]`);
    if (!list) return;
    input.addEventListener('input', () => {
      const keyword = input.value.trim().toLowerCase();
      list.querySelectorAll('[data-facet-label]').forEach((row) => {
        row.hidden = keyword !== '' && !row.dataset.facetLabel.includes(keyword);
      });
    });
  });

  // 雙滑桿(價格/時間/時長共用同一套邏輯)：data-range-slider 標記格式(price/time/duration)決定輸出文字怎麼組，
  // 跟搜尋表單(.search-panel)無關，首頁跟三個搜尋結果頁都可能有，所以獨立成一段，
  // 不能放在下面那段「找不到 .search-panel 表單就整段不執行」的邏輯裡面。
  const RANGE_FORMATTERS = {
    price: (value) => 'NT$ ' + Number(value).toLocaleString('zh-TW'),
    time: (value) => String(Math.floor(value / 60)).padStart(2, '0') + ':' + String(value % 60).padStart(2, '0'),
    duration: (value) => {
      const h = Math.floor(value / 60);
      const m = value % 60;
      return h + ' 小時' + (m ? ' ' + m + ' 分' : '');
    },
  };
  document.querySelectorAll('[data-range-slider]').forEach((slider) => {
    const inputs = slider.querySelectorAll('input[type="range"]');
    const minInput = inputs[0];
    const maxInput = inputs[1];
    if (!minInput || !maxInput) return;
    const fill = slider.querySelector('[data-price-fill]');
    const output = slider.closest('[data-range-row]')?.querySelector('[data-price-slider-output]');
    const sliderForm = slider.closest('form');
    const sliderMin = Number(minInput.min);
    const sliderMax = Number(minInput.max);
    const format = RANGE_FORMATTERS[slider.dataset.rangeSlider] || String;
    const percent = (value) => ((Number(value) - sliderMin) / (sliderMax - sliderMin)) * 100;
    // 滑桿旁邊的數字框(價格才有)：可以直接輸入金額；跟滑桿雙向同步
    const numberInputs = { min: slider.closest('[data-range-row]')?.querySelector('[data-range-num="min"]'), max: slider.closest('[data-range-row]')?.querySelector('[data-range-num="max"]') };
    function render(changed, fromNumber) {
      if (Number(minInput.value) > Number(maxInput.value)) {
        if (changed === minInput) maxInput.value = minInput.value;
        else minInput.value = maxInput.value;
      }
      fill.style.left = percent(minInput.value) + '%';
      fill.style.right = (100 - percent(maxInput.value)) + '%';
      if (output) output.textContent = format(minInput.value) + ' ～ ' + format(maxInput.value);
      if (!fromNumber) {  // 正在打字時不要回寫數字框，不然會一邊打一邊被改掉
        if (numberInputs.min) numberInputs.min.value = minInput.value;
        if (numberInputs.max) numberInputs.max.value = maxInput.value;
      }
    }
    minInput.addEventListener('input', () => render(minInput));
    maxInput.addEventListener('input', () => render(maxInput));
    [['min', minInput], ['max', maxInput]].forEach(([which, rangeInput]) => {
      const box = numberInputs[which];
      if (!box) return;
      const clamp = () => Math.min(sliderMax, Math.max(sliderMin, Number(box.value) || 0));
      box.addEventListener('input', () => { rangeInput.value = clamp(); render(rangeInput, true); });
      box.addEventListener('change', () => { rangeInput.value = clamp(); render(rangeInput); if (sliderForm) sliderForm.requestSubmit(); });
      box.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); box.dispatchEvent(new Event('change')); } });
    });
    minInput.addEventListener('change', () => sliderForm && sliderForm.requestSubmit());
    maxInput.addEventListener('change', () => sliderForm && sliderForm.requestSubmit());
    // 除了拖拉圓點，也可以直接點軌道：離點擊位置最近的圓點會跳過去並套用篩選。
    // 圓點本身的點擊事件 target 是 input，交給瀏覽器原本的拖拉行為處理，這裡只處理點在軌道上的情況。
    slider.addEventListener('click', (event) => {
      if (event.target === minInput || event.target === maxInput) return;
      const rect = slider.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
      const step = Number(minInput.step) || 1;
      const value = Math.min(sliderMax, Math.max(sliderMin, Math.round((sliderMin + ratio * (sliderMax - sliderMin)) / step) * step));
      const target = Math.abs(value - Number(minInput.value)) <= Math.abs(value - Number(maxInput.value))
        && value <= Number(maxInput.value) ? minInput : maxInput;
      target.value = value;
      render(target);
      target.dispatchEvent(new Event('change', {bubbles: true}));
    });
    render();
  });

  const form = document.querySelector('.search-panel form');
  if (!form) return;
  form.noValidate = true;
  const query = new URLSearchParams(location.search);
  const ids = {
    hotel: {destination:'hotelDest', checkin:'hotelCheckin', checkout:'hotelCheckout', guests:'hotelGuests'},
    flight: {from:'flightFrom', to:'flightTo', depart:'flightDepart', return:'flightReturn', pax:'flightPax'},
    train: {from:'trainFrom', to:'trainTo', date:'trainDate', return:'trainReturn', pax:'trainPax'}
  };
  const get = id => document.getElementById(id);

  // 日期範圍選擇器：住宿(入住/退房)、機票(去程/回程)、高鐵(出發/回程)都用同一顆 flatpickr 範圍選擇器，
  // 選好的日期另外寫進對應的隱藏欄位(hotelCheckin/hotelCheckout 等)，表單驗證、送出邏輯完全不用改。
  // 火車可選的最晚日期由後端算好放在 data-max-by-rail(booking_search.train_max_date)：
  // 高鐵＝開放訂票規則和 TDX 已公布時刻表取較晚(連假疏運提前開放會自動延長)，台鐵＝今天 + 28 天
  const trainMaxDate = () => {
    const rail = document.querySelector('input[name="rail"]:checked')?.value || 'thsr';
    let maxByRail = {};
    try { maxByRail = JSON.parse(get('trainDateRange')?.dataset.maxByRail || '{}'); } catch (e) { maxByRail = {}; }
    if (maxByRail[rail]) return maxByRail[rail];
    const max = new Date();  // 後端沒給(理論上不會)就退回今天 + 28 天
    max.setHours(0, 0, 0, 0);
    max.setDate(max.getDate() + 28);
    return max;
  };
  const pickers = {};
  if (typeof flatpickr !== 'undefined') {
    // 英文版(Google 翻譯)會把日曆上的數字翻成「twenty one」、星期翻成整個字擠在一起，
    // 所以英文版改用 flatpickr 內建英文(Sun、Mon…)，並把日曆格子標成 notranslate 不讓 Google 翻。
    const englishPage = /(?:^|;\s*)googtrans=\/[^/;]*\/en(?:;|$)/.test(document.cookie);
    const zhTw = englishPage ? null : (flatpickr.l10ns && flatpickr.l10ns.zh_tw);
    const dateLabel = englishPage ? 'M j (D)' : 'n月j日 D';
    const rangeFieldConfig = {
      hotel: {input:'hotelDateRange', start:'hotelCheckin', end:'hotelCheckout', badge:'hotelDateBadge'},
      flight: {input:'flightDateRange', start:'flightDepart', end:'flightReturn', badge:null},
      train: {input:'trainDateRange', start:'trainDate', end:'trainReturn', badge:null},
    };
    // 日曆下方那排「10月22日 週四 - 10月23日 週五（1晚）」摘要文字，flatpickr 本身沒有這個，自己插進去。
    const renderSummary = (instance) => {
      if (!instance.summaryEl) return;
      const [start, end] = instance.selectedDates;
      const fmt = (d) => flatpickr.formatDate(d, dateLabel, instance.l10n);  // 用日曆已經解析好的語言物件
      if (instance.config.mode === 'single') {  // 多座城市每一段只選一天
        instance.summaryEl.textContent = start ? fmt(start) : '請選擇日期';
        return;
      }
      if (start && end) {
        const nights = Math.round((end - start) / 86400000);
        instance.summaryEl.textContent = fmt(start) + ' - ' + fmt(end) + '（' + nights + '晚）';
      } else if (start) {
        instance.summaryEl.textContent = fmt(start) + '（請再選一個日期）';
      } else {
        instance.summaryEl.textContent = '請選擇日期';
      }
    };
    // 固定國定假日(農曆的初一、端午、中秋每年日期不同，沒有另外查表就不列進來，避免標錯)。
    const TAIWAN_HOLIDAYS = {'01-01':'元旦','02-28':'和平紀念日','04-04':'兒童節','05-01':'勞動節','10-10':'國慶日'};
    const renderHolidayNote = (instance) => {
      if (!instance.holidayEl) return;
      const pad = n => String(n).padStart(2, '0');
      const months = [];
      for (let i = 0; i < instance.config.showMonths; i++) {
        const d = new Date(instance.currentYear, instance.currentMonth + i, 1);
        months.push(d);
      }
      const notes = [];
      months.forEach((monthDate) => {
        const key = pad(monthDate.getMonth() + 1);
        Object.entries(TAIWAN_HOLIDAYS).forEach(([mmdd, name]) => {
          if (mmdd.slice(0, 2) === key) {
            notes.push(monthDate.getMonth() + 1 + '月' + Number(mmdd.slice(3)) + '日 ' + name);
          }
        });
      });
      instance.holidayEl.textContent = notes.length ? '• ' + notes.join('　• ') : '';
    };
    // 日曆共用的外觀：頁尾(假日提示＋日期摘要)、月份切換時更新、打開時外框亮起。範圍選擇器與多座城市的單日選擇器都用這一份
    const sharedHooks = {
        onReady: (selectedDates, dateStr, instance) => {
          instance.calendarContainer.querySelectorAll('.flatpickr-months, .flatpickr-weekdays, .flatpickr-days')
            .forEach((el) => el.classList.add('notranslate'));
          if (instance.altInput) instance.altInput.classList.add('notranslate');
          const footer = document.createElement('div');
          footer.className = 'date-range-footer';
          instance.holidayEl = document.createElement('div');
          instance.holidayEl.className = 'date-range-holiday';
          instance.summaryEl = document.createElement('div');
          instance.summaryEl.className = 'date-range-summary';
          footer.append(instance.holidayEl, instance.summaryEl);
          instance.calendarContainer.appendChild(footer);
          renderSummary(instance);
          renderHolidayNote(instance);
        },
        onMonthChange: (selectedDates, dateStr, instance) => renderHolidayNote(instance),
        onYearChange: (selectedDates, dateStr, instance) => renderHolidayNote(instance),
        // 日曆打開的整段期間框線都要亮著，不能只靠 :focus-within，因為點月曆格子時焦點會跑到
        // 外掛在 document.body 底下的日曆元素，不在 .date-range-box 裡面，:focus-within 會提前消失。
        onOpen: (selectedDates, dateStr, instance) => {
          instance.input.closest('.date-range-box')?.classList.add('active');
        },
        onClose: (selectedDates, dateStr, instance) => {
          instance.input.closest('.date-range-box')?.classList.remove('active');
        }
    };
    Object.entries(rangeFieldConfig).forEach(([kind, cfg]) => {
      const input = get(cfg.input);
      if (!input) return;
      pickers[kind] = flatpickr(input, {
        mode: 'range',
        altInput: true,
        altInputClass: 'date-range-input',
        altFormat: dateLabel,
        dateFormat: 'Y-m-d',
        minDate: 'today',
        // 火車只能選開放訂票期間內的日期，更後面的日期反灰(後端 booking_search.py 也會再檢查)
        maxDate: kind === 'train' ? trainMaxDate() : null,
        locale: zhTw || null,  // 沒有中文語言檔(英文版或沒載入)時傳 null 用內建英文；傳 undefined 會讓日曆整個丟錯
        rangeSeparator: ' - ',
        showMonths: window.innerWidth > 720 ? 2 : 1,
        position: 'below',
        ...sharedHooks,
        onChange: (selectedDates, dateStr, instance) => {
          const [start, end] = selectedDates;
          const toIso = d => d ? flatpickr.formatDate(d, 'Y-m-d') : '';
          get(cfg.start).value = toIso(start);
          get(cfg.end).value = toIso(end);
          const badge = cfg.badge && get(cfg.badge);
          if (badge) {
            if (start && end) {
              const nights = Math.round((end - start) / 86400000);
              badge.textContent = nights + '晚';
              badge.hidden = false;
            } else {
              badge.hidden = true;
            }
          }
          renderSummary(instance);
        },
      });
    });
    // 多座城市每一段的日期：跟單程/來回同一套日曆(同樣的外觀與頁尾)，只是一次選一天
    window.createSingleDatePicker = (input, { minDate = 'today', onPick } = {}) => flatpickr(input, {
      mode: 'single',
      altInput: true,
      altInputClass: 'date-range-input',
      altFormat: dateLabel,
      dateFormat: 'Y-m-d',
      minDate,
      locale: zhTw || null,  // 沒有中文語言檔(英文版或沒載入)時傳 null 用內建英文；傳 undefined 會讓日曆整個丟錯
      showMonths: window.innerWidth > 720 ? 2 : 1,
      position: 'below',
      ...sharedHooks,
      onChange: (selectedDates, dateStr, instance) => {
        renderSummary(instance);
        if (onPick) onPick(selectedDates[0] || null);
      },
    });
  }

  const getMode = kind => document.querySelector('input[name="'+kind+'Mode"]:checked')?.value || (kind==='flight'?'roundtrip':'oneway');
  // 單程/來回 切到「多座城市」：已經選好的出發地、目的地、去程日期、人數，帶入第一段；第二段的出發地預設是第一段的目的地。
  // 多座城市那邊已經自己填過東西就不覆蓋。反過來切回單程/來回，單程那邊還是空的，就把第一段帶回去。
  const mcLegs = () => document.querySelectorAll('#multiCityLegs .multi-city-leg');
  const carryToMulti = () => {
    const legs = mcLegs(); if (!legs.length) return;
    const first = legs[0], from = first.querySelector('.mc-from'), to = first.querySelector('.mc-to'), date = first.querySelector('.mc-date');
    if (!from.value && !to.value && !date.value) {
      from.value = get('flightFrom') ? get('flightFrom').value : '';
      to.value = get('flightTo') ? get('flightTo').value : '';
      const departValue = get('flightDepart') ? get('flightDepart').value : '';
      if (date._flatpickr) { if (departValue) date._flatpickr.setDate(departValue, true, 'Y-m-d'); }
      else date.value = departValue;
    }
    const second = legs[1];
    if (second) { const nextFrom = second.querySelector('.mc-from'); if (!nextFrom.value && to.value) { nextFrom.value = to.value; nextFrom.dataset.auto = '1'; } }
    copyParty('flightPax', 'flightPaxMc');
  };
  // 乘客/艙等小視窗：用隱藏的 pax 欄位找到它的容器
  const fpOf = (id) => { const el = get(id); const root = el && el.closest('[data-fp]'); return root ? (root._fp || (window.flightPassengers && window.flightPassengers.init(root))) : null; };
  const copyParty = (fromId, toId) => { const a = fpOf(fromId), b = fpOf(toId); if (a && b) b.set(Object.assign({}, a.state)); };
  const carryFromMulti = () => {
    const legs = mcLegs(); if (!legs.length) return;
    const from = legs[0].querySelector('.mc-from').value, to = legs[0].querySelector('.mc-to').value;
    if (get('flightFrom') && !get('flightFrom').value && from) get('flightFrom').value = from;
    if (get('flightTo') && !get('flightTo').value && to) get('flightTo').value = to;
    copyParty('flightPaxMc', 'flightPax');
  };
  ['flight','train'].forEach(kind => {
    const radios=document.querySelectorAll('input[name="'+kind+'Mode"]'); if (!radios.length) return;
    const tripMode=query.get('trip_mode');
    if (tripMode) radios.forEach(r=>{r.checked = r.value===tripMode;});
    let prevMode = null;
    const sync=()=>{
      const mode=getMode(kind);
      const wasMulti = prevMode==='multicity';
      prevMode = mode;
      if (kind==='flight') {
        const isMulti = mode==='multicity';
        if (get('flightSingleFields')) get('flightSingleFields').hidden = isMulti;
        if (get('flightMultiFields')) get('flightMultiFields').hidden = !isMulti;
        if (get('flightDirectField')) get('flightDirectField').hidden = isMulti;
        if (isMulti) { carryToMulti(); return; }
        if (wasMulti) carryFromMulti();  // 只有「從多座城市切回來」才帶回，來回、單程互換不動人數
      }
      const picker=pickers[kind]; if (!picker) return;
      picker.set('mode', mode==='oneway' ? 'single' : 'range');
      picker.clear();
      get(ids[kind].return).value='';
    };
    radios.forEach(r=>r.addEventListener('change',sync));
    sync();
  });
  // 多座城市：動態新增/刪除航班段落，各段獨立填出發地/目的地/日期。
  (() => {
    const legsBox = get('multiCityLegs');
    if (!legsBox) return;
    const addBtn = get('mcAddLeg');
    const MAX_LEGS = 6;
    const renumber = () => {
      const legs = legsBox.querySelectorAll('.multi-city-leg');
      legs.forEach((leg, i) => {
        leg.querySelector('.multi-city-leg-badge').textContent = i + 1;
        leg.querySelector('.mc-remove').hidden = legs.length <= 2;
      });
      addBtn.disabled = legs.length >= MAX_LEGS;
    };
    const bindLeg = (leg) => {
      leg.querySelector('[data-mc-swap]').addEventListener('click', () => {
        const a = leg.querySelector('.mc-from'), b = leg.querySelector('.mc-to');
        const tmp = a.value; a.value = b.value; b.value = tmp;
      });
      leg.querySelector('.mc-remove').addEventListener('click', () => {
        if (legsBox.querySelectorAll('.multi-city-leg').length <= 2) return;
        leg.remove();
        renumber();
      });
    };
    // 新增航班用的乾淨範本(在綁日曆之前先複製，不然複製到的會帶著日曆的外掛元素)
    const legTemplate = (() => {
      const all = legsBox.querySelectorAll('.multi-city-leg');
      const t = all[all.length - 1].cloneNode(true);
      t.querySelectorAll('input').forEach(input => { input.value = ''; });
      return t;
    })();
    // 每一段的日期：下一段最早只能選到上一段的日期，不能比前一段更早
    const refreshMinDates = () => {
      let previous = null;
      legsBox.querySelectorAll('.multi-city-leg').forEach((leg) => {
        const instance = leg.querySelector('.mc-date')._flatpickr;
        if (!instance) return;
        instance.set('minDate', previous || 'today');
        const picked = instance.selectedDates[0] || null;
        if (picked && previous && picked < previous) instance.clear();
        previous = instance.selectedDates[0] || previous;
      });
    };
    const bindDate = (leg) => {
      const input = leg.querySelector('.mc-date');
      if (window.createSingleDatePicker) window.createSingleDatePicker(input, { onPick: refreshMinDates });
      else input.type = 'date';  // 日曆套件沒載入成功時退回瀏覽器內建的日期欄位
    };
    legsBox.querySelectorAll('.multi-city-leg').forEach((leg) => { bindLeg(leg); bindDate(leg); });
    // 上一段的目的地填好(或換掉)，下一段的出發地跟著帶入；下一段的出發地如果是使用者自己填的，就不去動它
    legsBox.addEventListener('change', (event) => {
      if (!event.target.classList.contains('mc-to')) return;
      const all = Array.from(legsBox.querySelectorAll('.multi-city-leg'));
      const next = all[all.indexOf(event.target.closest('.multi-city-leg')) + 1];
      if (!next) return;
      const nextFrom = next.querySelector('.mc-from'), value = event.target.value.trim();
      if (value && (!nextFrom.value.trim() || nextFrom.dataset.auto === '1')) { nextFrom.value = value; nextFrom.dataset.auto = '1'; }
    });
    legsBox.addEventListener('input', (event) => { if (event.target.classList.contains('mc-from')) delete event.target.dataset.auto; });
    addBtn.addEventListener('click', () => {
      const legs = legsBox.querySelectorAll('.multi-city-leg');
      if (legs.length >= MAX_LEGS) return;
      const clone = legTemplate.cloneNode(true);
      // 新增的這一段，出發地直接接上一段的目的地(台北→東京→首爾→…)，旅客只要填下一個目的地
      const previousTo = legs[legs.length - 1].querySelector('.mc-to').value.trim();
      if (previousTo) { const f = clone.querySelector('.mc-from'); f.value = previousTo; f.dataset.auto = '1'; }
      legsBox.appendChild(clone);
      bindLeg(clone);
      bindDate(clone);
      refreshMinDates();
      renumber();
    });
    renumber();
    get('mcSubmit').addEventListener('click', () => {
      const legs = Array.from(legsBox.querySelectorAll('.multi-city-leg'));
      const params = new URLSearchParams();
      params.set('legs', legs.length);
      const party = fpOf('flightPaxMc');
      if (party) Object.entries(party.params()).forEach(([k, v]) => params.set(k, v)); else params.set('pax', get('flightPaxMc').value || '1');
      legs.forEach((leg, i) => {
        // 後面幾段的出發地如果沒填，就用上一段的目的地
        const previousTo = i > 0 ? legs[i - 1].querySelector('.mc-to').value.trim() : '';
        params.set('from' + (i + 1), leg.querySelector('.mc-from').value.trim() || previousTo);
        params.set('to' + (i + 1), leg.querySelector('.mc-to').value.trim());
        params.set('date' + (i + 1), leg.querySelector('.mc-date').value);
      });
      location.href = '/visitor/flights/multi-city?' + params.toString();
    });
  })();
  // 出發地／目的地 中間那顆交換按鈕。
  document.querySelectorAll('[data-swap-a]').forEach(btn => {
    btn.addEventListener('click', () => {
      const a=get(btn.dataset.swapA), b=get(btn.dataset.swapB);
      if (!a || !b) return;
      const tmp=a.value; a.value=b.value; b.value=tmp;
    });
  });
  if (get('hotelDest')) get('hotelDest').placeholder='輸入目的地或住宿名稱';
  const active=()=>document.querySelector('.search-tab.active')?.dataset.tab;
  const current=active();
  Object.entries(ids[current] || {}).forEach(([key,id])=>{
    if(!query.has(key) || !get(id)) return;
    get(id).value=query.get(key);
    const picker=pickers[current];
    if (picker && (id===ids[current].checkin || id===ids[current].depart || id===ids[current].date)) {
      const endKey = current==='hotel' ? 'checkout' : 'return';
      const endVal = query.get(endKey);
      picker.setDate(endVal ? [query.get(key), endVal] : [query.get(key)], true);
    }
  });
  if (get('flightDirect')) get('flightDirect').checked = query.get('stops')==='direct';
  if (query.get('rail')) form.querySelectorAll('input[name="rail"]').forEach(r=>{r.checked = r.value===query.get('rail');});
  // 換高鐵／台鐵時，已填的站名可能是另一個系統才有的站，順便收起已開的車站清單，下次點開就是新系統的清單
  form.querySelectorAll('input[name="rail"]').forEach(r=>r.addEventListener('change',()=>{
    form.querySelectorAll('[data-station-autocomplete] + .city-suggest-panel').forEach(p=>{p.hidden=true;});
    noteText();
    if (pickers.train) pickers.train.set('maxDate', trainMaxDate());  // 高鐵、台鐵開放訂票天數不同
  }));
  const today=new Date();
  const isoToday=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
  form.querySelectorAll('input[type=date]').forEach(input=>input.min=isoToday);
  function error(input,message) {
    if (!input) return;
    input.setAttribute('aria-invalid','true');
    const p=document.createElement('p');p.className='booking-field-error';p.textContent=message;p.id=input.id+'-error';
    input.setAttribute('aria-describedby',p.id);input.after(p);
  }
  // 入住/退房、去程/回程這種日期範圍，底層其實是兩個隱藏欄位(checkin+checkout等)，
  // 用 error() 各自插訊息會在同一個欄位下面疊出兩則一樣的「請填寫此欄位」，所以錯誤訊息
  // 統一改成插在看得到的那個 .date-range-box 後面，跟目的地欄位的訊息位置、樣式一致。
  const DATE_RANGE_BOX = {hotel:'hotelDateBox', flight:'flightDateBox', train:'trainDateBox'};
  function rangeError(kind,message) {
    const box=get(DATE_RANGE_BOX[kind]); if (!box) return;
    box.setAttribute('aria-invalid','true');
    const p=document.createElement('p');p.className='booking-field-error';p.textContent=message;
    box.after(p);
  }
  function clear() {
    document.querySelectorAll('.booking-field-error').forEach(el=>el.remove());
    document.querySelectorAll('[aria-invalid=true]').forEach(el=>{el.removeAttribute('aria-invalid');el.removeAttribute('aria-describedby');});
  }
  const backend=JSON.parse(get('booking-errors-data')?.textContent || '{}');
  Object.entries(backend).forEach(([key,msg])=>error(get(ids[current]?.[key]) || document.querySelector('.booking-filters [name="'+key+'"]'),msg));
  const RANGE_KEYS={hotel:['checkin','checkout'],flight:['depart','return'],train:['date','return']};
  form.addEventListener('submit',event=>{
    const kind=active(); if (!ids[kind]) return;
    event.preventDefault();event.stopImmediatePropagation();clear();
    const params=new URLSearchParams();const values={};
    const mode=kind==='hotel'?'':getMode(kind);
    const rangeKeys=RANGE_KEYS[kind]||[];
    let failed=false,rangeMissing=false;
    Object.entries(ids[kind]).forEach(([key,id])=>{
      const input=get(id);if(!input || (key==='return' && mode==='oneway')) return;
      const value=input.value.trim();values[key]=value;params.set(key,value);
      const isRangeKey=rangeKeys.includes(key);
      let message='';
      if(!value){ if(isRangeKey){rangeMissing=true;} else {message='請填寫此欄位';} }
      else if(input.type==='date' && value<isoToday) message='日期不能早於今天';
      else if((key==='pax'||key==='guests') && (!/^\d+$/.test(value)||Number(value)<1||Number(value)>(kind==='flight'?9:99))) message='人數須介於 1 與 '+(kind==='flight'?9:99);
      if(message){error(input,message);failed=true;}
    });
    if(kind==='hotel'){[['hotelRooms','rooms'],['hotelChildren','children'],['hotelChildAges','child_ages']].forEach(([id,key])=>{const el=get(id);if(el)params.set(key,el.value);});}
    if(rangeMissing){rangeError(kind,'請選擇日期');failed=true;}
    const start=kind==='hotel'?'checkin':kind==='flight'?'depart':'date';
    const end=kind==='hotel'?'checkout':'return';
    if(!rangeMissing && values[end] && values[start] && (values[end]<values[start] || (kind==='hotel' && values[end]===values[start]))) {
      rangeError(kind,kind==='hotel'?'退房日期必須晚於入住':'回程不能早於去程');failed=true;
    }
    if(kind!=='hotel' && values.from && values.from===values.to){error(get(ids[kind].to),'出發地與目的地不能相同');failed=true;}
    if(failed){form.querySelector('[aria-invalid=true]')?.focus();return;}
    if(mode)params.set('trip_mode',mode);
    if(kind==='train')params.set('rail',form.querySelector('input[name="rail"]:checked')?.value||'thsr');
    if(kind==='flight'){const party=fpOf('flightPax');if(party)Object.entries(party.params()).forEach(([k,v])=>params.set(k,v));}
    if(kind==='flight' && get('flightDirect')?.checked)params.set('stops','direct');
    location.href='/visitor/'+({hotel:'hotels',flight:'flights',train:'trains'}[kind])+'?'+params.toString();
  },true);
  const note=get('searchNote');
  const noteText=()=>{if(note)note.textContent=active()==='hotel'?'住宿價格為即時報價參考，空房與實際價格請以訂房網站為準。':active()==='train'?(form.querySelector('input[name="rail"]:checked')?.value==='tra'?'台鐵':'高鐵')+'班表與票價來自交通部 TDX，座位與訂票請以官方售票系統為準。':'班表與票價為資料庫參考資料，尚未串接即時售票或優惠報價。';};
  noteText();document.querySelectorAll('.search-tab').forEach(el=>el.addEventListener('click',noteText));
})();

// 網址帶了乘客/艙等(例如從結果頁回首頁)就還原到小視窗
(() => {
  const q = new URLSearchParams(location.search);
  ['flightPax', 'flightPaxMc'].forEach((id) => {
    const el = document.getElementById(id), root = el && el.closest('[data-fp]');
    const fp = root && (root._fp || (window.flightPassengers && window.flightPassengers.init(root)));
    if (!fp || !(q.has('adults') || q.has('pax'))) return;
    const adults = q.has('adults') ? q.get('adults') : q.get('pax');
    fp.set({ adults: parseInt(adults, 10) || 1, children: parseInt(q.get('children'), 10) || 0, infants: parseInt(q.get('infants'), 10) || 0, cabin: q.get('cabin') && q.get('cabin') !== 'all' ? q.get('cabin') : '' });
  });
})();
