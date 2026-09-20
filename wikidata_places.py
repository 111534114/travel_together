import requests  # 匯入 requests，用來呼叫 Wikidata 的 SPARQL 查詢服務

SPARQL_URL = "https://query.wikidata.org/sparql"  # Wikidata SPARQL 查詢服務網址(公開服務，不需要 API 金鑰)
SEARCH_API_URL = "https://www.wikidata.org/w/api.php"  # Wikidata 條目搜尋 API 網址(依相關度排序，比 SPARQL 純文字比對更準)

REQUEST_HEADERS = {  # 呼叫時帶上識別用的 User-Agent(Wikidata 建議所有自動化查詢都要帶，避免被當成惡意流量)
    "User-Agent": "TravelTogetherContentAdmin/1.0 (school project)",
}

MAX_CANDIDATE_QIDS = 5  # 名稱比對到的候選條目最多嘗試幾個(避免同名條目一直查下去)

# 中文標籤語言代碼的優先順序：優先採用繁體中文，找不到才退而求其次
LANGUAGE_PRIORITY = {"zh-hant": 0, "zh-tw": 1, "zh": 2, "zh-cn": 3}

MAX_DIVISIONS = 200  # 單一國家最多匯入的行政區數量上限，避免資料異常時匯入過多筆


class WikidataError(Exception):  # 定義自訂例外類別，代表呼叫 Wikidata 查詢服務時發生的錯誤
    pass


def _run_sparql(query):  # 定義內部函式：執行一段 SPARQL 查詢，回傳結果列表
    try:  # 嘗試發送查詢請求
        response = requests.get(
            SPARQL_URL,
            params={"query": query, "format": "json"},
            headers=REQUEST_HEADERS,
            timeout=15,  # 最多等待 15 秒，避免請求卡住拖慢管理頁面
        )
    except requests.RequestException as error:  # 如果連線失敗、逾時等
        raise WikidataError(f"無法連線到 Wikidata：{error}") from error

    if not response.ok:  # 如果 HTTP 狀態碼不是 2xx
        raise WikidataError(f"Wikidata 查詢服務回應錯誤(狀態碼 {response.status_code})")

    try:  # 嘗試解析回應內容
        return response.json()["results"]["bindings"]  # 回傳查詢結果列表
    except (ValueError, KeyError) as error:  # 如果回應格式不如預期
        raise WikidataError("Wikidata 回應格式異常") from error


def _find_candidate_qids(country_name):  # 定義內部函式：依中文名稱，查詢可能對應的 Wikidata 條目 ID(QID)候選清單(依相關度排序)
    try:  # 嘗試呼叫 Wikidata 的條目搜尋 API(依搜尋相關度排序，比純文字比對準確，例如「香港」會優先排到香港本身而不是同名專輯)
        response = requests.get(
            SEARCH_API_URL,
            params={
                "action": "wbsearchentities",  # 條目搜尋動作
                "search": country_name,  # 搜尋關鍵字(國家或地區的中文名稱)
                "language": "zh-hant",  # 用繁體中文比對
                "type": "item",  # 只搜尋一般條目
                "limit": MAX_CANDIDATE_QIDS,  # 最多回傳幾個候選
                "format": "json",  # 要求回傳 JSON 格式
            },
            headers=REQUEST_HEADERS,
            timeout=10,  # 最多等待 10 秒
        )
    except requests.RequestException as error:  # 如果連線失敗、逾時等
        raise WikidataError(f"無法連線到 Wikidata：{error}") from error

    if not response.ok:  # 如果 HTTP 狀態碼不是 2xx
        raise WikidataError(f"Wikidata 搜尋服務回應錯誤(狀態碼 {response.status_code})")

    try:  # 嘗試解析回應內容
        results = response.json().get("search", [])  # 取出搜尋結果清單
    except ValueError as error:  # 如果回應格式不如預期
        raise WikidataError("Wikidata 回應格式異常") from error

    return [item["id"] for item in results if "id" in item]  # 依相關度順序回傳候選 QID 清單


def _fetch_divisions_for_qid(qid):  # 定義內部函式：查詢單一 Wikidata 條目底下的第一級行政區中文名稱
    query = f"""
    SELECT ?division ?name (LANG(?name) AS ?lang) WHERE {{
      wd:{qid} wdt:P150 ?division .
      ?division rdfs:label ?name .
      FILTER(LANG(?name) IN ("zh-hant", "zh-tw", "zh", "zh-cn"))
    }}
    """  # 查詢這個條目底下的第一級行政區(P150：包含的行政領土實體)，並取出所有中文語系的標籤

    bindings = _run_sparql(query)  # 執行查詢

    best_by_division = {}  # 準備 {行政區網址: (語言優先度, 名稱)} 字典，每個行政區只保留最理想語言的名稱

    for row in bindings:  # 逐一處理每一筆(行政區, 名稱, 語言)結果
        division_uri = row["division"]["value"]  # 行政區的 Wikidata 網址(當作去重複的 key)
        lang = row["lang"]["value"]  # 這筆名稱使用的語言代碼
        name = row["name"]["value"]  # 這筆名稱本身
        priority = LANGUAGE_PRIORITY.get(lang, 99)  # 取得這個語言的優先度，沒列出的語言排最後

        current_best = best_by_division.get(division_uri)  # 取得目前這個行政區已經記錄的最佳名稱(可能還沒有)
        if current_best is None or priority < current_best[0]:  # 如果還沒記錄過，或這筆名稱的語言優先度更好
            best_by_division[division_uri] = (priority, name)  # 更新為這筆名稱

    return sorted({name for _, name in best_by_division.values()})  # 取出所有行政區的最終名稱，去除重複後排序


def get_admin_divisions(country_name):  # 定義函式：查詢指定國家/地區(中文名稱)底下的第一級行政區中文名稱清單
    """
    即時向 Wikidata 查詢指定國家或地區的第一級行政區(P150：包含的行政領土實體)，
    取回可用的中文名稱(優先繁體)。查不到，或名稱同名條目底下都沒有行政區資料時，
    回傳空清單，呼叫端應視為「查不到」而非直接當成錯誤。
    """
    for qid in _find_candidate_qids(country_name):  # 依序嘗試每個名稱相符的候選條目
        names = _fetch_divisions_for_qid(qid)  # 查詢這個候選條目底下有沒有行政區資料
        if names:  # 只要有查到資料，就視為找到正確的條目，不用再試下一個候選
            return names[:MAX_DIVISIONS]  # 回傳結果(最多回傳上限筆數，避免異常資料一次匯入過多筆)

    return []  # 所有候選條目都查不到行政區資料，回傳空清單
