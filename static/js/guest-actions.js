// 只有訪客會載入：探索景點／餐廳／住宿頁面上「要登入才能用」的按鈕(收藏、加入行程、上傳照片)，
// 按下去時先把「按了什麼、在哪一頁」交給 /visitor/remember 記住，再去登入；登入後網站會自動完成並帶回這一頁。
(function () {
    var MEMBER_ACTION = /^\/member\/(attractions|restaurants|accommodations)\/\d+\/(favorite|add-to-trip|posts)$/;

    function remember(target) {
        var form = document.createElement('form');
        form.method = 'post';
        form.action = '/visitor/remember';
        [['target', target], ['back', location.pathname + location.search]].forEach(function (pair) {
            var input = document.createElement('input');
            input.type = 'hidden';
            input.name = pair[0];
            input.value = pair[1];
            form.appendChild(input);
        });
        document.body.appendChild(form);
        form.submit();
    }

    function pathOf(url) {
        try { return new URL(url, location.href).pathname; } catch (e) { return ''; }
    }

    // 「＋ 加入行程」：搶在打開選行程視窗之前攔下來(訪客還沒有行程可以選)
    document.addEventListener('click', function (e) {
        var button = e.target.closest('[data-add-to-trip]');
        if (!button) return;
        var target = pathOf(button.dataset.action || '');
        if (!MEMBER_ACTION.test(target)) return;
        e.preventDefault();
        e.stopImmediatePropagation();
        remember(target);
    }, true);

    // 收藏(♡)等表單：不要直接送出(會被擋下來然後忘記)，改成先記住
    document.addEventListener('submit', function (e) {
        var target = pathOf(e.target.getAttribute('action') || '');
        if (!MEMBER_ACTION.test(target)) return;
        e.preventDefault();
        remember(target);
    }, true);
})();
