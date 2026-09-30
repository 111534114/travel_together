// Google 網站翻譯：用自訂的語言選單控制隱藏的 Google 翻譯小工具
(function () {
  var SOURCE_LANGUAGE = 'zh-TW';
  var TARGET_LANGUAGES = ['en'];

  // 隱藏 Google 頂部工具列、滑鼠停留時的原文提示，並避免工具列把頁面往下推
  var style = document.createElement('style');
  style.textContent =
    'body > .skiptranslate, .goog-te-banner-frame, #goog-gt-tt, .goog-te-balloon-frame,' +
    ' .VIpgJd-ZVi9od-ORHb-OEVmcd, .VIpgJd-yAWNEb-L7lbkb { display: none !important; }' +
    ' body { top: 0 !important; }' +
    ' .goog-text-highlight, font[style] { background: none !important; box-shadow: none !important; }';
  document.head.appendChild(style);

  function savedLanguage() {
    var match = document.cookie.match(/(?:^|;\s*)googtrans=\/[^/;]*\/([^;]+)/);
    return match ? decodeURIComponent(match[1]) : SOURCE_LANGUAGE;
  }

  function currentLanguage() {
    var language = savedLanguage();
    return TARGET_LANGUAGES.indexOf(language) === -1 ? SOURCE_LANGUAGE : language;
  }

  function clearCookie() {
    writeCookie('', 'Thu, 01 Jan 1970 00:00:00 GMT');
  }

  function writeCookie(value, expires) {
    var base = 'googtrans=' + value + '; path=/' + (expires ? '; expires=' + expires : '');
    document.cookie = base;
    // Google 可能把 cookie 設在網域上，清除時兩種都要處理
    document.cookie = base + '; domain=' + location.hostname;
    document.cookie = base + '; domain=.' + location.hostname;
  }

  function changeLanguage(language) {
    if (language === SOURCE_LANGUAGE) {
      clearCookie();
      location.reload();
      return;
    }
    var combo = document.querySelector('.goog-te-combo');
    if (combo) {
      combo.value = language;
      combo.dispatchEvent(new Event('change'));
    } else {
      writeCookie('/' + SOURCE_LANGUAGE + '/' + language);
      location.reload();
    }
  }

  window.googleTranslateElementInit = function () {
    new google.translate.TranslateElement({
      pageLanguage: SOURCE_LANGUAGE,
      includedLanguages: TARGET_LANGUAGES.join(','),
      autoDisplay: false
    }, 'google_translate_element');
  };

  function init() {
    // 之前選過、但現在已不提供的語言（例如日文、韓文），在 Google 載入前清掉，避免仍被翻譯
    if (currentLanguage() !== savedLanguage()) clearCookie();

    var container = document.createElement('div');
    container.id = 'google_translate_element';
    container.hidden = true;
    document.body.appendChild(container);

    document.querySelectorAll('[data-translate-select]').forEach(function (select) {
      select.value = currentLanguage();
      select.addEventListener('change', function () { changeLanguage(select.value); });
    });

    var script = document.createElement('script');
    script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    document.body.appendChild(script);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
