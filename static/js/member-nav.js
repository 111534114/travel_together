// 會員導覽列：手機版漢堡選單的開關（電腦版按鈕是隱藏的，不受影響）
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var backdrop = document.querySelector('.nav-backdrop');
  if (!toggle) return;

  function setOpen(open) {
    document.body.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.setAttribute('aria-label', open ? '關閉選單' : '開啟選單');
  }

  toggle.addEventListener('click', function () {
    setOpen(!document.body.classList.contains('nav-open'));
  });
  if (backdrop) backdrop.addEventListener('click', function () { setOpen(false); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') setOpen(false);
  });
  // 點選選單裡的連結後自動收起（語言選單不算）
  document.querySelectorAll('.member-sidenav nav a').forEach(function (link) {
    link.addEventListener('click', function () { setOpen(false); });
  });
  // 轉成電腦版寬度時自動收起，避免殘留 nav-open 鎖住捲動
  window.matchMedia('(min-width: 851px)').addEventListener('change', function (event) {
    if (event.matches) setOpen(false);
  });
})();

