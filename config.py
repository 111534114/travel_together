import os  # 匯入作業系統相關功能，用來讀取環境變數

from dotenv import load_dotenv  # 匯入 dotenv，用來讀取本機的 .env 檔案(不會進 git)

load_dotenv()  # 載入 .env 檔案裡設定的環境變數(檔案不存在也不會報錯)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "travel_together",
    "use_pure": True
}

# Google Places API 金鑰，用來批次匯入 Google 地圖景點資料
# 請在專案根目錄建立 .env 檔案，寫入一行：GOOGLE_MAPS_API_KEY=你的金鑰
# .env 已經被 .gitignore 排除，不會被提交到 GitHub
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Claude API(Anthropic)金鑰，用來提供 AI 助理對話功能
# 請在 .env 檔案裡新增一行：ANTHROPIC_API_KEY=你的金鑰
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# 中央氣象署開放資料平台授權碼，用來提供訪客頁面的台灣縣市天氣預報功能
# 請到 https://opendata.cwa.gov.tw 註冊會員取得授權碼，並在 .env 檔案裡新增一行：CWA_API_KEY=你的授權碼
CWA_API_KEY = os.environ.get("CWA_API_KEY", "")

# Google 登入 OAuth 設定
# 重新導向 URI：http://127.0.0.1:5000/auth/google/callback
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# LINE Login Channel 設定（不是 Messaging API 官方帳號）
# Callback URL：http://127.0.0.1:5000/auth/line/callback
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID", "")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

# LINE 官方帳號 Messaging API 設定（和上面的 LINE Login 是不同 channel，但要在同一個 Provider 底下，
# 這樣同一位使用者在兩邊拿到的 userId 才會相同，資料庫的 line_sub 才能直接拿來推播）
# Webhook URL：https://你的公開網址/line/webhook
LINE_BOT_CHANNEL_SECRET = os.environ.get("LINE_BOT_CHANNEL_SECRET", "")
LINE_BOT_ACCESS_TOKEN = os.environ.get("LINE_BOT_ACCESS_TOKEN", "")
# 官方帳號的 Basic ID（例如 @861vahjn，不是機密），用來產生網站上的加好友連結與 QR Code
LINE_BOT_BASIC_ID = os.environ.get("LINE_BOT_BASIC_ID", "")

try:
    TRIP_REMINDER_HOUR = max(0, min(23, int(os.environ.get("TRIP_REMINDER_HOUR", "9"))))
except ValueError:
    TRIP_REMINDER_HOUR = 9
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
