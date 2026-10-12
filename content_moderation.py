# 景點相簿照片上傳時，先用本機端、免費、不用連外部 API 的 NudeNet 模型做一次色情/裸露內容的自動初篩，
# 當作擋在人工審核前面的第一道防線；偵測不是百分之百準確，最終還是要靠內容管理員人工審核把關。
try:
    from nudenet import NudeDetector  # 匯入 NudeNet 的偵測器
    _detector = NudeDetector()  # 建立共用的偵測器實例(整個 App 共用一個，避免每次都重新載入模型)
except Exception as error:  # 如果套件沒安裝，或模型載入失敗(例如教的隊友電腦沒裝這個套件)
    _detector = None  # 偵測器設為 None，後面的函式會直接跳過自動偵測，不影響其他功能正常運作
    print("NSFW 自動偵測初始化失敗，這次先略過自動偵測，所有照片都只能靠人工審核：", error)

# 只關注會被視為明確裸露/色情的類別，臉部、腳、腋下、遮蔽中的部位不算
EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
}

EXPLICIT_SCORE_THRESHOLD = 0.5  # 信心度門檻，超過才視為偵測到不當內容


def is_image_explicit(absolute_path):
    """判斷這張照片是否疑似含有色情/裸露內容。回傳 False 代表沒偵測到，或偵測功能目前無法使用（此時完全交給人工審核）。"""
    if _detector is None:  # 偵測器沒有成功初始化(套件未安裝或模型載入失敗)
        return False
    try:
        detections = _detector.detect(absolute_path)  # 對這張照片跑一次偵測
    except Exception as error:  # 單張照片偵測失敗(例如檔案損毀)，不要讓整個上傳流程掛掉
        print("NSFW 偵測這張照片時發生錯誤，先當作沒有偵測到處理：", error)
        return False
    return any(
        d["class"] in EXPLICIT_CLASSES and d["score"] >= EXPLICIT_SCORE_THRESHOLD
        for d in detections
    )
