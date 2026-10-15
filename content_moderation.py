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
        detections = _detector.detect(absolute_path)
    except Exception as error:
        print("NSFW 照片偵測失敗，改由人工審核：", error)
        return False
    return any(
        item.get("class") in EXPLICIT_CLASSES
        and item.get("score", 0) >= EXPLICIT_SCORE_THRESHOLD
        for item in detections
    )
