# LINE 官方帳號公開行程測試設定

此分支已加入 LINE Webhook 與公開行程 Flex Message。沒有設定 LINE 金鑰時，原本網站仍可正常啟動。

## 一 環境變數

在專案根目錄的 `.env` 加入以下設定，不要將正式金鑰提交到 GitHub。

```text
LINE_CHANNEL_SECRET=你的 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN=你的 Channel Access Token
APP_BASE_URL=https://你的公開 HTTPS 網址
LINE_DEFAULT_COVER_URL=https://可公開讀取的預設封面網址
```

`APP_BASE_URL` 必須是 LINE 能從網際網路存取的 HTTPS 網址，不能使用 `127.0.0.1`。

## 二 本機預覽

啟動 Flask 後開啟：

```text
http://127.0.0.1:5000/line/status
http://127.0.0.1:5000/line/public-trips/preview
http://127.0.0.1:5000/line/public-trips/preview?keyword=台北
```

預覽端點會顯示準備傳給 LINE 的 Flex Message JSON，不會真的傳送訊息。

## 三 LINE Developers 設定

1. 建立 LINE Official Account 與 Messaging API Channel。
2. 將 Webhook URL 設為 `https://你的網址/line/webhook`。
3. 啟用 Webhook。
4. 將 Channel Secret 與 Channel Access Token 填入 `.env`。
5. Rich Menu 的公開行程按鈕使用 postback action，資料填入 `action=public_trips`。
6. 加入官方帳號後傳送「公開行程」，或傳送「搜尋 台北」測試。

## 四 目前功能

- 驗證 `X-Line-Signature`，阻擋偽造 Webhook。
- 加入好友時傳送歡迎訊息與快速按鈕。
- 收到「公開行程」後查詢最新公開行程。
- 收到「搜尋 關鍵字」後依行程名稱、國家、城市、分類及建立者暱稱搜尋。
- 使用 Flex Message Carousel 顯示最多十筆行程。
- 卡片提供查看詳情與分享行程按鈕。
- 排除私人、已取消及停用會員的行程。

## 五 正式測試前注意事項

- LINE 卡片圖片與按鈕網址應使用 HTTPS。
- `.env` 已被 Git 排除，不要把 Token 或 Secret 寫進程式碼。
- 本階段尚未建立會員 LINE 帳號綁定及問題回報通知，這些適合在公開行程卡片確認正常後再加入。
