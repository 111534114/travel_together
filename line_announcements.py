"""系統公告接到 LINE：會員輸入「最新消息」查看公告（回覆，免費），管理員可以把公告推播給 LINE 好友（會用掉每月額度）。"""
from mysql.connector import Error  # 匯入 MySQL 錯誤類別

import line_flex as flex  # 匯入卡片訊息工具
import line_messaging  # 匯入 LINE 官方帳號共用工具
from db import get_db_connection  # 匯入資料庫連線函式

LATEST_LIMIT = 5  # 「最新消息」最多列出幾則公告
CONTENT_LIMIT = 300  # 卡片上公告內容最多顯示幾個字，完整內容到網站看

# 和網站會員端公告頁（blueprints/member.py announcements_page）相同的條件：已發布且到了發布時間
PUBLISHED_SQL = """
    SELECT announcement_id, title, content, is_pinned, publish_at, created_at, line_pushed_at
    FROM announcements
    WHERE status = 'published' AND (publish_at IS NULL OR publish_at <= NOW())
"""


def _bubble(announcement):
    content = (announcement["content"] or "").strip()
    if len(content) > CONTENT_LIMIT:
        content = content[:CONTENT_LIMIT] + "…"
    published = announcement["publish_at"] or announcement["created_at"]
    kicker = "📌 置頂公告" if announcement["is_pinned"] else "📢 系統公告"
    body = [flex.text(content, size="sm", color=flex.INK)]
    if published:
        body.append(flex.text(published.strftime("%Y/%m/%d"), size="xs", color=flex.MUTED, margin="md"))
    return flex.bubble(flex.header(kicker, announcement["title"]), body,
                       [flex.uri_button("查看全部公告", "/member/announcements")], size="kilo")


def announcement_message(announcement):  # 單則公告卡片（推播用）
    return flex.flex_message(f"📢 公告：{announcement['title']}", _bubble(announcement))


def latest_reply():  # 「最新消息」關鍵字的回覆：最新公告卡片（置頂優先），可左右滑動
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法查詢，請稍後再試。"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(PUBLISHED_SQL + " ORDER BY is_pinned DESC, publish_at DESC, created_at DESC LIMIT %s", (LATEST_LIMIT,))
        announcements = cursor.fetchall()
    except Error as error:
        print("LINE 查詢公告失敗：", error)
        return "系統暫時無法查詢，請稍後再試。"
    finally:
        cursor.close()
        connection.close()
    if not announcements:
        return "目前沒有新的公告。"
    titles = "、".join(item["title"] for item in announcements)
    return flex.flex_message(f"最新消息：{titles}", flex.carousel([_bubble(item) for item in announcements]))


def push_status():  # 後台顯示用：推播對象人數與本月額度
    quota = line_messaging.monthly_quota()
    return {
        "configured": line_messaging.is_configured(),
        "recipients": len(line_messaging.linked_friend_user_ids()),
        "limit": quota["limit"] if quota else None,
        "used": quota["used"] if quota else None,
        "quota_known": quota is not None,
    }


def push_announcement(announcement_id):  # 推播公告給所有 LINE 好友，回傳（是否成功, 給管理員看的訊息）
    if not line_messaging.is_configured():
        return False, "LINE 官方帳號尚未設定，無法推播。"
    connection = get_db_connection()
    if connection is None:
        return False, "資料庫連線失敗。"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(PUBLISHED_SQL + " AND announcement_id = %s", (announcement_id,))
        announcement = cursor.fetchone()
        if not announcement:
            return False, "只有「已發布」的公告可以推播到 LINE。"
        recipients = line_messaging.linked_friend_user_ids()
        if not recipients:
            return False, "目前沒有綁定帳號並加入官方帳號好友的會員。"
        quota = line_messaging.monthly_quota()
        if quota and quota["limit"] is not None and quota["used"] + len(recipients) > quota["limit"]:
            remaining = max(quota["limit"] - quota["used"], 0)
            return False, f"本月推播額度不足：這次需要 {len(recipients)} 則，只剩 {remaining} 則。"
        sent = line_messaging.push_to_users(recipients, announcement_message(announcement))
        if not sent:
            return False, "推播失敗，請稍後再試。"
        cursor.execute("UPDATE announcements SET line_pushed_at = NOW() WHERE announcement_id = %s", (announcement_id,))
        connection.commit()
        return True, f"已推播到 LINE，共 {sent} 位會員（用掉 {sent} 則額度）。"
    except Error as error:
        connection.rollback()
        print("公告推播到 LINE 失敗：", error)
        return False, "推播失敗，請稍後再試。"
    finally:
        cursor.close()
        connection.close()

