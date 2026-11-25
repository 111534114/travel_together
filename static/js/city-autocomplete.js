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
      resultsCoverStatic: true,
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
      renderResults: (results, onPick) => buildDetailList('全部車站', results.map((station) => {
        if (station.en && !STATION_EN[station.name]) STATION_EN[station.name] = station.en;  // 記下來，存最近搜尋時才換得回中文
        const en = isEnglishPage() && (station.en || STATION_EN[station.name]);
        return en ? { label: en, sub: station.systems.join('・'), value: en, notranslate: true }
          : { label: station.name, sub: station.systems.join('・'), value: station.name };
      }), onPick),
      toItems: (names) => toStationItems(names),
      emptyText: '沒有符合的車站。',
      resultsCoverStatic: true,
    },
    // 住宿目的地(data-hotel-autocomplete)：沒打字時列熱門目的地、台灣縣市，以及全世界各洲的所有國家；打字時查 Google 地點(全世界的國家、城市、景點、飯店)
    hotel: {
      recentKey: 'hotelSearch.recentPlaces',
      popularTitle: '熱門目的地',
      popular: ['台北市', '台中市', '高雄市', '日本', '韓國', '泰國', '越南', '新加坡', '香港', '美國', '英國', '法國'],
      regions: {
        '台灣北部': ['台北市', '新北市', '基隆市', '桃園市', '新竹市', '新竹縣', '宜蘭縣'],
        '台灣中部': ['苗栗縣', '台中市', '彰化縣', '南投縣', '雲林縣'],
        '台灣南部': ['嘉義市', '嘉義縣', '台南市', '高雄市', '屏東縣'],
        '台灣東部與離島': ['花蓮縣', '台東縣', '澎湖縣', '金門縣', '連江縣'],
        '東亞': ['中國', '北韓', '台灣', '日本', '澳門', '蒙古', '韓國', '香港'],
        '東南亞': ['印尼', '寮國', '新加坡', '東帝汶', '柬埔寨', '汶萊', '泰國', '緬甸', '菲律賓', '越南', '馬來西亞'],
        '南亞與中亞': ['不丹', '印度', '吉爾吉斯', '哈薩克', '土庫曼', '塔吉克', '孟加拉', '尼泊爾', '巴基斯坦', '斯里蘭卡', '烏茲別克', '阿富汗', '馬爾地夫'],
        '中東': ['亞塞拜然', '亞美尼亞', '以色列', '伊拉克', '伊朗', '卡達', '喬治亞', '土耳其', '巴勒斯坦自治區', '巴林', '敘利亞', '沙烏地阿拉伯', '科威特', '約旦', '葉門', '阿拉伯聯合大公國', '阿曼', '黎巴嫩'],
        '歐洲': ['丹麥', '俄羅斯', '保加利亞', '克羅埃西亞', '冰島', '匈牙利', '北馬其頓', '塞爾維亞', '奧地利', '希臘', '德國', '愛沙尼亞', '愛爾蘭', '拉脫維亞', '挪威', '捷克', '摩爾多瓦', '斯洛伐克', '斯洛維尼亞', '曼島', '根息', '比利時', '法國', '法羅群島', '波士尼亞與赫塞哥維納', '波蘭', '澤西島', '烏克蘭', '瑞典', '瑞士', '白俄羅斯', '盧森堡', '直布羅陀', '立陶宛', '羅馬尼亞', '義大利', '芬蘭', '英國', '荷蘭', '葡萄牙', '蒙特內哥羅', '西班牙', '賽普勒斯', '阿爾巴尼亞', '馬爾他'],
        '北美洲': ['加拿大', '墨西哥', '格陵蘭', '百慕達', '美國', '聖皮埃與密克隆群島'],
        '中美洲與加勒比海': ['千里達及托巴哥', '古巴', '哥斯大黎加', '土克斯及開科斯群島', '多明尼加共和國', '多米尼克', '安地卡及巴布達', '安奎拉', '宏都拉斯', '尼加拉瓜', '巴哈馬', '巴拿馬', '巴貝多', '格瑞那達', '波多黎各', '海地', '牙買加', '瓜地洛普', '瓜地馬拉', '美屬維京群島', '聖克里斯多福及尼維斯', '聖文森及格瑞那丁', '聖露西亞', '英屬維京群島', '荷屬安地列斯', '荷屬阿魯巴', '蒙哲臘', '薩爾瓦多', '貝里斯', '開曼群島', '馬丁尼克'],
        '南美洲': ['厄瓜多', '哥倫比亞', '委內瑞拉', '巴拉圭', '巴西', '智利', '法屬圭亞那', '烏拉圭', '玻利維亞', '福克蘭群島', '秘魯', '蓋亞那', '蘇利南', '阿根廷'],
        '大洋洲': ['中途島', '北馬利安納群島', '吉里巴斯', '吐瓦魯', '威克島', '密克羅尼西亞', '巴布亞紐幾內亞', '帛琉', '庫克群島', '強斯頓環礁', '斐濟', '新喀里多尼亞', '東加', '法屬玻里尼西亞', '澳洲', '瓦利斯群島和富圖那群島', '科克斯（基靈）群島', '紐埃島', '紐西蘭', '索羅門群島', '美屬薩摩亞', '聖誕島', '萬那杜', '薩摩亞', '諾福克島', '諾魯', '關島', '馬紹爾群島'],
        '非洲': ['中非共和國', '利比亞', '剛果（布拉薩）', '剛果（金夏沙）', '加彭', '南蘇丹', '南非', '厄利垂亞', '史瓦帝尼', '吉布地', '喀麥隆', '坦尚尼亞', '埃及', '塞內加爾', '塞席爾', '多哥', '奈及利亞', '安哥拉', '尚比亞', '尼日', '布吉納法索', '幾內亞', '幾內亞比索', '摩洛哥', '查德', '模里西斯', '波札那', '烏干達', '獅子山', '甘比亞', '留尼旺', '盧安達', '突尼西亞', '納米比亞', '索馬利亞', '維德角', '聖多美普林西比', '聖赫勒拿島', '肯亞', '茅利塔尼亞', '莫三比克', '葛摩', '蒲隆地', '蘇丹', '衣索比亞', '西撒哈拉', '象牙海岸', '貝南', '賴比瑞亞', '賴索托', '赤道幾內亞', '辛巴威', '迦納', '阿爾及利亞', '馬利', '馬拉威', '馬約特島', '馬達加斯加'],
      },
      matchTitle: '地區與國家',
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
    items.forEach(({ label, value, sub, notranslate }) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'city-suggest-item' + (notranslate ? ' notranslate' : '');
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

  // 英文版網頁(Google 翻譯)：車站清單要顯示並填入正確的英文站名。不能用 Google 翻出來的字，
  // 它會把「桃園」直譯成 Peach orchard 之類，後端對不到；輸入框的值本來也不會被翻譯，點了會填中文。
  const STATION_EN = {
    '南港': 'Nangang', '台北': 'Taipei', '板橋': 'Banqiao', '桃園': 'Taoyuan', '新竹': 'Hsinchu', '苗栗': 'Miaoli',
    '台中': 'Taichung', '彰化': 'Changhua', '雲林': 'Yunlin', '嘉義': 'Chiayi', '台南': 'Tainan', '左營': 'Zuoying',
    '基隆': 'Keelung', '松山': 'Songshan', '萬華': 'Wanhua', '樹林': 'Shulin', '中壢': 'Zhongli', '豐原': 'Fengyuan',
    '新烏日': 'Xinwuri', '員林': 'Yuanlin', '斗六': 'Douliu', '新營': 'Xinying', '新左營': 'Xinzuoying', '高雄': 'Kaohsiung',
    '屏東': 'Pingtung', '潮州': 'Chaozhou', '宜蘭': 'Yilan', '羅東': 'Luodong', '蘇澳新': "Su'aoxin", '花蓮': 'Hualien',
    '玉里': 'Yuli', '池上': 'Chishang', '台東': 'Taitung', '知本': 'Zhiben',
  };
  const isEnglishPage = () => /(?:^|;\s*)googtrans=\/[^/;]*\/en(?:;|$)/.test(document.cookie);
  // 英文站名 → 中文站名(大小寫不拘)；查不到回傳空字串
  const stationZh = (name) => {
    const lower = String(name).toLowerCase();
    return Object.keys(STATION_EN).find((zh) => STATION_EN[zh].toLowerCase() === lower) || '';
  };
  // 車站名換成目前網頁語言：英文版顯示英文、中文版顯示中文；最近搜尋一律存中文，才不會中文版冒出英文
  const stationInLanguage = (name) => (isEnglishPage() ? (STATION_EN[name] || name) : (stationZh(name) || name));
  function toStationItems(names) {
    const seen = new Set();  // 最近搜尋可能同時有「台北」和「Taipei」，換成同一種語言後只留一個
    return names.map(stationInLanguage)
      .filter((name) => !seen.has(name) && seen.add(name))
      .map((name) => ({ label: name, value: name, notranslate: isEnglishPage() }));
  }

  // 機票的機場選單(像 Agoda)：每個城市一個標題列(圖釘＋城市名＋右側「所有機場」)，
  // 底下縮排列出該城市的機場(飛機圖示＋機場名稱＋右側代碼)。
  const PLANE_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>';
  const GROUP_PIN_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z"/></svg>';

  function cityLabelOf(airport) {
    if (airport.label_zh) return airport.label_zh;
    if (airport.city_zh) return airport.city_zh;
    // 沒有整理過的中文城市名：用機場中文名去掉「國際機場」「機場」當城市名，再不行才用英文
    const stripped = (airport.name_zh || '').replace(/(國際)?(機場|航空站)$/, '');
    return stripped || airport.city;
  }

  // 城市標題列：城市不只一個機場時可以點(選「所有機場」)，只有一個機場時是灰色、不能點
  function makeGroupHeader(label, onPick, clickable, countryLabel) {
    const header = document.createElement(clickable ? 'button' : 'div');
    if (clickable) header.type = 'button';
    header.className = 'city-suggest-group' + (clickable ? '' : ' is-muted');
    const icon = document.createElement('span');
    icon.className = 'city-suggest-icon';
    icon.innerHTML = GROUP_PIN_ICON;
    const name = document.createElement('span');
    name.className = 'city-suggest-group-name';
    name.textContent = countryLabel ? `${label}, ${countryLabel}` : label;  // 像 Agoda 的「關島, 關島」「倫敦, 英國」
    const tag = document.createElement('span');
    tag.className = 'city-suggest-group-tag';
    tag.textContent = '所有機場';
    header.append(icon, name, tag);
    if (clickable) {
      header.addEventListener('mousedown', (event) => {
        event.preventDefault();
        onPick(`${label}（所有機場）`);
      });
    }
    return header;
  }

  function makeAirportItem(airport, onPick) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'city-suggest-airport';
    const icon = document.createElement('span');
    icon.className = 'city-suggest-icon';
    icon.innerHTML = PLANE_ICON;
    const name = document.createElement('span');
    name.className = 'city-suggest-airport-name';
    name.textContent = airport.name_zh || airport.name;
    name.title = airport.name;  // 滑鼠移上去看英文原名
    const code = document.createElement('span');
    code.className = 'city-suggest-airport-code';
    code.textContent = airport.iata;
    item.append(icon, name, code);
    // 只飛國內線的小機場(台南、花蓮⋯)：選單顯示機場名稱，選了之後輸入框變成縣市名，像 Agoda 的「台南市 (TNN)」
    const mainName = airport.label_zh || airport.name_zh || airport.name;
    item.addEventListener('mousedown', (event) => {
      event.preventDefault();
      onPick(`${mainName} (${airport.iata})`);
    });
    return item;
  }

  function buildAirportList(title, airports, onPick) {
    if (!airports.length) return null;
    const section = document.createElement('div');
    section.className = 'city-suggest-section city-suggest-section--airports';
    const list = document.createElement('div');
    list.className = 'city-suggest-list';

    // 北海道、九州這種涵蓋多個城市的地區：最前面放一列「地區・所有機場」
    if (airports[0].region && airports.every((airport) => airport.region === airports[0].region)) {
      list.appendChild(makeGroupHeader(airports[0].region, onPick, true));
      airports.forEach((airport) => list.appendChild(makeAirportItem(airport, onPick)));
      section.appendChild(list);
      return section;
    }

    // 後端已經把同一個城市的機場排在一起了，連續幾筆同一個城市就是同一組
    let index = 0;
    while (index < airports.length) {
      let groupEnd = index + 1;
      while (groupEnd < airports.length
        && airports[groupEnd].city === airports[index].city
        && airports[groupEnd].country === airports[index].country) {
        groupEnd += 1;
      }
      const group = airports.slice(index, groupEnd);
      // 每個城市都放「城市・所有機場」標題列(正常顏色、可以點)，底下縮排列出該城市的機場
      list.appendChild(makeGroupHeader(cityLabelOf(group[0]), onPick, true, group[0].country_zh));
      group.forEach((airport) => list.appendChild(makeAirportItem(airport, onPick)));
      index = groupEnd;
    }

    section.appendChild(list);
    return section;
  }

  // 車站、住宿地區的結果跟機場一樣用一欄直式清單：第一行名稱，第二行補充說明(高鐵/台鐵、幾間住宿)
  // 住宿目的地的小圖示：住宿用大樓、國家／城市／景點用圖釘(內嵌 SVG，不用 emoji)
  const PIN_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z"/></svg>';
  const STAR_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="currentColor" d="m12 2.5 2.95 6 6.55.95-4.75 4.62 1.12 6.53L12 17.55 6.13 20.6l1.12-6.53L2.5 9.45l6.55-.95L12 2.5Z"/></svg>';
  const BUILDING_ICON = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" d="M5 21V4h10v17M15 9h4v12M3 21h18M8 8h2M8 12h2M8 16h2"/></svg>';

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
    items.forEach(({ label, sub, value, notranslate, kind, city, country }) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'city-suggest-item city-suggest-item--airport';
      const text = document.createElement('span');
      text.className = 'city-suggest-item-text';
      const primary = document.createElement('span');
      primary.className = 'city-suggest-item-primary' + (notranslate ? ' notranslate' : '');
      if (kind === 'popular') {
        // 熱門城市：「倫敦, **英國**」+ 「人氣王」標籤
        primary.append(document.createTextNode(city + ', '));
        const bold = document.createElement('b');
        bold.textContent = country;
        const badge = document.createElement('span');
        badge.className = 'city-suggest-badge';
        badge.textContent = '人氣王';
        primary.append(bold, badge);
      } else {
        primary.textContent = label;
      }
      const secondary = document.createElement('span');
      secondary.className = 'city-suggest-item-secondary';
      secondary.textContent = sub;
      text.appendChild(primary);
      text.appendChild(secondary);
      if (kind) {
        item.classList.add('city-suggest-item--icon');
        const icon = document.createElement('span');
        icon.className = 'city-suggest-icon';
        icon.innerHTML = kind === 'lodging' ? BUILDING_ICON : kind === 'popular' ? STAR_ICON : PIN_ICON;
        item.appendChild(icon);
      }
      item.appendChild(text);
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
      const toItems = mode.toItems || toPlainItems;
      const recentSection = buildSection('最近搜尋', toItems(readRecent(mode.recentKey)), onPick);
      if (recentSection) panel.appendChild(recentSection);
      const popularSection = buildSection(mode.popularTitle, toItems(mode.popular), onPick);
      if (popularSection) panel.appendChild(popularSection);
      Object.entries(mode.regions).forEach(([region, cities]) => {
        const section = buildSection(region, toItems(cities), onPick);
        if (section) panel.appendChild(section);
      });
      return;
    }
    const lowerKeyword = keyword.toLowerCase();
    const matches = mode.all.filter((city) => city.includes(keyword)
      || (mode.toItems && (STATION_EN[city] || '').toLowerCase().includes(lowerKeyword)));
    const section = buildSection(mode.matchTitle, (mode.toItems || toPlainItems)(matches), onPick);
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
    // 「全部車站」已經包含上面的常用車站，結果回來後就把常用車站那區拿掉，避免同一站出現兩次
    if (mode.resultsCoverStatic) panel.querySelectorAll('.city-suggest-section').forEach((el) => el.remove());
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

  // 表單上選了「高鐵」或「台鐵」(name="rail" 的單選鈕或下拉選單)，車站清單就只列該系統的車站，避免選到另一個系統沒有的站
  const RAIL_POPULAR = {
    thsr: ['南港', '台北', '板橋', '桃園', '新竹', '台中', '嘉義', '台南', '左營'],
    tra: ['台北', '板橋', '桃園', '新竹', '台中', '台南', '高雄', '宜蘭', '花蓮', '台東'],
  };
  const stationModeCache = {};
  function stationMode(input) {
    const railField = input.form && input.form.elements.namedItem('rail');
    const rail = railField ? railField.value : '';
    if (!RAIL_POPULAR[rail]) return MODES.station;
    if (!stationModeCache[rail]) {
      const regions = Object.fromEntries(Object.entries(MODES.station.regions)
        .filter(([region]) => (rail === 'thsr') === region.startsWith('高鐵')));
      stationModeCache[rail] = Object.assign({}, MODES.station, {
        recentKey: MODES.station.recentKey + '.' + rail,
        popular: RAIL_POPULAR[rail],
        regions,
        all: Array.from(new Set(Object.values(regions).flat())),
        searchSuffix: '&rail=' + rail,
      });
    }
    return stationModeCache[rail];
  }

  // showAll：剛點進輸入框時，就算裡面已經有字(例如搜尋結果頁帶回來的「台北」)也列出完整清單，
  // 不然只會看到跟原本那個字相符的一兩筆；使用者開始打字才依輸入內容篩選。
  function openPanel(input, showAll = false) {
    const panel = getOrCreatePanel(input);
    const keyword = showAll ? '' : input.value.trim();
    const mode = input.matches('[data-station-autocomplete]') ? stationMode(input)
      : input.matches('[data-hotel-autocomplete]') ? MODES.hotel : MODES.city;
    const onPick = (value) => {
      input.value = value;
      saveRecent(mode.recentKey, mode.toItems ? (stationZh(value) || value) : value);
      panel.hidden = true;
      // 程式直接改 input.value 不會觸發任何事件；多座城市的目的地要通知表單，下一段的出發地才能跟著填
      if (input.classList.contains('mc-to')) input.dispatchEvent(new Event('change', { bubbles: true }));
    };
    renderStaticPanel(panel, keyword, onPick, mode);
    panel.hidden = false;

    const existingTimer = debounceTimers.get(input);
    if (existingTimer) clearTimeout(existingTimer);
    if (!keyword) return;

    const timer = setTimeout(() => {
      fetch(mode.searchUrl + encodeURIComponent(keyword) + (mode.searchSuffix || ''))
        .then((resp) => (resp.ok ? resp.json() : []))
        .then((results) => {
          if (input.value.trim() !== keyword) return; // 使用者已經改打別的字，這批結果過時了，不要顯示
          appendWorldwideSection(panel, results, onPick, mode);
        })
        .catch(() => {});
    }, SEARCH_DEBOUNCE_MS);
    debounceTimers.set(input, timer);
  }

  // 結果頁的出發站/到達站是照網址帶回來的(可能是另一種語言搜尋的)，載入時換成目前網頁的語言
  document.querySelectorAll('[data-station-autocomplete]').forEach((input) => {
    if (input.value) input.value = stationInLanguage(input.value.trim());
  });

  document.addEventListener('focus', (event) => {
    const input = event.target;
    if (!(input instanceof HTMLElement) || !input.matches(AUTOCOMPLETE_SELECTOR)) return;
    openPanel(input, true);
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
