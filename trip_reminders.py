"""出發前提醒(每天固定時間之後執行，每 10 分鐘檢查一次，靠 line_notification_logs 避免重複發送)：

- 出發前 1 天：LINE「明天就要出發囉！」卡片，下面附上出發前檢查結果(沒問題就寫「✅ 沒問題」)；
  每位旅伴也會收到網站通知。
- 出發前 3 天：先做出發前檢查，有問題才發 LINE 卡片和網站通知，沒問題就不打擾。

旅伴可以在「通知設定」關掉「出發前檢查」(precheck)：關掉的人網站通知不會收到，
出發前 1 天的 LINE 仍會收到原本的出發提醒，只是不附檢查結果；出發前 3 天的 LINE 也不會收到。
"""

import threading
import time
from datetime import date, datetime, timedelta

from mysql.connector import Error

import line_commands
import line_messaging
import pre_trip_check
from config import TRIP_REMINDER_HOUR
from db import get_db_connection
from notification_preferences import send_notification


NOTIFY_TYPE = "trip_day_before"  # 出發前 1 天 LINE(維持原本的名稱，舊紀錄才對得上)
PRECHECK_LINE_3D = "precheck_3d"  # 出發前 3 天 LINE
PRECHECK_SITE_TYPES = {1: "precheck_1d_site", 3: "precheck_3d_site"}  # 網站通知
CHECK_INTERVAL_SECONDS = 600


def build_card(cursor, trip, checks=None):  # 出發前一天提醒卡片：和「下一趟旅程」同一種卡片，含天氣、第一天安排與「查看行程」按鈕（LIFF）
    return line_commands.trip_card(cursor, trip, "明天就要出發囉！", trip["start_date"], "第一天安排",
                                   note="記得檢查證件、行李和天氣，祝旅途愉快！", checks=checks)


def build_precheck_card(cursor, trip, checks, days_before):  # 出發前 3 天：有問題才發
    return line_commands.trip_card(cursor, trip, f"{days_before} 天後出發，先檢查一下！", trip["start_date"], "第一天安排",
                                   checks=checks)


def _trips_starting(cursor, start_date):
    cursor.execute(
        """
        SELECT t.trip_id, t.trip_name, t.start_date, t.end_date, t.cover_image_path, t.total_budget, t.currency,
               co.name AS country, ci.name AS city
        FROM trips t JOIN countries co ON co.country_id=t.country_id
        JOIN cities ci ON ci.city_id=t.city_id
        WHERE t.start_date=%s AND t.deleted_at IS NULL AND t.status<>'cancelled'
        ORDER BY t.trip_id
        """,
        (start_date,),
    )
    return cursor.fetchall()


def _members(cursor, trip_id, notify_type, today):
    """還沒收過這種通知的旅伴：[{user_id, line_ok(可以收 LINE), precheck_off(關掉出發前檢查)}]。"""
    cursor.execute(
        """
        SELECT u.user_id,
               (u.line_sub IS NOT NULL AND u.line_friend=1) AS line_ok
        FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
        WHERE tm.trip_id=%s AND tm.join_status='accepted' AND u.status='active'
          AND NOT EXISTS (SELECT 1 FROM line_notification_logs l
            WHERE l.trip_id=tm.trip_id AND l.user_id=tm.user_id AND l.notify_type=%s AND l.notify_date=%s)
        """,
        (trip_id, notify_type, today),
    )
    rows = cursor.fetchall()
    off = _precheck_off(cursor, [row["user_id"] for row in rows])
    for row in rows:
        row["line_ok"] = bool(row["line_ok"])
        row["precheck_off"] = row["user_id"] in off
    return rows


def _precheck_off(cursor, user_ids):
    if not user_ids:
        return set()
    placeholders = ",".join(["%s"] * len(user_ids))
    try:
        cursor.execute(
            f"SELECT user_id FROM notification_preferences WHERE category='precheck' AND enabled=FALSE AND user_id IN ({placeholders})",
            list(user_ids),
        )
        return {row["user_id"] for row in cursor.fetchall()}
    except Error:  # 還沒有通知設定資料表：大家都當作開啟
        return set()


def _log(cursor, trip_id, user_ids, notify_type, today):
    if user_ids:
        cursor.executemany(
            "INSERT IGNORE INTO line_notification_logs (trip_id,user_id,notify_type,notify_date) VALUES (%s,%s,%s,%s)",
            [(trip_id, user_id, notify_type, today) for user_id in user_ids],
        )


