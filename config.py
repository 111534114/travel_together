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
