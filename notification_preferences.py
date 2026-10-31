"""會員站內通知類別偏好；未設定時維持原本全部接收的行為。"""

from mysql.connector import Error


NOTIFICATION_CATEGORIES = {
    "trip": {"label": "旅程邀請與成員", "description": "旅程邀請、加入申請與成員異動。"},
    "mention": {"label": "留言提及", "description": "旅伴在留言或聊天室提及你。"},
    "friend_group": {"label": "交友揪團", "description": "揪團申請、審核與功能解鎖。"},
    "event": {"label": "官方活動公告", "description": "已報名活動的新公告。"},
    "album": {"label": "景點相簿審核", "description": "相簿照片審核結果。"},
}

_TABLE_MISSING = 1146


def send_notification(cursor, user_id, category, notification_type, title, message, target_url=None, trip_id=None):
    """依會員偏好寫入通知；system 類別不可關閉。"""
    values = (user_id, trip_id, notification_type, title, message, target_url)
    if category == "system":
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "VALUES (%s,%s,%s,%s,%s,%s)", values)
        return
    if category not in NOTIFICATION_CATEGORIES:
        raise ValueError(f"未知的通知類別：{category}")
    try:
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "SELECT %s,%s,%s,%s,%s,%s FROM DUAL WHERE NOT EXISTS ("
            "SELECT 1 FROM notification_preferences WHERE user_id=%s AND category=%s AND enabled=FALSE)",
            values + (user_id, category))
    except Error as error:
        if getattr(error, "errno", None) != _TABLE_MISSING:
            raise
        cursor.execute(
            "INSERT INTO notifications (user_id, trip_id, notification_type, title, message, target_url) "
            "VALUES (%s,%s,%s,%s,%s,%s)", values)


def get_preferences(cursor, user_id):
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
    for category in NOTIFICATION_CATEGORIES:
        cursor.execute(
            "INSERT INTO notification_preferences (user_id, category, enabled) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE enabled=VALUES(enabled), updated_at=NOW()",
            (user_id, category, category in enabled_categories))
