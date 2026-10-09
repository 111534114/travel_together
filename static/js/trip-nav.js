// 行程頁上方的快捷按鈕列：點了平滑捲到該功能區塊，捲動時自動標示目前所在的區塊。
// 按鈕列會黏在網站頂部導覽列下方；導覽列高度會因語系選單換行而變，所以用 JS 量實際高度。
(function () {
    var nav = document.querySelector('[data-trip-jump-nav]');
    if (!nav) return;

    var siteHeader = document.querySelector('.member-nav');
    var links = [].slice.call(nav.querySelectorAll('a[data-jump]'));
    var sections = links.map(function (link) {
        return document.getElementById(link.dataset.jump);
    });

    // 沒有對應區塊的按鈕（例如某些身分看不到的區塊）就隱藏
    links.forEach(function (link, i) { if (!sections[i]) link.hidden = true; });

    function headerHeight() {
        return siteHeader ? siteHeader.getBoundingClientRect().height : 0;
    }

    function syncOffsets() {
        var top = headerHeight();
        document.documentElement.style.setProperty('--trip-nav-top', top + 'px');
        document.documentElement.style.setProperty('--trip-scroll-offset', (top + nav.offsetHeight + 12) + 'px');
    }

    function setActive(index) {
        links.forEach(function (link, i) {
            var active = i === index;
            link.classList.toggle('active', active);
            if (active) link.setAttribute('aria-current', 'true'); else link.removeAttribute('aria-current');
        });
        // 手機上按鈕列可以左右滑，讓目前的按鈕保持在可見範圍
        var current = links[index];
        if (current && nav.scrollWidth > nav.clientWidth) {
            var left = current.offsetLeft - (nav.clientWidth - current.offsetWidth) / 2;
            nav.scrollTo({ left: left, behavior: 'smooth' });
        }
    }

    function isBesideContent(section) {
        var side = section.closest('.trip-side');
        return !!side && side.getBoundingClientRect().left >= nav.getBoundingClientRect().right;
    }

    var activeIndex = -1;
    var ticking = false;
    function updateActive() {
        ticking = false;
        var line = headerHeight() + nav.offsetHeight + 40;
        var index = 0;
        sections.forEach(function (section, i) {
            // 桌機版側欄（旅伴）跟主欄並排、一直在畫面上方，不參與捲動判斷，只在點按鈕時標示
            if (!section || isBesideContent(section)) return;
            if (section.getBoundingClientRect().top <= line) index = i;
        });
        if (index !== activeIndex) { activeIndex = index; setActive(index); }
    }

    links.forEach(function (link, i) {
        link.addEventListener('click', function (event) {
            if (!sections[i]) return;
            event.preventDefault();
            syncOffsets();
            sections[i].scrollIntoView({ behavior: 'smooth', block: 'start' });
            history.replaceState(null, '', '#' + link.dataset.jump);
            activeIndex = i; setActive(i);
        });
    });

    window.addEventListener('scroll', function () {
        if (!ticking) { ticking = true; requestAnimationFrame(updateActive); }
    }, { passive: true });
    window.addEventListener('resize', function () { syncOffsets(); updateActive(); });

    syncOffsets();
    updateActive();
})();
