(() => {
  // 機票搜尋表單的出發地/目的地輸入框：
  // - 沒打字時(focus)：顯示「最近搜尋」+「熱門城市」+「依地區」的中文城市快速挑選清單(手動整理的常見城市)。
  // - 開始打字時：先同步顯示上面那份中文城市清單裡符合的，同時打 /api/city-search 問後端的全球機場資料庫
  //   (database/airports_data.csv，約 6000 筆真實機場資料，含英文城市名/機場名/IATA 代碼)，
  //   找到的結果會補一個「全球機場」區塊，這樣打任何城市的英文名字或機場代碼都找得到，不是只有手動整理的那些城市。
  const POPULAR_CITIES = ['台北', '東京', '首爾', '大阪', '釜山', '沖繩', '香港', '曼谷', '新加坡'];
  const CITY_REGIONS = {
    '台灣': ['台北', '桃園'],
    '日本': ['東京', '大阪', '名古屋', '福岡', '札幌', '沖繩', '京都'],
    '韓國': ['首爾', '釜山'],
    '港澳中國': ['香港', '澳門', '上海', '北京', '廣州', '深圳'],
    '東南亞': ['曼谷', '新加坡', '吉隆坡', '雅加達', '馬尼拉', '胡志明市', '河內', '峇里島', '清邁'],
    '南亞': ['新德里', '孟買'],
    '大洋洲': ['雪梨', '墨爾本', '奧克蘭', '布里斯本'],
    '北美': ['紐約', '洛杉磯', '舊金山', '芝加哥', '西雅圖', '溫哥華', '多倫多', '拉斯維加斯', '夏威夷'],
    '歐洲': ['倫敦', '巴黎', '法蘭克福', '羅馬', '阿姆斯特丹', '蘇黎世', '維也納', '馬德里'],
    '中東': ['伊斯坦堡', '莫斯科', '杜拜', '多哈'],
  };
  const RECENT_MAX = 5;
  const SEARCH_DEBOUNCE_MS = 250;
  const AUTOCOMPLETE_SELECTOR = '[data-city-autocomplete], [data-station-autocomplete], [data-hotel-autocomplete]';

  // 高鐵／火車票的出發站/到達站輸入框(data-station-autocomplete)用同一套面板，只是清單換成車站：
  // 沒打字時列常用車站，打字時再打 /api/station-search 查高鐵 12 站＋台鐵全部車站(交通部 TDX 車站資料)。
  const MODES = {
    city: {
      recentKey: 'flightSearch.recentCities',
      popularTitle: '熱門城市',
      popular: POPULAR_CITIES,
      regions: CITY_REGIONS,
      matchTitle: '常見城市',
      searchUrl: '/api/city-search?q=',
      renderResults: (results, onPick) => buildAirportList('全球機場', results, onPick),
      emptyText: '沒有符合的城市或機場。',
    },
    station: {
      recentKey: 'trainSearch.recentStations',
      popularTitle: '熱門車站',
      popular: ['台北', '板橋', '桃園', '新竹', '台中', '台南', '左營', '高雄', '花蓮'],
      regions: {
        '高鐵': ['南港', '台北', '板橋', '桃園', '新竹', '苗栗', '台中', '彰化', '雲林', '嘉義', '台南', '左營'],
        '台鐵・北部': ['基隆', '南港', '松山', '台北', '萬華', '板橋', '樹林', '桃園', '中壢', '新竹'],
        '台鐵・中部': ['苗栗', '豐原', '台中', '新烏日', '彰化', '員林', '斗六'],
        '台鐵・南部': ['嘉義', '新營', '台南', '新左營', '高雄', '屏東', '潮州'],
        '台鐵・東部': ['宜蘭', '羅東', '蘇澳新', '花蓮', '玉里', '池上', '台東', '知本'],
      },
      matchTitle: '常用車站',
      searchUrl: '/api/station-search?q=',
      renderResults: (results, onPick) => buildDetailList('全部車站', results.map((station) => (
        { label: station.name, sub: station.systems.join('・'), value: station.name })), onPick),
      emptyText: '沒有符合的車站。',
    },
    // 住宿目的地(data-hotel-autocomplete)目前只有台灣：沒打字時列台灣縣市，打字時查資料庫裡住宿的地區與名稱
    hotel: {
      recentKey: 'hotelSearch.recentPlaces',
      popularTitle: '熱門地區',
      popular: ['台北市', '新北市', '台中市', '台南市', '高雄市', '花蓮縣', '宜蘭縣', '屏東縣', '南投縣'],
      regions: {
        '北部': ['台北市', '新北市', '基隆市', '桃園市', '新竹市', '新竹縣', '宜蘭縣'],
        '中部': ['苗栗縣', '台中市', '彰化縣', '南投縣', '雲林縣'],
        '南部': ['嘉義市', '嘉義縣', '台南市', '高雄市', '屏東縣'],
        '東部': ['花蓮縣', '台東縣'],
        '離島': ['澎湖縣', '金門縣', '連江縣'],
      },
      matchTitle: '台灣縣市',
      searchUrl: '/api/hotel-place-search?q=',
      renderResults: (results, onPick) => buildDetailList('地區與住宿', results, onPick),
      emptyText: '沒有符合的地區或住宿。',
    },
  };
  Object.values(MODES).forEach((mode) => {
    mode.all = Array.from(new Set(Object.values(mode.regions).flat()));
  });

  function readRecent(key) {
    try {
      const raw = localStorage.getItem(key);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (error) {
      return [];
    }
  }

  function saveRecent(key, label) {
    try {
      const list = readRecent(key).filter((item) => item !== label);
      list.unshift(label);
      localStorage.setItem(key, JSON.stringify(list.slice(0, RECENT_MAX)));
    } catch (error) {
      // 無痕視窗或封鎖網站資料時 localStorage 會噴錯，忽略即可，不影響搜尋功能本身
    }
  }

  function buildSection(title, items, onPick) {
    if (!items.length) return null;
    const section = document.createElement('div');
    section.className = 'city-suggest-section';
    const heading = document.createElement('span');
    heading.className = 'city-suggest-title';
    heading.textContent = title;
    section.appendChild(heading);
    const grid = document.createElement('div');
    grid.className = 'city-suggest-grid';
    items.forEach(({ label, value, sub }) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'city-suggest-item';
      item.textContent = sub ? `${label}・${sub}` : label;
      item.addEventListener('mousedown', (event) => {
        event.preventDefault(); // 避免 input 先觸發 blur 把面板關掉，導致點擊沒反應
        onPick(value);
      });
      grid.appendChild(item);
    });
    section.appendChild(grid);
    return section;
  }

  function toPlainItems(names) {
    return names.map((name) => ({ label: name, value: name }));
  }

  // 機場名稱+城市+國家+代碼這種比較長的文字，放進原本給城市名字用的三欄格狀排版會擠爆，
  // 改用一欄直式清單，每個項目分兩行(機場名稱為主、城市國家代碼為輔)。
  function makeAirportItem(airport, onPick, { isAllAirports = false } = {}) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'city-suggest-item city-suggest-item--airport';
    const primary = document.createElement('span');
    primary.className = 'city-suggest-item-primary';
    const secondary = document.createElement('span');
    secondary.className = 'city-suggest-item-secondary';

    if (isAllAirports) {
      const cityLabel = airport.city_zh || airport.city;
      primary.textContent = cityLabel + '・所有機場';
      secondary.textContent = airport.country;
      item.appendChild(primary);
      item.appendChild(secondary);
      item.addEventListener('mousedown', (event) => {
        event.preventDefault();
        onPick(`${cityLabel}（所有機場）`);
      });
      return item;
    }

    primary.textContent = airport.name_zh || airport.name;
    // 有中文機場名稱時，第二行補上英文原名方便對照；沒有中文名稱時，第二行維持城市/國家/代碼
    secondary.textContent = airport.name_zh
      ? `${airport.name}・${airport.iata}`
      : `${airport.city}, ${airport.country}・${airport.iata}`;
    item.appendChild(primary);
    item.appendChild(secondary);
    item.addEventListener('mousedown', (event) => {
      event.preventDefault();
      onPick(`${airport.name_zh || airport.name} (${airport.iata})`);
    });
    return item;
  }

  function buildAirportList(title, airports, onPick) {
    if (!airports.length) return null;
    const section = document.createElement('div');
    section.className = 'city-suggest-section';
    const heading = document.createElement('span');
    heading.className = 'city-suggest-title';
    heading.textContent = title;
    section.appendChild(heading);
    const list = document.createElement('div');
    list.className = 'city-suggest-list';

    // 後端已經把同一個城市的機場排在一起了，這裡偵測連續幾筆是不是同一個城市，
    // 是的話(表示這個城市不只一個機場)在最前面插一個「城市・所有機場」的選項。
    let index = 0;
    while (index < airports.length) {
      let groupEnd = index + 1;
      while (groupEnd < airports.length
        && airports[groupEnd].city === airports[index].city
        && airports[groupEnd].country === airports[index].country) {
        groupEnd += 1;
      }
      const group = airports.slice(index, groupEnd);
      if (group.length > 1) {
        list.appendChild(makeAirportItem(group[0], onPick, { isAllAirports: true }));
      }
      group.forEach((airport) => list.appendChild(makeAirportItem(airport, onPick)));
      index = groupEnd;
    }

    section.appendChild(list);
    return section;
  }

  // 車站、住宿地區的結果跟機場一樣用一欄直式清單：第一行名稱，第二行補充說明(高鐵/台鐵、幾間住宿)
  function buildDetailList(title, items, onPick) {
    if (!items.length) return null;
    const section = document.createElement('div');
    section.className = 'city-suggest-section';
    const heading = document.createElement('span');
    heading.className = 'city-suggest-title';
    heading.textContent = title;
    section.appendChild(heading);
    const list = document.createElement('div');
    list.className = 'city-suggest-list';
    items.forEach(({ label, sub, value }) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'city-suggest-item city-suggest-item--airport';
      const primary = document.createElement('span');
      primary.className = 'city-suggest-item-primary';
      primary.textContent = label;
      const secondary = document.createElement('span');
      secondary.className = 'city-suggest-item-secondary';
      secondary.textContent = sub;
      item.appendChild(primary);
      item.appendChild(secondary);
      item.addEventListener('mousedown', (event) => {
        event.preventDefault();
        onPick(value);
      });
      list.appendChild(item);
    });
    section.appendChild(list);
    return section;
  }

  function renderStaticPanel(panel, keyword, onPick, mode) {
    panel.innerHTML = '';
    if (!keyword) {
      const recentSection = buildSection('最近搜尋', toPlainItems(readRecent(mode.recentKey)), onPick);
      if (recentSection) panel.appendChild(recentSection);
      const popularSection = buildSection(mode.popularTitle, toPlainItems(mode.popular), onPick);
      if (popularSection) panel.appendChild(popularSection);
      Object.entries(mode.regions).forEach(([region, cities]) => {
        const section = buildSection(region, toPlainItems(cities), onPick);
        if (section) panel.appendChild(section);
      });
      return;
    }
    const matches = mode.all.filter((city) => city.includes(keyword));
    const section = buildSection(mode.matchTitle, toPlainItems(matches), onPick);
    if (section) panel.appendChild(section);
  }

  function appendWorldwideSection(panel, results, onPick, mode) {
    const existingEmpty = panel.querySelector('.city-suggest-empty');
    if (existingEmpty) existingEmpty.remove();
    const existingWorld = panel.querySelector('[data-world-section]');
    if (existingWorld) existingWorld.remove();

    if (!results.length) {
      if (!panel.children.length) {
        const empty = document.createElement('p');
        empty.className = 'city-suggest-empty';
        empty.textContent = mode.emptyText;
        panel.appendChild(empty);
      }
      return;
    }
    const section = mode.renderResults(results, onPick);
    if (section) {
      section.setAttribute('data-world-section', '1');
      panel.appendChild(section);
    }
  }

  // 用事件代理(在 document 上監聽，判斷 event.target 符不符合)而不是對每個欄位個別綁定，
  // 這樣多城市航班「添加航班」用 cloneNode 動態複製出來的新出發地/目的地欄位也會自動生效，
  // 不用每次新增一段航班就重新初始化一次。
  function getOrCreatePanel(input) {
    let panel = input.nextElementSibling;
    if (!panel || !panel.classList.contains('city-suggest-panel')) {
      panel = document.createElement('div');
      panel.className = 'city-suggest-panel';
      panel.hidden = true;
      input.insertAdjacentElement('afterend', panel);
    }
    return panel;
  }

  const debounceTimers = new WeakMap();

  function openPanel(input) {
    const panel = getOrCreatePanel(input);
    const keyword = input.value.trim();
    const mode = input.matches('[data-station-autocomplete]') ? MODES.station
      : input.matches('[data-hotel-autocomplete]') ? MODES.hotel : MODES.city;
    const onPick = (value) => {
      input.value = value;
      saveRecent(mode.recentKey, value);
      panel.hidden = true;
    };
    renderStaticPanel(panel, keyword, onPick, mode);
    panel.hidden = false;

    const existingTimer = debounceTimers.get(input);
    if (existingTimer) clearTimeout(existingTimer);
    if (!keyword) return;

    const timer = setTimeout(() => {
      fetch(mode.searchUrl + encodeURIComponent(keyword))
        .then((resp) => (resp.ok ? resp.json() : []))
        .then((results) => {
          if (input.value.trim() !== keyword) return; // 使用者已經改打別的字，這批結果過時了，不要顯示
          appendWorldwideSection(panel, results, onPick, mode);
        })
        .catch(() => {});
    }, SEARCH_DEBOUNCE_MS);
    debounceTimers.set(input, timer);
  }

  document.addEventListener('focus', (event) => {
    const input = event.target;
    if (!(input instanceof HTMLElement) || !input.matches(AUTOCOMPLETE_SELECTOR)) return;
    openPanel(input);
  }, true);

  document.addEventListener('input', (event) => {
    const input = event.target;
    if (!(input instanceof HTMLElement) || !input.matches(AUTOCOMPLETE_SELECTOR)) return;
    openPanel(input);
  });

  document.addEventListener('blur', (event) => {
    const input = event.target;
    if (!(input instanceof HTMLElement) || !input.matches(AUTOCOMPLETE_SELECTOR)) return;
    const panel = input.nextElementSibling;
    if (panel && panel.classList.contains('city-suggest-panel')) panel.hidden = true;
  }, true);
})();
