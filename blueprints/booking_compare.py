"""機票＋住宿比價的網址(行程頁「住宿與預算」分頁用 fetch 呼叫，回傳 JSON)。

- POST /member/trips/<id>/compare                       開始比價(所有旅伴都能用，每人每天 booking_compare.DAILY_LIMIT 次)
- GET  /member/trips/<id>/compare/<compare_id>          查進度(比價在背景執行，頁面每幾秒問一次)
- POST /member/trips/<id>/compare/<compare_id>/add-hotel  把某個方案的飯店加進行程(只有建立者、共同編輯者)
"""

import json
from datetime import date, timedelta

from flask import Blueprint, jsonify, request, session

import booking_compare
from ai_client import ai_ready
from auth import login_required
from blueprints.member import _can_edit, _member_access
from db import get_db_connection

booking_compare_bp = Blueprint("booking_compare", __name__, url_prefix="/member/trips/<int:trip_id>/compare")


def _open(trip_id):
    connection = get_db_connection()
    if connection is None:
        return None, None, None, (jsonify(error="目前無法連線資料庫，請稍後再試"), 503)
    cursor = connection.cursor(dictionary=True)
    trip = _member_access(cursor, trip_id, session["user_id"])
    if not trip:
        cursor.close(); connection.close()
        return None, None, None, (jsonify(error="你沒有這趟行程的權限"), 403)
    if not booking_compare.table_available(cursor):
        cursor.close(); connection.close()
        return None, None, None, (jsonify(error=booking_compare.TABLE_MISSING_MESSAGE), 503)
    return connection, cursor, trip, None


def _people(cursor, trip):
    if trip.get("people_count"):
        return max(1, min(int(trip["people_count"]), 9))
    cursor.execute("SELECT COUNT(*) AS n FROM trip_members WHERE trip_id=%s AND join_status='accepted'", (trip["trip_id"],))
    return max(1, min(int((cursor.fetchone() or {}).get("n") or 1), 9))


@booking_compare_bp.route("", methods=["POST"])
@login_required("member")
def start(trip_id):
    data = request.get_json(silent=True) or {}
    origin = str(data.get("origin") or "").strip()
    request_text = str(data.get("request") or "").strip()
    scope_values = data.get("scope") if isinstance(data.get("scope"), list) else []
    if scope_values and not any(value in booking_compare.SCOPE_LABELS for value in scope_values):
        return jsonify(error="請選擇要比什麼（住宿、機票、高鐵或台鐵）"), 400
    if len(origin) > 60 or len(request_text) > 300:
        return jsonify(error="出發地或要求太長了，請縮短一點"), 400
    if not ai_ready():
        return jsonify(error="伺服器還沒設定 AI 服務，暫時不能比價"), 503
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        scope = booking_compare.clean_scope(scope_values, trip)
        if booking_compare.needs_origin(scope) and not origin:
            return jsonify(error="要比機票或火車時，請填寫出發地，例如「台北」"), 400
        if not booking_compare.needs_origin(scope):
            origin = ""  # 只比住宿：不需要出發地
        if trip["start_date"] < date.today():
            return jsonify(error="這趟旅程已經出發了，查不到過去日期的票價"), 400
        used = booking_compare.used_today(cursor, session["user_id"])
        if used >= booking_compare.DAILY_LIMIT:
            return jsonify(error=f"今天已經比價 {booking_compare.DAILY_LIMIT} 次了，明天再來吧！可以先看看旅伴查過的結果。"), 429
        people = _people(cursor, trip)
        compare_id = booking_compare.start(cursor, trip, session["user_id"], origin, request_text, people)
        connection.commit()
    finally:
        cursor.close(); connection.close()
    booking_compare.launch(compare_id, trip, origin, request_text, people, scope)
    return jsonify(compare_id=compare_id, remaining=max(0, booking_compare.DAILY_LIMIT - used - 1))


@booking_compare_bp.route("/<int:compare_id>", methods=["GET"])
@login_required("member")
def status(trip_id, compare_id):
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        rows = [row for row in booking_compare.latest(cursor, trip_id, limit=20) if row["compare_id"] == compare_id]
        if not rows:
            return jsonify(error="找不到這次比價"), 404
        return jsonify(status=rows[0]["status"], error=rows[0].get("error_message"))
    finally:
        cursor.close(); connection.close()


@booking_compare_bp.route("/<int:compare_id>/add-hotel", methods=["POST"])
@login_required("member")
def add_hotel(trip_id, compare_id):
    data = request.get_json(silent=True) or {}
    kind = str(data.get("kind") or "")
    wanted = data.get("dates") if isinstance(data.get("dates"), list) else None  # 使用者勾選要住的晚上；沒給就用「還沒有住宿的每一晚」
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        if not _can_edit(trip):
            return jsonify(error="只有建立者和共同編輯者可以把飯店加進行程"), 403
        cursor.execute("SELECT result_json FROM trip_booking_compares WHERE compare_id=%s AND trip_id=%s AND status='done'",
                       (compare_id, trip_id))
        row = cursor.fetchone()
        result = json.loads(row["result_json"]) if row and row.get("result_json") else {}
        option = next((o for o in result.get("options", []) if o.get("kind") == kind), None)
        hotel = next((line for line in (option or {}).get("lines", []) if line.get("type") == "hotel"), None)
        if not hotel:
            return jsonify(error="這個方案沒有飯店"), 404
        start_day, end_day = trip["start_date"], trip["end_date"]
        cursor.execute(
            "SELECT DISTINCT itinerary_date FROM itineraries WHERE trip_id=%s AND item_type='accommodation'", (trip_id,))
        booked = {r["itinerary_date"] for r in cursor.fetchall()}
        nights = [start_day + timedelta(days=n) for n in range((end_day - start_day).days)]
        if wanted is not None:  # 只加使用者勾的晚上，而且一定要在旅程期間內
            chosen = {str(value)[:10] for value in wanted}
            nights = [night for night in nights if night.isoformat() in chosen]
            if not nights:
                return jsonify(error="請至少勾選一個晚上"), 400
        else:
            nights = [night for night in nights if night not in booked]  # 那一晚已經有住宿就不重複加
        nights = nights[:booking_compare.MAX_HOTEL_NIGHTS_TO_ADD]
        added = 0
        for night in nights:
            cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s",
                           (trip_id, night))
            order = cursor.fetchone()["next_order"]
            cursor.execute(
                """INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,is_all_day,
                       address,transport_method,transport_minutes,estimated_cost,notes,sort_order)
                   VALUES (%s,%s,%s,'accommodation',%s,NULL,NULL,0,%s,NULL,0,%s,%s,%s)""",
                (trip_id, session["user_id"], night, (hotel.get("title") or "住宿")[:150], (hotel.get("address") or None),
                 hotel.get("per_night") or 0, f"由機票＋住宿比價加入（{result.get('searched_at', '')} 查詢的價格，實際以訂房網站為準）", order),
            )
            added += 1
        connection.commit()
        if not added:
            return jsonify(ok=True, message="每一晚都已經有住宿了，沒有重複加入")
        if wanted is not None:
            return jsonify(ok=True, message=f"已把「{hotel.get('title')}」加進你勾選的 {added} 晚")
        return jsonify(ok=True, message=f"已把「{hotel.get('title')}」加進 {added} 晚的行程")
    except Exception as unexpected:
        connection.rollback()
        print("比價飯店加入行程失敗：", unexpected)
        return jsonify(error="加入失敗，請再試一次"), 500
    finally:
        cursor.close(); connection.close()