def _send_site_notifications(cursor, trip, issues, days_before, today):
    """網站通知：每位旅伴一則(關掉「出發前檢查」的人 send_notification 會自動略過)。"""
    notify_type = PRECHECK_SITE_TYPES[days_before]
    members = _members(cursor, trip["trip_id"], notify_type, today)
    if not members:
        return 0
    when = "明天就要出發了" if days_before == 1 else f"再 {days_before} 天就要出發了"
    if issues:
        title = f"「{trip['trip_name']}」出發前檢查：有 {len(issues)} 件事要注意"
        message = f"{when}！\n" + "\n".join(pre_trip_check.summary_lines(issues, limit=4))
    else:
        title = f"「{trip['trip_name']}」出發前檢查：沒問題！"
        message = f"{when}！天氣、營業時間、住宿和預算都檢查過了，祝旅途愉快。"
    for member in members:
        send_notification(cursor, member["user_id"], "precheck", "departure", title[:150], message,
                          f"/member/trips/{trip['trip_id']}#itinerary", trip["trip_id"])
    _log(cursor, trip["trip_id"], [m["user_id"] for m in members], notify_type, today)
    return len(members)


def send_trip_reminders(today=None):
    """出發前 1 天：LINE 卡片(附出發前檢查) + 網站通知。回傳送出的 LINE 人數。"""
    today = today or date.today()
    connection = get_db_connection()
    if connection is None:
        return 0
    cursor = connection.cursor(dictionary=True)
    sent_total = 0
    try:
        for trip in _trips_starting(cursor, today + timedelta(days=1)):
            issues = pre_trip_check.run_checks(cursor, trip, today)
            checks = pre_trip_check.summary_lines(issues)
            members = _members(cursor, trip["trip_id"], NOTIFY_TYPE, today)
            with_checks = [m["user_id"] for m in members if m["line_ok"] and not m["precheck_off"]]
            plain = [m["user_id"] for m in members if m["line_ok"] and m["precheck_off"]]
            for user_ids, card in ((with_checks, build_card(cursor, trip, checks)), (plain, build_card(cursor, trip))):
                if user_ids and line_messaging.push_to_users(user_ids, card):
                    _log(cursor, trip["trip_id"], user_ids, NOTIFY_TYPE, today)
                    sent_total += len(user_ids)
            _send_site_notifications(cursor, trip, issues, 1, today)
            connection.commit()
    except Error as error:
        connection.rollback()
        print("發送行程提醒失敗：", error)
    finally:
        cursor.close()
        connection.close()
    return sent_total


def send_precheck_reminders(today=None, days_before=3):
    """出發前 3 天：有問題才發 LINE 卡片 + 網站通知。回傳送出的 LINE 人數。"""
    today = today or date.today()
    connection = get_db_connection()
    if connection is None:
        return 0
    cursor = connection.cursor(dictionary=True)
    sent_total = 0
    try:
        for trip in _trips_starting(cursor, today + timedelta(days=days_before)):
            issues = pre_trip_check.run_checks(cursor, trip, today)
            if not issues:  # 沒問題就不打擾
                continue
            members = _members(cursor, trip["trip_id"], PRECHECK_LINE_3D, today)
            user_ids = [m["user_id"] for m in members if m["line_ok"] and not m["precheck_off"]]
            card = build_precheck_card(cursor, trip, pre_trip_check.summary_lines(issues), days_before)
            if user_ids and line_messaging.push_to_users(user_ids, card):
                _log(cursor, trip["trip_id"], user_ids, PRECHECK_LINE_3D, today)
                sent_total += len(user_ids)
            _send_site_notifications(cursor, trip, issues, days_before, today)
            connection.commit()
    except Error as error:
        connection.rollback()
        print("發送出發前檢查失敗：", error)
    finally:
        cursor.close()
        connection.close()
    return sent_total


def _scheduler_loop():
    while True:
        if datetime.now().hour >= TRIP_REMINDER_HOUR:
            for job in (send_trip_reminders, send_precheck_reminders):
                try:
                    job()
                except Exception as error:
                    print("行程提醒排程錯誤：", error)
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_scheduler():
    # 沒設定 LINE 也要啟動：網站通知(出發前檢查)不需要 LINE；LINE 推播在沒設定時會自動略過
    threading.Thread(target=_scheduler_loop, name="trip-reminders", daemon=True).start()


if __name__ == "__main__":
    print(f"已發送 {send_trip_reminders()} 則行程出發提醒、{send_precheck_reminders()} 則出發前 3 天檢查")
