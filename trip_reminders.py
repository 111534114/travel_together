"""Send LINE reminders on the day before a trip begins."""

import threading
import time
from datetime import date, datetime, timedelta

from mysql.connector import Error

import line_commands
import line_messaging
from config import TRIP_REMINDER_HOUR
from db import get_db_connection


NOTIFY_TYPE = "trip_day_before"
CHECK_INTERVAL_SECONDS = 600


def build_card(cursor, trip):  # 出發前一天提醒卡片：和「下一趟旅程」同一種卡片，含天氣、第一天安排與「查看行程」按鈕（LIFF）
    return line_commands.trip_card(cursor, trip, "明天就要出發囉！", trip["start_date"], "第一天安排",
                                   note="記得檢查證件、行李和天氣，祝旅途愉快！")


def send_trip_reminders(today=None):
    today = today or date.today()
    tomorrow = today + timedelta(days=1)
    connection = get_db_connection()
    if connection is None:
        return 0
    cursor = connection.cursor(dictionary=True)
    sent_total = 0
    try:
        cursor.execute(
            """
            SELECT t.trip_id,t.trip_name,t.start_date,t.end_date,t.cover_image_path,
                   co.name AS country,ci.name AS city,tm.user_id
            FROM trips t JOIN countries co ON co.country_id=t.country_id
            JOIN cities ci ON ci.city_id=t.city_id
            JOIN trip_members tm ON tm.trip_id=t.trip_id AND tm.join_status='accepted'
            JOIN users u ON u.user_id=tm.user_id
            WHERE t.start_date=%s AND t.deleted_at IS NULL AND t.status<>'cancelled'
              AND u.status='active' AND u.line_sub IS NOT NULL AND u.line_friend=1
              AND NOT EXISTS (SELECT 1 FROM line_notification_logs l
                WHERE l.trip_id=t.trip_id AND l.user_id=tm.user_id
                  AND l.notify_type=%s AND l.notify_date=%s)
            ORDER BY t.trip_id
            """,
            (tomorrow, NOTIFY_TYPE, today),
        )
        trips = {}
        for row in cursor.fetchall():
            trip = trips.setdefault(row["trip_id"], {**row, "user_ids": []})
            trip["user_ids"].append(row["user_id"])
        for trip in trips.values():
            if not line_messaging.push_to_users(trip["user_ids"], build_card(cursor, trip)):
                continue
            cursor.executemany(
                "INSERT IGNORE INTO line_notification_logs (trip_id,user_id,notify_type,notify_date) VALUES (%s,%s,%s,%s)",
                [(trip["trip_id"], user_id, NOTIFY_TYPE, today) for user_id in trip["user_ids"]],
            )
            sent_total += len(trip["user_ids"])
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
                send_trip_reminders()
            except Exception as error:
                print("行程提醒排程錯誤：", error)
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler():
    if line_messaging.is_configured():
        threading.Thread(target=_scheduler_loop, name="trip-reminders", daemon=True).start()


if __name__ == "__main__":
    print(f"已發送 {send_trip_reminders()} 則行程出發提醒")
