"""站內通知的類別與會員偏好設定。

會員可以在個人資料頁關閉某些類別的通知。沒有設定紀錄的類別一律視為開啟，
所以從沒調整過的會員會收到所有通知。
"""
from mysql.connector import Error

# 會員可以自己開關的通知類別：代碼 -> 顯示名稱與說明
NOTIFICATION_CATEGORIES = {
    "trip": {"label": "旅程邀請與成員", "description": "被邀請加入旅程、有人申請加入你的旅程、申請通過或被移出旅程。"},
    "mention": {"label": "留言提及", "description": "旅伴在旅程留言或聊天室中 @ 提及你。"},
    "friend_group": {"label": "交友揪團", "description": "揪團申請與審核結果、有人申請加入你的揪團、解鎖徽章與功能。"},
    "event": {"label": "官方活動公告", "description": "你報名的官方活動發布新公告。"},
    "album": {"label": "景點相簿審核", "description": "你分享到景點相簿的照片通過或被退回。"},
}
# 帳號與管理相關通知（行程被管理員處理、問題回報結果）一律發送，不能關閉
SYSTEM_CATEGORY = "system"

_TABLE_MISSING = 1146  # MySQL：資料表不存在（還沒執行 migrate_1029_notification_preferences.sql）


def send_notification(cursor, user_id, category, notification_type, title, message, target_url=None, trip_id=None):
    """新增一則站內通知；會員關閉了這個類別就不發送。"""
    values = (user_id, trip_id, notification_type, title, message, target_url)
    if category == SYSTEM_CATEGORY:
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "VALUES (%s,%s,%s,%s,%s,%s)", values)
        return
    try:
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "SELECT %s,%s,%s,%s,%s,%s FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM notification_preferences WHERE user_id=%s AND category=%s AND enabled=FALSE)",
            values + (user_id, category))
    except Error as error:
        if getattr(error, "errno", None) != _TABLE_MISSING:
            raise
        # 偏好設定資料表還沒建立時照常發送，不影響原本的功能
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "VALUES (%s,%s,%s,%s,%s,%s)", values)


def get_preferences(cursor, user_id):
    """回傳 {類別代碼: 是否開啟}；沒有設定過的類別為開啟。"""
    preferences = {category: True for category in NOTIFICATION_CATEGORIES}
    try:
        cursor.execute("SELECT category, enabled FROM notification_preferences WHERE user_id=%s", (user_id,))
    except Error as error:
        if getattr(error, "errno", None) != _TABLE_MISSING:
            raise
        return preferences
    for row in cursor.fetchall():
        category, enabled = (row["category"], row["enabled"]) if isinstance(row, dict) else row
        if category in preferences:
            preferences[category] = bool(enabled)
    return preferences


def save_preferences(cursor, user_id, enabled_categories):
    """儲存會員勾選的類別；沒勾的類別記為關閉。"""
    for category in NOTIFICATION_CATEGORIES:
        cursor.execute(
            "INSERT INTO notification_preferences (user_id, category, enabled) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE enabled=VALUES(enabled), updated_at=NOW()",
            (user_id, category, category in enabled_categories))
