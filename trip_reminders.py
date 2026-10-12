"""行程出發前一天的 LINE 提醒。

- 網站啟動後會在背景每 10 分鐘檢查一次：每天 TRIP_REMINDER_HOUR（config.py）點以後，
  把「明天出發」的行程推播給已綁定 LINE 且已加官方帳號好友的成員。
- 已發送的紀錄寫在 line_notification_logs，同一人同一行程不會重複收到；
  提醒時間過後才加入行程的成員，下一輪檢查時也會補發。
- 手動執行一次（測試或 Demo 用，不受提醒時間限制）：python trip_reminders.py
"""
import threading  # 匯入 threading，用來在背景執行排程
import time  # 匯入 time，用來讓排程間隔等待
from datetime import date, datetime, timedelta  # 匯入日期工具

from mysql.connector import Error  # 匯入 MySQL 錯誤類別

import line_messaging  # 匯入 LINE 官方帳號共用工具
from config import PUBLIC_BASE_URL, TRIP_REMINDER_HOUR  # 匯入提醒時間與網站公開網址設定
from db import get_db_connection  # 匯入資料庫連線函式
from utils import format_hm  # 匯入 TIME 欄位格式化函式

NOTIFY_TYPE = "trip_day_before"
CHECK_INTERVAL_SECONDS = 600  # 背景排程檢查間隔：10 分鐘
FIRST_DAY_ITEMS = 5  # 訊息中最多列出第一天的幾個行程項目


def _format_period(start, end):
    if start == end:
        return start.strftime("%Y/%m/%d")
    return f"{start.strftime('%Y/%m/%d')} – {end.strftime('%m/%d')}"


def build_message(trip, first_day_items):  # 組出提醒訊息文字
    lines = [
        "🧳 明天就要出發囉！",
        "",
        f"行程：{trip['trip_name']}",
        f"日期：{_format_period(trip['start_date'], trip['end_date'])}",
        f"地點：{trip['country']} {trip['city']}",
    ]
    if first_day_items:
        lines += ["", "第一天安排："]
        for item in first_day_items[:FIRST_DAY_ITEMS]:
            time_text = format_hm(item["start_time"]) if item["start_time"] and not item["is_all_day"] else "全天"
            lines.append(f"・{time_text} {item['title']}")
        if len(first_day_items) > FIRST_DAY_ITEMS:
            lines.append(f"…還有 {len(first_day_items) - FIRST_DAY_ITEMS} 項")
    lines += ["", "記得檢查證件、行李和天氣，祝旅途愉快！"]
    if PUBLIC_BASE_URL:
        lines.append(f"查看行程：{PUBLIC_BASE_URL}/member/trips/{trip['trip_id']}")
    return "\n".join(lines)


def send_trip_reminders(today=None):  # 發送明天出發的行程提醒，回傳實際收到訊息的人數
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    connection = get_db_connection()
    if connection is None:
        return 0
    cursor = connection.cursor(dictionary=True)
    sent_total = 0
    try:
        # 找出明天出發、還沒收到提醒、而且收得到 LINE 訊息的成員
        cursor.execute(
            """
            SELECT t.trip_id, t.trip_name, t.start_date, t.end_date,
                   co.name AS country, ci.name AS city, tm.user_id
            FROM trips t
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.join_status = 'accepted'
            JOIN users u ON u.user_id = tm.user_id
            WHERE t.start_date = %s AND t.deleted_at IS NULL AND t.status <> 'cancelled'
              AND u.status = 'active' AND u.line_sub IS NOT NULL AND u.line_friend = 1
              AND NOT EXISTS (
                  SELECT 1 FROM line_notification_logs l
                  WHERE l.trip_id = t.trip_id AND l.user_id = tm.user_id
                    AND l.notify_type = %s AND l.notify_date = %s
              )
            ORDER BY t.trip_id
            """,
            (tomorrow, NOTIFY_TYPE, today),
        )
        trips = {}
        for row in cursor.fetchall():
            trip = trips.setdefault(row["trip_id"], {**row, "user_ids": []})
            trip["user_ids"].append(row["user_id"])

        for trip in trips.values():
            cursor.execute(
                """
                SELECT title, start_time, is_all_day FROM itineraries
                WHERE trip_id = %s AND itinerary_date = %s
                ORDER BY is_all_day DESC, start_time IS NULL, start_time, sort_order
                """,
                (trip["trip_id"], trip["start_date"]),
            )
            message = build_message(trip, cursor.fetchall())
            sent = line_messaging.push_to_users(trip["user_ids"], message)
            if sent == 0:  # 發送失敗就不寫紀錄，下一輪會再試
                continue
            sent_total += sent
            cursor.executemany(
                """
                INSERT IGNORE INTO line_notification_logs (trip_id, user_id, notify_type, notify_date)
                VALUES (%s, %s, %s, %s)
                """,
                [(trip["trip_id"], user_id, NOTIFY_TYPE, today) for user_id in trip["user_ids"]],
            )
            connection.commit()
    except Error as error:
        connection.rollback()
        print("發送行程提醒失敗：", error)
    finally:
        cursor.close()
        connection.close()
    return sent_total


def _scheduler_loop():
    while True:
        if datetime.now().hour >= TRIP_REMINDER_HOUR:
            try:
                sent = send_trip_reminders()
                if sent:
                    print(f"已發送 {sent} 則行程出發提醒")
            except Exception as error:  # 排程不能因為單次錯誤就停止
                print("行程提醒排程錯誤：", error)
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler():  # 在背景啟動提醒排程（daemon 執行緒，網站關閉時一起結束）
    if not line_messaging.is_configured():
        print("LINE 官方帳號尚未設定，不啟動行程提醒排程")
        return
    threading.Thread(target=_scheduler_loop, name="trip-reminders", daemon=True).start()


if __name__ == "__main__":
    print(f"已發送 {send_trip_reminders()} 則行程出發提醒")
