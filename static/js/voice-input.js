// 語音輸入：按下 [data-voice-target="輸入框 id"] 的按鈕，用瀏覽器語音辨識把說的話填進輸入框。
// 只有支援 Web Speech API 的瀏覽器（Chrome、Edge、Safari）可用，不支援時按鈕會隱藏並顯示提示。
(function () {
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  document.querySelectorAll('[data-voice-target]').forEach(function (button) {
    var target = document.getElementById(button.dataset.voiceTarget);
    var status = button.dataset.voiceStatus ? document.getElementById(button.dataset.voiceStatus) : null;
    var idleLabel = button.innerHTML;
    if (!target) return;

    function say(message) { if (status) status.textContent = message; }

    if (!Recognition) {
      button.hidden = true;
      say('這個瀏覽器不支援語音輸入，請改用 Chrome 或 Edge，或直接打字。');
      return;
    }

    var recognition = new Recognition();
    recognition.lang = button.dataset.voiceLang || 'zh-TW';
    recognition.interimResults = true;
    recognition.continuous = false;
    var listening = false;
    var baseText = '';

    function stopUi() {
      listening = false;
      button.classList.remove('is-listening');
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = idleLabel;
    }

    recognition.onresult = function (event) {
      var text = '';
      for (var i = 0; i < event.results.length; i += 1) text += event.results[i][0].transcript;
      target.value = (baseText ? baseText + '，' : '') + text;
      target.dispatchEvent(new Event('input', { bubbles: true }));
    };
    recognition.onerror = function (event) {
      var messages = {
        'not-allowed': '沒有麥克風權限，請在瀏覽器網址列旁允許使用麥克風。',
        'service-not-allowed': '沒有麥克風權限，請在瀏覽器網址列旁允許使用麥克風。',
        'no-speech': '沒有聽到聲音，請再按一次麥克風並開始說話。',
        'audio-capture': '找不到麥克風，請確認裝置已連接。',
        'network': '語音辨識需要網路連線，請確認網路後再試。'
      };
      say(messages[event.error] || '語音輸入失敗，請再試一次或直接打字。');
      stopUi();
    };
    recognition.onend = function () {
      if (listening) say('語音已輸入，可以再修改文字後送出。');
      stopUi();
    };

    button.addEventListener('click', function () {
      if (listening) { recognition.stop(); return; }
      baseText = target.value.trim();
      try {
        recognition.start();
      } catch (error) {
        return;
      }
      listening = true;
      button.classList.add('is-listening');
      button.setAttribute('aria-pressed', 'true');
      button.innerHTML = '⏹ 停止';
      say('正在聆聽…請說出你想去哪裡、玩幾天、喜歡什麼。');
    });
  });
})();
