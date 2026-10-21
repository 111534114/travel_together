"""在 LINE 裡直接投票：投票卡片上的按鈕是 postback 動作，點了由 webhook 交給 handle_postback 記錄投票。

投票規則和網站（blueprints/member.py 的 cast_vote）一致：必須是行程成員、投票開放中且未截止、
不允許更改的投票投過就不能再投。LINE 上「不想」不填理由，需要寫理由可以到網站修改。
"""
from datetime import datetime  # 匯入日期時間工具

from mysql.connector import Error  # 匯入 MySQL 錯誤類別

import line_flex as flex  # 匯入卡片訊息工具
from db import get_db_connection  # 匯入資料庫連線函式

APPROVAL_CHOICES = (("agree", "想"), ("disagree", "不想"), ("neutral", "沒意見"))  # 和網站的按鈕文字一致
MAX_OPTION_BUTTONS = 6  # 單選投票最多直接列出幾個選項按鈕，再多就請使用者到網站投
POSTBACK_PREFIX = "vote"  # postback data 格式：vote:{vote_id}:{choice}


def _postback(vote_id, choice, label, display):
    return {
        "type": "button", "style": "secondary", "height": "sm",
        "action": {"type": "postback", "label": label[:20], "data": f"{POSTBACK_PREFIX}:{vote_id}:{choice}",
                   "displayText": display[:300]},
    }


def vote_bubble(cursor, vote):  # 一個投票一張卡片；vote 需要 vote_id, trip_id, trip_name, title, vote_type, deadline_at
    if vote["vote_type"] == "approval":
        buttons = [_postback(vote["vote_id"], key, label, f"投「{label}」：{vote['title']}") for key, label in APPROVAL_CHOICES]
        hint = "選擇你的意見"
    else:
        cursor.execute("SELECT option_id, option_text FROM vote_options WHERE vote_id=%s ORDER BY sort_order, option_id",
                       (vote["vote_id"],))
        options = cursor.fetchall()
        buttons = [_postback(vote["vote_id"], option["option_id"], option["option_text"],
                             f"投「{option['option_text']}」：{vote['title']}") for option in options[:MAX_OPTION_BUTTONS]]
        hint = "選擇一個選項" if len(options) <= MAX_OPTION_BUTTONS else f"共 {len(options)} 個選項，其他選項請到網站投票"
    buttons.append(flex.uri_button("到網站查看", f"/member/trips/{vote['trip_id']}#proposals", style="link"))
    body = [
        flex.info_row("行程", vote["trip_name"]),
        flex.info_row("截止", vote["deadline_at"].strftime("%m/%d %H:%M")),
        flex.text(hint, size="xs", color=flex.MUTED, margin="md"),
    ]
    return flex.bubble(flex.header("🗳️ 投票", vote["title"], color=flex.PRIMARY_DEEP), body, buttons, size="kilo")


def parse_postback(data):  # 解析 postback data，不是投票的資料回傳 None
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != POSTBACK_PREFIX or not parts[1].isdigit():
        return None
    return int(parts[1]), parts[2]


def _results_text(cursor, vote):  # 目前的投票結果摘要
    if vote["vote_type"] == "approval":
        cursor.execute("SELECT approval_choice, COUNT(*) AS n FROM vote_records WHERE vote_id=%s GROUP BY approval_choice",
                       (vote["vote_id"],))
        counts = {row["approval_choice"]: row["n"] for row in cursor.fetchall()}
        return "、".join(f"{label} {counts.get(key, 0)}" for key, label in APPROVAL_CHOICES)
    cursor.execute(
        """
        SELECT o.option_text, COUNT(r.vote_record_id) AS n FROM vote_options o
        LEFT JOIN vote_records r ON r.option_id = o.option_id
        WHERE o.vote_id=%s GROUP BY o.option_id, o.option_text, o.sort_order ORDER BY o.sort_order, o.option_id
        """,
        (vote["vote_id"],),
    )
    return "、".join(f"{row['option_text']} {row['n']}" for row in cursor.fetchall())


def cast_vote(user_id, vote_id, choice):  # 記錄投票，回傳要回覆給使用者的文字
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法投票，請稍後再試。"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT v.*, t.trip_name FROM votes v
            JOIN trips t ON t.trip_id = v.trip_id AND t.deleted_at IS NULL
            JOIN trip_members tm ON tm.trip_id = v.trip_id AND tm.user_id = %s AND tm.join_status = 'accepted'
            WHERE v.vote_id = %s
            """,
            (user_id, vote_id),
        )
        vote = cursor.fetchone()
        if not vote:
            return "找不到這個投票，或你已經不是這個行程的成員。"
        if vote["status"] != "open" or vote["deadline_at"] < datetime.now():
            return f"「{vote['title']}」已經結束投票了。"
        cursor.execute("SELECT vote_record_id FROM vote_records WHERE vote_id=%s AND user_id=%s", (vote_id, user_id))
        existing = cursor.fetchone()
        if existing and not vote["allow_change"]:
            return f"「{vote['title']}」不允許更改，你已經投過票了。"

        if vote["vote_type"] == "approval":
            labels = dict(APPROVAL_CHOICES)
            if choice not in labels:
                return "這個選項無效，請到網站投票。"
            label = labels[choice]
            if existing:
                cursor.execute("UPDATE vote_records SET approval_choice=%s, option_id=NULL, reason=NULL WHERE vote_record_id=%s",
                               (choice, existing["vote_record_id"]))
            else:
                cursor.execute("INSERT INTO vote_records (vote_id,user_id,approval_choice) VALUES (%s,%s,%s)",
                               (vote_id, user_id, choice))
        else:
            cursor.execute("SELECT option_text FROM vote_options WHERE option_id=%s AND vote_id=%s",
                           (choice if choice.isdigit() else 0, vote_id))
            option = cursor.fetchone()
            if not option:
                return "這個選項無效，請到網站投票。"
            label = option["option_text"]
            if existing:
                cursor.execute("UPDATE vote_records SET option_id=%s, approval_choice=NULL WHERE vote_record_id=%s",
                               (int(choice), existing["vote_record_id"]))
            else:
                cursor.execute("INSERT INTO vote_records (vote_id,user_id,option_id) VALUES (%s,%s,%s)",
                               (vote_id, user_id, int(choice)))
        connection.commit()
        action = "已更新" if existing else "已送出"
        return f"✅ {action}你的投票：「{label}」\n{vote['trip_name']}｜{vote['title']}\n\n目前結果：{_results_text(cursor, vote)}"
    except Error as error:
        connection.rollback()
        print("LINE 投票失敗：", error)
        return "投票失敗，請稍後再試。"
    finally:
        cursor.close()
        connection.close()


def handle_postback(line_sub, data):  # webhook 收到 postback 時呼叫；不是投票的 postback 回傳 None
    parsed = parse_postback(data)
    if parsed is None:
        return None
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法投票，請稍後再試。"
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT user_id FROM users WHERE line_sub=%s AND status='active' LIMIT 1", (line_sub,))
        row = cursor.fetchone()
    finally:
        cursor.close()
        connection.close()
    if not row:
        return "你的 LINE 還沒有和網站帳號連動，請先到網站綁定 LINE 再投票。"
    return cast_vote(row[0], *parsed)
