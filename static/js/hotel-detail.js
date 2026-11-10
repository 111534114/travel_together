(() => {
  // 點住宿卡片(或「查看詳情」)開啟詳情視窗。資料來自搜尋結果卡片上的 data-detail，不會再打 API。
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

  function buildRatings(d) {
    const box = section('住客評價');
    if (d.rating_10) {
      const head = el('div', 'hd-rating');
      head.appendChild(el('span', 'hd-score', String(d.rating_10)));
      head.appendChild(el('span', '', `${d.reviews.toLocaleString('zh-TW')} 則評價${d.location_rating ? `・位置評分 ${d.location_rating}` : ''}`));
      box.appendChild(head);
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

  function buildOffers(d, query) {
    const box = el('div', 'hd-offers');
    if (!d.property_token || !query) return box;
    const button = el('button', 'hd-btn', '查看各訂房網站價格');
    button.type = 'button';
    const list = el('div', 'hd-offer-list');
    button.addEventListener('click', async () => {
      button.disabled = true;
      button.textContent = '查詢中⋯⋯（約需 10 秒）';
      const params = new URLSearchParams({
        token: d.property_token, destination: query.destination, checkin: query.checkin,
        checkout: query.checkout, guests: query.guests,
      });
      try {
        const response = await fetch('/api/hotel-offers?' + params.toString(), { headers: { Accept: 'application/json' } });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || '查詢失敗，請稍後再試。');
        button.remove();
        renderOffers(list, data.offers, query.guests);
      } catch (error) {
        button.disabled = false;
        button.textContent = '查看各訂房網站價格';
        list.replaceChildren(el('p', 'hd-offer-note', error.message));
      }
    });
    box.append(button, list);
    return box;
  }

  function renderOffers(list, offers, guests) {
    list.replaceChildren();
    if (!offers.length) {
      list.appendChild(el('p', 'hd-offer-note', '目前沒有找到可訂房的網站。'));
      return;
    }
    list.appendChild(el('p', 'hd-offer-note', `價格以 ${guests} 位住客計算。房型、房間照片與剩餘房數，請在訂房網站選房時查看。`));
    offers.forEach((offer, index) => {
      const row = el('a', 'hd-offer' + (index === 0 ? ' best' : ''));
      row.href = offer.link; row.target = '_blank'; row.rel = 'noopener';
      const left = el('span', 'hd-offer-name', offer.source);
      if (offer.official) left.appendChild(el('em', 'hd-tag', '官網'));
      if (offer.free_cancellation) left.appendChild(el('em', 'hd-tag green', offer.free_until ? `免費取消（至 ${offer.free_until}）` : '免費取消'));
      row.append(left, el('b', 'hd-offer-price', `NT$ ${Math.round(offer.price).toLocaleString('zh-TW')}`));
      list.appendChild(row);
    });
  }

  function buildSide(d, query) {
    const side = el('aside', 'hd-side');
    const price = el('div', 'hd-price', `NT$ ${Math.round(d.price).toLocaleString('zh-TW')}`);
    price.appendChild(el('small', '', ' / 晚'));
    side.appendChild(price);
    if (d.total_price) side.appendChild(el('div', 'hd-total', `住宿期間共 NT$ ${Math.round(d.total_price).toLocaleString('zh-TW')}`));
    const times = el('ul', 'hd-times');
    if (d.check_in_time) times.appendChild(el('li', '', `入住時間　${d.check_in_time}`));
    if (d.check_out_time) times.appendChild(el('li', '', `退房時間　${d.check_out_time}`));
    if (times.children.length) side.appendChild(times);
    if (query) side.appendChild(el('div', 'hd-total', `以 ${query.guests} 位住客計價`));
    side.appendChild(buildOffers(d, query));
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
    if (event.target.closest('.photo-nav, a')) return;  // 相片左右箭頭、連結不要觸發開視窗
    const card = event.target.closest('.hotel-row');
    if (!card || !card.dataset.detail) return;
    try { open(JSON.parse(card.dataset.detail), card); } catch (error) { /* 資料壞掉就不開 */ }
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
})();
