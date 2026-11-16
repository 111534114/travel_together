(() => {
  // 住宿的「房間／成人／兒童」選擇器：按 +/− 即時更新隱藏欄位，所以就算沒按「確認」直接搜尋，送出的值也是對的。
  const LIMITS = { rooms: [1, 30], adults: [1, 60], children: [0, 20] };
  const MAX_GUESTS = 60;  // 成人 + 兒童的總上限
  const MAX_ADULTS_PER_ROOM = 4;  // 每間房最多 4 位成人，人多時房間數自動增加

  function init(root) {
    const toggle = root.querySelector('.guest-picker-toggle');
    const panel = root.querySelector('.guest-picker-panel');
    const agesBox = root.querySelector('[data-gp-ages]');
    const hidden = (key) => root.querySelector(`[data-gp-value="${key}"]`);
    const state = {
      rooms: Number(hidden('rooms').value) || 1,
      adults: Number(hidden('adults').value) || 2,
      children: Number(hidden('children').value) || 0,
      ages: hidden('ages').value ? hidden('ages').value.split(',').map(Number).filter((n) => n >= 0) : [],
    };

    const minRooms = () => Math.max(1, Math.ceil(state.adults / MAX_ADULTS_PER_ROOM));

    function normalize() {
      state.adults = Math.min(LIMITS.adults[1], Math.max(1, state.adults));
      state.children = Math.min(LIMITS.children[1], Math.max(0, state.children), MAX_GUESTS - state.adults);
      state.rooms = Math.min(LIMITS.rooms[1], Math.max(state.rooms, minRooms())); // 人多時自動補足房間
      state.adults = Math.max(state.adults, state.rooms); // 每間房至少一位成人
      while (state.ages.length < state.children) state.ages.push(8);
      state.ages.length = state.children;
    }

    function render() {
      normalize();
      const total = state.adults + state.children;
      ['rooms', 'adults', 'children'].forEach((key) => {
        const row = root.querySelector(`[data-gp-row="${key}"]`);
        row.querySelector('output').textContent = state[key];
        const min = key === 'rooms' ? minRooms() : key === 'adults' ? state.rooms : LIMITS[key][0];
        const full = key !== 'rooms' && total >= MAX_GUESTS;
        row.querySelector('[data-gp-minus]').disabled = state[key] <= min;
        row.querySelector('[data-gp-plus]').disabled = state[key] >= LIMITS[key][1] || full;
      });
      agesBox.replaceChildren();
      state.ages.forEach((age, index) => {
        const label = document.createElement('label');
        label.className = 'gp-age';
        label.append(`兒童 ${index + 1} 年齡`);
        const select = document.createElement('select');
        for (let value = 0; value <= 17; value += 1) {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = value === 0 ? '未滿 1 歲' : `${value} 歲`;
          option.selected = value === age;
          select.appendChild(option);
        }
        select.addEventListener('change', () => { state.ages[index] = Number(select.value); sync(); });
        label.appendChild(select);
        agesBox.appendChild(label);
      });
      sync();
    }

    function sync() {
      hidden('rooms').value = state.rooms;
      hidden('adults').value = state.adults;
      hidden('children').value = state.children;
      hidden('ages').value = state.ages.join(',');
      toggle.textContent = `${state.rooms} 房, ${state.adults}位成人, ${state.children}位兒童`;
    }

    root.querySelectorAll('[data-gp-row]').forEach((row) => {
      const key = row.dataset.gpRow;
      row.querySelector('[data-gp-minus]').addEventListener('click', () => { state[key] -= 1; render(); });
      row.querySelector('[data-gp-plus]').addEventListener('click', () => { state[key] += 1; render(); });
    });

    function setOpen(open) {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
    }
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    root.querySelector('.gp-confirm').addEventListener('click', () => setOpen(false));
    document.addEventListener('click', (event) => { if (!root.contains(event.target)) setOpen(false); });
    document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setOpen(false); });
    render();
  }

  document.querySelectorAll('[data-guest-picker]').forEach(init);
})();
