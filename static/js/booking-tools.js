(() => {
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
  document.querySelectorAll('[data-price-range]').forEach(range => {
    const minInput = range.querySelector('[name="min_price"]');
    const maxInput = range.querySelector('[name="max_price"]');
    const minOutput = range.querySelector('[data-min-output]');
    const maxOutput = range.querySelector('[data-max-output]');
    const summary = range.querySelector('[data-price-summary]');
    const money = value => 'NT$ ' + Number(value).toLocaleString('zh-TW');
    function sync(changed) {
      if (Number(minInput.value) > Number(maxInput.value)) {
        if (changed === minInput) maxInput.value = minInput.value;
        else minInput.value = maxInput.value;
      }
      minOutput.textContent = money(minInput.value);
      maxOutput.textContent = money(maxInput.value);
      summary.textContent = money(minInput.value) + ' ～ ' + money(maxInput.value);
    }
    minInput.addEventListener('input', () => sync(minInput));
    maxInput.addEventListener('input', () => sync(maxInput));
    sync();
  });
  const trainDate = get('trainDate');
  if (trainDate && !get('trainReturn')) {
    const field = document.createElement('div'); field.className='field';
    const label=document.createElement('label'); label.htmlFor='trainReturn';label.textContent='回程日期';
    const input=document.createElement('input');input.id='trainReturn';input.type='date';
    field.append(label,input);trainDate.closest('.field').after(field);
  }
  ['flight','train'].forEach(kind => {
    const start=get(ids[kind].from); if (!start) return;
    const field=document.createElement('div');field.className='field';
    const label=document.createElement('label');label.htmlFor=kind+'Mode';label.textContent='行程類型';
    const select=document.createElement('select');select.id=kind+'Mode';select.className='booking-mode';
    [['oneway','單程'],['roundtrip','來回']].forEach(([v,t])=>select.add(new Option(t,v)));
    select.value=query.get('trip_mode') || (kind==='flight'?'roundtrip':'oneway');
    field.append(label,select);start.closest('.field').before(field);
    const sync=()=>{get(ids[kind].return).closest('.field').hidden=select.value==='oneway';};
    select.addEventListener('change',sync);sync();
  });
  if (get('hotelDest')) get('hotelDest').placeholder='例如：九份、瑞芳、新北市 九份、飯店名稱';
  const active=()=>document.querySelector('.search-tab.active')?.dataset.tab;
  const current=active();
  Object.entries(ids[current] || {}).forEach(([key,id])=>{if(query.has(key) && get(id)) get(id).value=query.get(key);});
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
    const mode=kind==='hotel'?'':get(kind+'Mode').value;
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
    location.href='/visitor/'+({hotel:'hotels',flight:'flights',train:'trains'}[kind])+'?'+params.toString();
  },true);
  const note=get('searchNote');
  const noteText=()=>{if(note)note.textContent=active()==='hotel'?'住宿為資料庫資訊，空房與日期價格請向業者確認。':'班表與票價為資料庫參考資料，尚未串接即時售票或優惠報價。';};
  noteText();document.querySelectorAll('.search-tab').forEach(el=>el.addEventListener('click',noteText));
})();
