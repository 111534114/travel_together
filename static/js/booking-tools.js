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

  // 價格滑桿：跟搜尋表單(.search-panel)無關，首頁跟三個搜尋結果頁都可能有，所以獨立成一段，
  // 不能放在下面那段「找不到 .search-panel 表單就整段不執行」的邏輯裡面。
  document.querySelectorAll('[data-price-slider]').forEach((slider) => {
    const minInput = slider.querySelector('[name="min_price"]');
    const maxInput = slider.querySelector('[name="max_price"]');
    const fill = slider.querySelector('[data-price-fill]');
    const output = slider.closest('.price-slider-row')?.querySelector('[data-price-slider-output]');
    const sliderForm = slider.closest('form');
    const sliderMin = Number(minInput.min);
    const sliderMax = Number(minInput.max);
    const money = (value) => 'NT$ ' + Number(value).toLocaleString('zh-TW');
    const percent = (value) => ((Number(value) - sliderMin) / (sliderMax - sliderMin)) * 100;
    function render(changed) {
      if (Number(minInput.value) > Number(maxInput.value)) {
        if (changed === minInput) maxInput.value = minInput.value;
        else minInput.value = maxInput.value;
      }
      fill.style.left = percent(minInput.value) + '%';
      fill.style.right = (100 - percent(maxInput.value)) + '%';
      if (output) output.textContent = money(minInput.value) + ' ～ ' + money(maxInput.value);
    }
    minInput.addEventListener('input', () => render(minInput));
    maxInput.addEventListener('input', () => render(maxInput));
    minInput.addEventListener('change', () => sliderForm && sliderForm.requestSubmit());
    maxInput.addEventListener('change', () => sliderForm && sliderForm.requestSubmit());
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
  const pickers = {};
  if (typeof flatpickr !== 'undefined') {
    const zhTw = flatpickr.l10ns && flatpickr.l10ns.zh_tw;
    const rangeFieldConfig = {
      hotel: {input:'hotelDateRange', start:'hotelCheckin', end:'hotelCheckout', badge:'hotelDateBadge'},
      flight: {input:'flightDateRange', start:'flightDepart', end:'flightReturn', badge:null},
      train: {input:'trainDateRange', start:'trainDate', end:'trainReturn', badge:null},
    };
    // 日曆下方那排「10月22日 週四 - 10月23日 週五（1晚）」摘要文字，flatpickr 本身沒有這個，自己插進去。
    const renderSummary = (instance) => {
      if (!instance.summaryEl) return;
      const [start, end] = instance.selectedDates;
      const fmt = (d) => flatpickr.formatDate(d, 'n月j日 D', instance.config.locale);
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
    Object.entries(rangeFieldConfig).forEach(([kind, cfg]) => {
      const input = get(cfg.input);
      if (!input) return;
      pickers[kind] = flatpickr(input, {
        mode: 'range',
        altInput: true,
        altInputClass: 'date-range-input',
        altFormat: 'n月j日 D',
        dateFormat: 'Y-m-d',
        minDate: 'today',
        locale: zhTw || undefined,
        rangeSeparator: ' - ',
        showMonths: window.innerWidth > 720 ? 2 : 1,
        position: 'below',
        onReady: (selectedDates, dateStr, instance) => {
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
        },
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
  }

  const getMode = kind => document.querySelector('input[name="'+kind+'Mode"]:checked')?.value || (kind==='flight'?'roundtrip':'oneway');
  ['flight','train'].forEach(kind => {
    const radios=document.querySelectorAll('input[name="'+kind+'Mode"]'); if (!radios.length) return;
    const tripMode=query.get('trip_mode');
    if (tripMode) radios.forEach(r=>{r.checked = r.value===tripMode;});
    const sync=()=>{
      const mode=getMode(kind);
      if (kind==='flight') {
        const isMulti = mode==='multicity';
        if (get('flightSingleFields')) get('flightSingleFields').hidden = isMulti;
        if (get('flightMultiFields')) get('flightMultiFields').hidden = !isMulti;
        if (get('flightDirectField')) get('flightDirectField').hidden = isMulti;
        if (isMulti) return;
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
    legsBox.querySelectorAll('.multi-city-leg').forEach(bindLeg);
    addBtn.addEventListener('click', () => {
      const legs = legsBox.querySelectorAll('.multi-city-leg');
      if (legs.length >= MAX_LEGS) return;
      const clone = legs[legs.length - 1].cloneNode(true);
      clone.querySelectorAll('input').forEach(input => { input.value = ''; });
      legsBox.appendChild(clone);
      bindLeg(clone);
      renumber();
    });
    renumber();
    get('mcSubmit').addEventListener('click', () => {
      const legs = Array.from(legsBox.querySelectorAll('.multi-city-leg'));
      const params = new URLSearchParams();
      params.set('legs', legs.length);
      params.set('pax', get('flightPaxMc').value || '1');
      legs.forEach((leg, i) => {
        params.set('from' + (i + 1), leg.querySelector('.mc-from').value.trim());
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
  if (get('hotelDest')) get('hotelDest').placeholder='例如：九份、瑞芳、新北市 九份、飯店名稱';
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
  const today=new Date();
  const isoToday=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
  form.querySelectorAll('input[type=date]').forEach(input=>input.min=isoToday);
  function error(input,message) {
    if (!input) return;
    input.setAttribute('aria-invalid','true');
    const p=document.createElement('p');p.className='booking-field-error';p.textContent=message;p.id=input.id+'-error';
    input.setAttribute('aria-describedby',p.id);input.after(p);
  }
  function clear() {
    document.querySelectorAll('.booking-field-error').forEach(el=>el.remove());
    document.querySelectorAll('[aria-invalid=true]').forEach(el=>{el.removeAttribute('aria-invalid');el.removeAttribute('aria-describedby');});
  }
  const backend=JSON.parse(get('booking-errors-data')?.textContent || '{}');
  Object.entries(backend).forEach(([key,msg])=>error(get(ids[current]?.[key]) || document.querySelector('.booking-filters [name="'+key+'"]'),msg));
  form.addEventListener('submit',event=>{
    const kind=active(); if (!ids[kind]) return;
    event.preventDefault();event.stopImmediatePropagation();clear();
    const params=new URLSearchParams();const values={};
    const mode=kind==='hotel'?'':getMode(kind);
    let failed=false;
    Object.entries(ids[kind]).forEach(([key,id])=>{
      const input=get(id);if(!input || (key==='return' && mode==='oneway')) return;
      const value=input.value.trim();values[key]=value;params.set(key,value);
      let message='';
      if(!value) message='請填寫此欄位';
      else if(input.type==='date' && value<isoToday) message='日期不能早於今天';
      else if((key==='pax'||key==='guests') && (!/^\d+$/.test(value)||Number(value)<1||Number(value)>99)) message='人數須介於 1 與 99';
      if(message){error(input,message);failed=true;}
    });
    const start=kind==='hotel'?'checkin':kind==='flight'?'depart':'date';
    const end=kind==='hotel'?'checkout':'return';
    if(values[end] && values[start] && (values[end]<values[start] || (kind==='hotel' && values[end]===values[start]))) {
      error(get(ids[kind][end]),kind==='hotel'?'退房日期必須晚於入住':'回程不能早於去程');failed=true;
    }
    if(kind!=='hotel' && values.from && values.from===values.to){error(get(ids[kind].to),'出發地與目的地不能相同');failed=true;}
    if(failed){form.querySelector('[aria-invalid=true]')?.focus();return;}
    if(mode)params.set('trip_mode',mode);
    if(kind==='flight' && get('flightDirect')?.checked)params.set('stops','direct');
    location.href='/visitor/'+({hotel:'hotels',flight:'flights',train:'trains'}[kind])+'?'+params.toString();
  },true);
  const note=get('searchNote');
  const noteText=()=>{if(note)note.textContent=active()==='hotel'?'住宿為資料庫資訊，空房與日期價格請向業者確認。':'班表與票價為資料庫參考資料，尚未串接即時售票或優惠報價。';};
  noteText();document.querySelectorAll('.search-tab').forEach(el=>el.addEventListener('click',noteText));
})();
