import requests  # 匯入 requests，用來呼叫 Claude API

from config import ANTHROPIC_API_KEY  # 匯入 Claude API 金鑰

MESSAGES_URL = "https://api.anthropic.com/v1/messages"  # Claude 對話 API 網址
API_VERSION = "2023-06-01"  # Anthropic API 版本號(官方文件要求的固定表頭值)
MODEL = "claude-haiku-4-5-20251001"  # 使用的模型：這個助理只做簡單的新增/查詢判斷，用較便宜的 Haiku 模型就足夠

SYSTEM_PROMPT = (  # 定義給 Claude 的系統提示，限定它只處理國家與城市相關的請求
    "你是「走吧揪團」旅遊網站後台的 AI 助理，專門幫內容管理員維護「國家」與「城市」資料。"
    "使用者會用中文跟你聊天，可能會要求你新增國家、新增城市，或是詢問目前有哪些國家/城市。"
    "請只處理國家與城市相關的請求；如果使用者問的是其他資料(例如景點、餐廳、住宿、分類、提案)，"
    "禮貌地告訴他這個助理目前只處理國家與城市，其他資料請到對應的管理頁面操作，不要嘗試用工具處理。"
    "新增城市時，如果使用者沒有講清楚屬於哪個國家、你也無法從上下文合理判斷，"
    "要先反問使用者這個城市屬於哪個國家，不要憑空亂猜國家。"
    "每次工具執行完畢後，用簡短、口語、友善的繁體中文告訴使用者結果，不要條列一堆技術細節。"
)

TOOLS = [  # 定義 Claude 可以呼叫的工具(函式)清單
    {
        "name": "add_country",  # 工具名稱：新增國家
        "description": "新增一個國家到資料庫，如果國家已經存在就不會重複新增",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "國家名稱，使用繁體中文，例如「日本」"}
            },
            "required": ["name"],
        },
    },
    {
        "name": "add_city",  # 工具名稱：新增城市
        "description": "新增一個城市到資料庫，並歸屬到指定的國家；如果該國家還不存在會自動一併新增，如果城市已存在就不會重複新增",
        "input_schema": {
            "type": "object",
            "properties": {
                "country_name": {"type": "string", "description": "這個城市所屬的國家名稱"},
                "city_name": {"type": "string", "description": "城市名稱"},
            },
            "required": ["country_name", "city_name"],
        },
    },
    {
        "name": "list_countries_and_cities",  # 工具名稱：查詢目前所有國家與城市
        "description": "查詢目前資料庫裡已經有的所有國家，以及每個國家底下的城市清單",
        "input_schema": {"type": "object", "properties": {}},
    },
]


class ClaudeApiError(Exception):  # 定義自訂例外類別，代表呼叫 Claude API 時發生的錯誤
    pass


def is_configured():  # 定義函式：檢查目前是否已經設定 API 金鑰
    return bool(ANTHROPIC_API_KEY)  # 金鑰非空字串才算已設定


def call_claude(messages):  # 定義函式：把目前的對話內容送給 Claude，回傳這一輪的回應
    response = requests.post(  # 發送 POST 請求到 Claude 對話 API
        MESSAGES_URL,
        headers={  # 帶上金鑰、API 版本、內容類型
            "x-api-key": ANTHROPIC_API_KEY,  # API 金鑰
            "anthropic-version": API_VERSION,  # API 版本號
            "content-type": "application/json",  # 告知伺服器請求內容是 JSON
        },
        json={  # 請求內容
            "model": MODEL,  # 要使用的模型
            "max_tokens": 1024,  # 這一輪回應最多產生的字數上限(以 token 計)
            "system": SYSTEM_PROMPT,  # 系統提示，設定助理的角色與限制
            "tools": TOOLS,  # 可以呼叫的工具清單
            "messages": messages,  # 目前為止的對話內容
        },
        timeout=30  # 最多等待 30 秒
    )

    if not response.ok:  # 如果 HTTP 狀態碼不是 2xx(代表金鑰錯誤、額度用完、格式錯誤等)
        message = response.text  # 預設錯誤訊息為原始回應內容
        try:  # 嘗試把錯誤內容解析成 Anthropic 慣用的錯誤格式
            message = response.json().get("error", {}).get("message", message)  # 取得更精簡的錯誤說明
        except ValueError:  # 如果回應內容不是合法的 JSON
            pass  # 就沿用原始的錯誤內容
        raise ClaudeApiError(message)  # 拋出例外，帶上錯誤說明

    return response.json()  # 回傳解析後的回應內容
