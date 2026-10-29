"""Optional local image moderation for member attraction posts."""

_detector = None
_detector_initialized = False


EXPLICIT_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "ANUS_EXPOSED",
}
EXPLICIT_SCORE_THRESHOLD = 0.5


def is_image_explicit(absolute_path):
    """Return True only when the optional detector confidently finds explicit content."""
    global _detector, _detector_initialized
    if not _detector_initialized:
        _detector_initialized = True
        try:
            from nudenet import NudeDetector
            _detector = NudeDetector()
        except Exception as error:
            print("NSFW 自動偵測無法使用，照片將交由人工審核：", error)
    if _detector is None:
        return False
    try:
        # 不能直接把路徑字串傳給 detect()：nudenet 內部字串路徑一律走 cv2.imread()，
        # 而 OpenCV 在 Windows 上讀不懂路徑裡的非 ASCII 字元（例如「桌面」），遇到就會
        # 讀檔失敗、整張圖都沒分析到，偵測永遠是「沒問題」，不是真的判斷過內容。改成自己
        # 用 Python 讀成 bytes 再傳進去，nudenet 就會改用 cv2.imdecode()，不受路徑編碼影響。
        with open(absolute_path, "rb") as image_file:
            image_bytes = image_file.read()
        detections = _detector.detect(image_bytes)
    except Exception as error:
        print("NSFW 照片偵測失敗，改由人工審核：", error)
        return False
    return any(
        item.get("class") in EXPLICIT_CLASSES
        and item.get("score", 0) >= EXPLICIT_SCORE_THRESHOLD
        for item in detections
    )
