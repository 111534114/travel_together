(() => {
  // 點住宿卡片(或「查看詳情」)開啟詳情視窗。資料來自搜尋結果卡片上的 data-detail，不會再打 API。
  const money = (twd) => (window.siteCurrency ? window.siteCurrency.fmt(twd) : `NT$ ${Math.round(twd).toLocaleString('zh-TW')}`);
  let backdrop = null;
  let lastFocus = null;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Google 的圖片網址結尾 =s10000 是原圖尺寸，載入太大，視窗只需要約 1200 寬
  function sized(url) {
    return url.replace(/=s10000$/, '=s1200');
  }

  function close() {
    closeReviews();
    if (!backdrop) return;
    backdrop.remove();
    backdrop = null;
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  }

  function section(title) {
    const box = el('div', 'hd-section');
    box.appendChild(el('h3', '', title));
    return box;
  }

  function buildGallery(d) {
    const gallery = el('div', 'hd-gallery');
    const main = el('div', 'hd-main');
    if (!d.images.length) {
      main.appendChild(el('div', 'hotel-photo-empty', '沒有圖片'));
      gallery.appendChild(main);
      return gallery;
    }
    const image = el('img');
    image.alt = d.name;
    image.referrerPolicy = 'no-referrer';
    main.appendChild(image);
    const thumbs = el('div', 'hd-thumbs');
    const thumbNodes = d.images.map((url, index) => {
      const thumb = el('img');
      thumb.src = sized(url).replace(/=s1200$/, '=s200');
      thumb.alt = `${d.name} 第 ${index + 1} 張`;
      thumb.referrerPolicy = 'no-referrer';
      thumb.addEventListener('click', () => show(index));
      thumbs.appendChild(thumb);
      return thumb;
    });
    let current = 0;
    function show(index) {
      current = (index + d.images.length) % d.images.length;
      image.src = sized(d.images[current]);
      thumbNodes.forEach((node, i) => node.classList.toggle('active', i === current));
      thumbNodes[current].scrollIntoView({ block: 'nearest', inline: 'center' });
    }
    if (d.images.length > 1) {
      [['prev', '‹', -1], ['next', '›', 1]].forEach(([cls, glyph, step]) => {
        const arrow = el('button', 'hd-arrow ' + cls, glyph);
        arrow.type = 'button';
        arrow.setAttribute('aria-label', step < 0 ? '上一張' : '下一張');
        arrow.addEventListener('click', () => show(current + step));
        main.appendChild(arrow);
      });
    }
    gallery.append(main, thumbs);
    show(0);
    return gallery;
  }

  // 住客留言：在詳情視窗上面再開一個小視窗，留言在裡面自己捲動，載入更多也在裡面，不會把詳情視窗撐長
  let reviewsOverlay = null;

  function closeReviews() {
    if (reviewsOverlay) reviewsOverlay.remove();
    reviewsOverlay = null;
  }

  function openReviews(d) {
    closeReviews();
    reviewsOverlay = el('div', 'hd-rv-backdrop');
    reviewsOverlay.addEventListener('mousedown', (event) => { if (event.target === reviewsOverlay) closeReviews(); });
    const panel = el('div', 'hd-rv-panel');
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', `${d.name} 的住客留言`);
    const head = el('div', 'hd-rv-head');
    const titleBox = el('div');
    titleBox.appendChild(el('b', 'hd-rv-title', '住客留言'));
    titleBox.appendChild(el('div', 'hd-rv-sub', `${d.name}・★ ${d.rating}・${d.reviews.toLocaleString('zh-TW')} 則 Google 評論`));
    const closeBtn = el('button', 'hd-rv-close', '×');
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', '關閉留言');
    closeBtn.addEventListener('click', closeReviews);
    head.append(titleBox, closeBtn);
    const body = el('div', 'hd-rv-body');
    body.appendChild(el('p', 'hd-offer-note', '留言來自 Google 地圖的住客評論。'));
    panel.append(head, body);
    reviewsOverlay.appendChild(panel);
    document.body.appendChild(reviewsOverlay);
    closeBtn.focus();
    loadReviewPage(d.property_token, body, null);
  }

  async function loadReviewPage(token, body, pageToken) {
    const status = el('p', 'hd-offer-note', '載入住客留言中⋯⋯');
    body.appendChild(status);
    try {
      const params = new URLSearchParams({ token });
      if (pageToken) params.set('page_token', pageToken);
      const response = await fetch('/api/hotel-reviews?' + params.toString(), { headers: { Accept: 'application/json' } });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || '查詢失敗，請稍後再試。');
      status.remove();
      data.reviews.forEach((review) => body.appendChild(buildReview(review)));
      if (!data.reviews.length && !pageToken) body.appendChild(el('p', 'hd-offer-note', '目前沒有可顯示的留言。'));
      if (data.next_page_token) {
        const more = el('button', 'hd-btn hd-reviews-btn', '載入更多留言');
        more.type = 'button';
        more.addEventListener('click', () => { more.remove(); loadReviewPage(token, body, data.next_page_token); });
        body.appendChild(more);
      }
    } catch (error) {
      status.textContent = error.message;
      const retry = el('button', 'hd-btn hd-reviews-btn', '重試');
      retry.type = 'button';
      retry.addEventListener('click', () => { status.remove(); retry.remove(); loadReviewPage(token, body, pageToken); });
      body.appendChild(retry);
    }
  }

  function buildReview(review) {
    const item = el('article', 'hd-review');
    const head = el('div', 'hd-review-head');
    head.appendChild(el('b', '', review.name));
    head.appendChild(el('span', 'hd-review-stars', review.rating ? '★'.repeat(Math.round(review.rating)) + '☆'.repeat(5 - Math.round(review.rating)) : ''));
    head.appendChild(el('span', 'hd-review-date', review.date));
    item.appendChild(head);
    const text = el('p', 'hd-review-text clamped', review.text);
    item.appendChild(text);
    if (review.text.length > 140) {
      const toggle = el('button', 'hd-review-toggle', '展開');
      toggle.type = 'button';
      toggle.addEventListener('click', () => { const open = text.classList.toggle('clamped'); toggle.textContent = open ? '展開' : '收合'; });
      item.appendChild(toggle);
    } else {
      text.classList.remove('clamped');
    }
    if (review.reply) item.appendChild(el('p', 'hd-review-reply', `飯店回覆：${review.reply}`));
    return item;
  }

  function buildRatings(d) {
    const box = section('住客評價');
    if (d.rating) {
      const head = el('div', 'hd-rating');
      const score = el('button', 'hd-score', `★ ${d.rating}`);
      score.type = 'button';
      score.title = '點一下查看住客留言';
      head.appendChild(score);
      head.appendChild(el('span', '', `${d.reviews.toLocaleString('zh-TW')} 則 Google 評論${d.location_rating ? `・位置評分 ${d.location_rating}` : ''}`));
      box.appendChild(head);
      if (d.property_token) {
        const open = el('button', 'hd-btn hd-reviews-btn', '查看住客留言');
        open.type = 'button';
        const show = () => openReviews(d);
        open.addEventListener('click', show);
        score.addEventListener('click', show);
        box.appendChild(open);
      }
    }
    const maxCount = Math.max(1, ...d.rating_counts.map((r) => r.count));
    d.rating_counts.forEach((r) => {
      const row = el('div', 'hd-bar-row');
      row.appendChild(el('span', '', `${r.stars} 星`));
      const bar = el('div', 'hd-bar'); const fill = el('i');
      fill.style.width = `${Math.round((r.count / maxCount) * 100)}%`;
      bar.appendChild(fill);
      row.append(bar, el('span', '', r.count.toLocaleString('zh-TW')));
      box.appendChild(row);
    });
    if (d.topics.length) {
      box.appendChild(el('h3', '', '住客提到最多的面向')).style.marginTop = '16px';
      d.topics.forEach((t) => {
        const row = el('div', 'hd-bar-row');
        row.appendChild(el('span', '', t.name));
        const bar = el('div', 'hd-bar topic'); const fill = el('i');
        fill.style.width = `${Math.round((t.positive / t.total) * 100)}%`;
        bar.appendChild(fill);
        row.append(bar, el('span', '', `${Math.round((t.positive / t.total) * 100)}% 好評`));
        box.appendChild(row);
      });
    }
    return box;
  }

  // 各訂房網站的站內搜尋連結：不花 API 額度，一打開詳情就能用，Google 沒列出價格的網站也能自己去查
  function buildSiteLinks(d, query) {
    const box = el('div', 'hd-sites');
    if (!query) return box;
    const name = encodeURIComponent(d.original_name || d.name);
    const adults = query.totalAdults || query.adults || 2;
    const kids = query.totalChildren || 0;
    const rooms = query.rooms || 1;
    const sites = [
      ['Agoda', `https://www.agoda.com/zh-tw/search?textToSearch=${name}&checkIn=${query.checkin}&checkOut=${query.checkout}&rooms=${rooms}&adults=${adults}&children=${kids}&locale=zh-tw`],
      ['Trip.com', `https://tw.trip.com/hotels/list?searchWord=${name}&checkIn=${query.checkin}&checkOut=${query.checkout}&adult=${adults}&children=${kids}&crn=${rooms}`],
      ['Booking.com', `https://www.booking.com/searchresults.zh-tw.html?ss=${name}&checkin=${query.checkin}&checkout=${query.checkout}&group_adults=${adults}&no_rooms=${rooms}&group_children=${kids}`],
      ['Expedia', `https://www.expedia.com.tw/Hotel-Search?destination=${name}&startDate=${query.checkin}&endDate=${query.checkout}&adults=${adults}&rooms=${rooms}`],
      ['Hotels.com', `https://tw.hotels.com/Hotel-Search?destination=${name}&startDate=${query.checkin}&endDate=${query.checkout}&adults=${adults}&rooms=${rooms}`],
      ['Kayak', `https://www.kayak.com.tw/hotels/${name}/${query.checkin}/${query.checkout}/${adults}adults`],
      ['Trivago', `https://www.trivago.com.tw/zh-Hant-TW?search=${name}&checkin=${query.checkin}&checkout=${query.checkout}`],
      // 台灣的訂房網站沒有確定能帶入條件的搜尋網址，改成用 Google 搜尋「飯店名稱＋網站名稱」，點進去再選日期
      ['樂天旅遊', `https://www.google.com/search?q=${name}+${encodeURIComponent('樂天旅遊 訂房')}`],
      ['易遊網', `https://www.google.com/search?q=${name}+${encodeURIComponent('易遊網 訂房')}`],
      ['雄獅旅遊', `https://www.google.com/search?q=${name}+${encodeURIComponent('雄獅旅遊 訂房')}`],
    ];
    const details = el('details', 'hd-sites-details');
    details.appendChild(el('summary', '', '其他訂房網站'));
    details.appendChild(el('p', 'hd-offer-note', '到訂房網站搜尋這間飯店（會帶入你的日期與人數）：'));
    const row = el('div', 'hd-site-row');
    sites.forEach(([label, href]) => {
      const a = el('a', 'hd-site', label);
      a.dataset.site = label.toLowerCase();
      a.href = href; a.target = '_blank'; a.rel = 'noopener';
      row.appendChild(a);
    });
    details.appendChild(row);
    box.appendChild(details);
    return box;
  }

  function buildOffers(d, query, onOffers) {
    const box = el('div', 'hd-offers');
    if (!d.property_token || !query) return box;
    const button = el('button', 'hd-btn', '查看各訂房網站價格');
    button.type = 'button';
    const list = el('div', 'hd-offer-list');
    const siteBox = buildSiteLinks(d, query);
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = '查詢中⋯⋯（約需 10 秒）';
      const params = new URLSearchParams({
        token: d.property_token, destination: query.destination, checkin: query.checkin,
        checkout: query.checkout, guests: query.adults, child_ages: query.childAges || '',
      });
      try {
        const response = await fetch('/api/hotel-offers?' + params.toString(), { headers: { Accept: 'application/json' } });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || '查詢失敗，請稍後再試。');
        button.remove();
        renderOffers(list, data.offers, query.party, query.partyNote);
        // 已經在比價清單裡有報價(附直接訂房連結)的網站，下面的搜尋入口就不用再放了，只留清單裡沒有的
        const sources = data.offers.map((o) => o.source.toLowerCase());
        siteBox.querySelectorAll('[data-site]').forEach((a) => {
          if (sources.some((s) => s.includes(a.dataset.site.replace('.com', '')))) a.remove();
        });
        const note = siteBox.querySelector('.hd-offer-note');
        if (note) note.textContent = '以下網站在上面沒有報價，點進去自己搜尋：';
        if (!siteBox.querySelector('[data-site]')) siteBox.remove();
        if (data.offers.length) onOffers(data.offers[0]);
      } catch (error) {
        button.disabled = false;
        button.textContent = '查看各訂房網站價格';
        list.replaceChildren(el('p', 'hd-offer-note', error.message));
      }
    });
    box.append(button, list);
    box.appendChild(siteBox);
    return box;
  }

  function renderOffers(list, offers, party, partyNote) {
    list.replaceChildren();
    if (!offers.length) {
      list.appendChild(el('p', 'hd-offer-note', '目前沒有找到可訂房的網站。'));
      return;
    }
    list.appendChild(el('p', 'hd-offer-note', `共 ${offers.length} 家有這間飯店報價的網站，由低到高排列。價格${party}。各網站為即時報價，可能與列表上的最低價略有差異，實際金額以訂房網站為準。${partyNote ? partyNote + '。' : ''}房型、房間照片與剩餘房數，請在訂房網站選房時查看。`));
    const VISIBLE = 5;
    const extraBox = el('div', 'hd-offer-more');
    extraBox.hidden = true;
    offers.forEach((offer, index) => {
      const row = el('a', 'hd-offer' + (index === 0 ? ' best' : ''));
      row.href = offer.link; row.target = '_blank'; row.rel = 'noopener';
      const left = el('span', 'hd-offer-name', offer.source);
      if (index === 0) left.appendChild(el('em', 'hd-tag red', '最低價'));
      if (offer.official) left.appendChild(el('em', 'hd-tag', '官網'));
      if (offer.free_cancellation) left.appendChild(el('em', 'hd-tag green', offer.free_until ? `免費取消（至 ${offer.free_until}）` : '免費取消'));
      const priceBox = el('span', 'hd-offer-pricebox');
      priceBox.appendChild(el('b', 'hd-offer-price', money(offer.price)));
      const extra = Math.round(offer.price - offers[0].price);
      if (extra > 0) priceBox.appendChild(el('small', 'hd-offer-diff', `比最低貴 ${money(extra)}`));
      row.append(left, priceBox);
      (index < VISIBLE ? list : extraBox).appendChild(row);
    });
    if (offers.length > VISIBLE) {
      list.appendChild(extraBox);
      const toggle = el('button', 'hd-btn', `看全部 ${offers.length} 家`);
      toggle.type = 'button';
      toggle.addEventListener('click', () => {
        extraBox.hidden = !extraBox.hidden;
        toggle.textContent = extraBox.hidden ? `看全部 ${offers.length} 家` : '收合，只看前 5 家';
      });
      list.appendChild(toggle);
    }
  }

  function buildSide(d, query) {
    const side = el('aside', 'hd-side');
    const rooms = query ? Number(query.rooms) || 1 : 1;
    const price = el('div', 'hd-price');
    const priceLabel = el('small', 'hd-price-label', '搜尋列表最低價');
    const priceValue = el('span', '', money(d.price));
    price.append(priceLabel, el('br'), priceValue, el('small', '', rooms > 1 ? ' / 晚・每間' : ' / 晚'));
    side.appendChild(price);
    const totalText = (total) => (total ? `${rooms > 1 ? `${rooms} 間住宿期間約` : '住宿期間共'} ${money(total * rooms)}` : '');
    const totalNode = el('div', 'hd-total', totalText(d.total_price));
    side.appendChild(totalNode);
    const times = el('ul', 'hd-times');
    if (d.check_in_time) times.appendChild(el('li', '', `入住時間　${d.check_in_time}`));
    if (d.check_out_time) times.appendChild(el('li', '', `退房時間　${d.check_out_time}`));
    if (times.children.length) side.appendChild(times);
    if (query) side.appendChild(el('div', 'hd-total', query.party));
    // 上方價格固定跟列表一致，不隨比價結果改變，避免跟列表上看到的價格對不起來
    side.appendChild(buildOffers(d, query, () => {}));
    if (d.website_url) {
      const a = el('a', 'hd-btn primary', '前往飯店官網');
      a.href = d.website_url; a.target = '_blank'; a.rel = 'noopener';
      side.appendChild(a);
    }
    const hotelName = d.original_name || d.name;
    const hotelLocation = d.address || (query && query.destination) || '';
    const mapQuery = [hotelName, hotelLocation].filter(Boolean).join(', ') ||
      (d.latitude != null && d.longitude != null ? `${d.latitude},${d.longitude}` : '');
    if (mapQuery) {
      const a = el('a', 'hd-btn', '在地圖上查看');
      const mapUrl = new URL('https://www.google.com/maps/search/');
      mapUrl.searchParams.set('api', '1');
      mapUrl.searchParams.set('query', mapQuery);
      if (d.place_id) mapUrl.searchParams.set('query_place_id', d.place_id);
      a.href = mapUrl.toString();
      a.target = '_blank'; a.rel = 'noopener';
      side.appendChild(a);
    }
    return side;
  }

  function open(d, trigger) {
    close();
    const queryBox = trigger.closest('[data-hotel-query]');
    const query = queryBox ? { ...queryBox.dataset } : null;
    lastFocus = trigger;
    backdrop = el('div', 'hd-backdrop');
    backdrop.addEventListener('mousedown', (event) => { if (event.target === backdrop) close(); });
    const dialog = el('div', 'hd-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-label', d.name);
    const closeButton = el('button', 'hd-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', '關閉');
    closeButton.addEventListener('click', close);
    dialog.append(closeButton, buildGallery(d));

    const body = el('div', 'hd-body');
    const left = el('div');
    left.appendChild(el('h2', '', d.name));
    if (d.original_name) left.appendChild(el('div', 'hd-meta', `原名：${d.original_name}（中文為機器翻譯）`));
    left.appendChild(el('div', 'hd-meta', [d.property_type, d.star ? `${d.star} 星級` : ''].filter(Boolean).join('・')));
    if (d.description) left.appendChild(el('p', 'hd-desc', d.description));
    left.appendChild(buildRatings(d));
    if (d.amenities.length) {
      const box = section('設施與服務');
      const chips = el('div', 'hd-chips');
      d.amenities.forEach((a) => chips.appendChild(el('span', '', a)));
      box.appendChild(chips);
      left.appendChild(box);
    }
    if (d.nearby.length) {
      const box = section('附近地點');
      const list = el('ul', 'hd-nearby');
      d.nearby.forEach((place) => {
        const item = el('li');
        item.appendChild(el('span', '', place.name));
        item.appendChild(el('span', '', place.ways.map((w) => `${w.label} ${w.duration}`).join('・')));
        list.appendChild(item);
      });
      box.appendChild(list);
      left.appendChild(box);
    }
    body.append(left, buildSide(d, query));
    dialog.appendChild(body);
    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);
    document.body.style.overflow = 'hidden';
    closeButton.focus();
  }

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) return;
    if (event.target.closest('.photo-nav, a, .booking-heart, .booking-save-form, .hotel-heart')) return;  // 相片左右箭頭、連結不要觸發開視窗
    const card = event.target.closest('.hotel-row');
    if (!card || !card.dataset.detail) return;
    try { open(JSON.parse(card.dataset.detail), card); } catch (error) { /* 資料壞掉就不開 */ }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (reviewsOverlay) closeReviews(); else close();  // 先關掉留言小視窗，再關詳情
  });
})();
