"""行程助理的網址(行程頁「每日行程」旁邊的聊天框用 fetch 呼叫，全部回傳 JSON)。

- GET  /member/trips/<id>/assistant          對話紀錄(只有自己的)、今天還能問幾次、能不能套用
- POST /member/trips/<id>/assistant/ask      問一次(所有旅伴都能問；每人每天 trip_assistant.DAILY_LIMIT 次)
- POST /member/trips/<id>/assistant/apply    套用改動清單(只有建立者、共同編輯者)
- POST /member/trips/<id>/assistant/dismiss  不要這份建議
- POST /member/trips/<id>/assistant/undo     復原助理的上一次改動(只有建立者、共同編輯者)
- POST /member/trips/<id>/assistant/clear    清除自己的對話紀錄
"""

from flask import Blueprint, jsonify, request, session

import trip_assistant
from ai_client import AIUnavailable, ai_ready
from auth import login_required
from blueprints.member import _can_edit, _member_access
from db import get_db_connection

trip_assistant_bp = Blueprint("trip_assistant", __name__, url_prefix="/member/trips/<int:trip_id>/assistant")


def _open(trip_id):
    """開連線並確認是這趟行程的旅伴。回傳 (connection, cursor, trip, 錯誤回應)。"""
    connection = get_db_connection()
    if connection is None:
        return None, None, None, (jsonify(error="目前無法連線資料庫，請稍後再試"), 503)
    cursor = connection.cursor(dictionary=True)
    trip = _member_access(cursor, trip_id, session["user_id"])
    if not trip:
        cursor.close(); connection.close()
        return None, None, None, (jsonify(error="你沒有這趟行程的權限"), 403)
    if not trip_assistant.table_available(cursor):
        cursor.close(); connection.close()
        return None, None, None, (jsonify(error=trip_assistant.TABLE_MISSING_MESSAGE), 503)
    return connection, cursor, trip, None


def _message_id():
    try:
        return int((request.get_json(silent=True) or {}).get("message_id"))
    except (TypeError, ValueError):
        return None


@trip_assistant_bp.route("", methods=["GET"])
@login_required("member")
def history(trip_id):
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        user_id = session["user_id"]
        return jsonify(
            messages=trip_assistant.load_history(cursor, trip_id, user_id),
            remaining=max(0, trip_assistant.DAILY_LIMIT - trip_assistant.used_today(cursor, user_id)),
            limit=trip_assistant.DAILY_LIMIT, can_apply=_can_edit(trip), ai_ready=ai_ready(),
            undo_id=trip_assistant.latest_undoable_id(cursor, trip_id),
        )
    finally:
        cursor.close(); connection.close()


@trip_assistant_bp.route("/ask", methods=["POST"])
@login_required("member")
def ask(trip_id):
    question = str((request.get_json(silent=True) or {}).get("message") or "").strip()
    if not question:
        return jsonify(error="請輸入你想問的問題"), 400
    if len(question) > 500:
        return jsonify(error="問題太長了，請縮短到 500 字以內"), 400
    if not ai_ready():
        return jsonify(error="伺服器還沒設定 AI 服務，暫時不能使用行程助理"), 503
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        user_id = session["user_id"]
        used = trip_assistant.used_today(cursor, user_id)
        if used >= trip_assistant.DAILY_LIMIT:
            return jsonify(error=f"今天已經問了 {trip_assistant.DAILY_LIMIT} 次，明天再來問吧！"), 429
        try:
            result = trip_assistant.ask(cursor, trip, user_id, question)
        except AIUnavailable as ai_error:
            return jsonify(error=str(ai_error)), 503
        message_id = trip_assistant.save_exchange(cursor, trip_id, user_id, question, result)
        connection.commit()
        return jsonify(
            message={"id": message_id, "role": "assistant", "content": result["reply"],
                     "changes": [{"label": c["label"], "reason": c.get("reason")} for c in result["changes"]],
                     "rejected": result["rejected"], "status": "pending" if result["changes"] else "none"},
            remaining=max(0, trip_assistant.DAILY_LIMIT - used - 1),
        )
    except Exception as unexpected:
        connection.rollback()
        print("行程助理回答失敗：", unexpected)
        return jsonify(error="助理暫時出了點問題，請再試一次"), 500
    finally:
        cursor.close(); connection.close()


@trip_assistant_bp.route("/apply", methods=["POST"])
@login_required("member")
def apply(trip_id):
    message_id = _message_id()
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        if not _can_edit(trip):
            return jsonify(error="只有建立者和共同編輯者可以套用改動"), 403
        try:
            count = trip_assistant.apply_plan(cursor, trip, session["user_id"], message_id)
        except trip_assistant.ConflictError as conflict:
            connection.commit()  # 「已過期」的狀態也要存下來
            return jsonify(error=str(conflict)), 409
        connection.commit()
        return jsonify(ok=True, message=f"已套用 {count} 項改動，也通知了其他旅伴")
    except Exception as unexpected:
        connection.rollback()
        print("套用行程助理改動失敗：", unexpected)
        return jsonify(error="套用失敗，行程沒有任何變動，請再試一次"), 500
    finally:
        cursor.close(); connection.close()


@trip_assistant_bp.route("/dismiss", methods=["POST"])
@login_required("member")
def dismiss(trip_id):
    message_id = _message_id()
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        cursor.execute(
            """UPDATE trip_ai_messages SET plan_status='dismissed'
               WHERE message_id=%s AND trip_id=%s AND user_id=%s AND plan_status='pending'""",
            (message_id, trip_id, session["user_id"]),
        )
        connection.commit()
        return jsonify(ok=True)
    finally:
        cursor.close(); connection.close()


@trip_assistant_bp.route("/undo", methods=["POST"])
@login_required("member")
def undo(trip_id):
    message_id = _message_id()
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        if not _can_edit(trip):
            return jsonify(error="只有建立者和共同編輯者可以復原"), 403
        try:
            trip_assistant.undo_plan(cursor, trip, session["user_id"], message_id)
        except trip_assistant.ConflictError as conflict:
            connection.rollback()
            return jsonify(error=str(conflict)), 409
        connection.commit()
        return jsonify(ok=True, message="已經復原，行程改回套用前的樣子，也通知了其他旅伴")
    except Exception as unexpected:
        connection.rollback()
        print("復原行程助理改動失敗：", unexpected)
        return jsonify(error="復原失敗，行程沒有任何變動，請再試一次"), 500
    finally:
        cursor.close(); connection.close()


@trip_assistant_bp.route("/clear", methods=["POST"])
@login_required("member")
def clear(trip_id):
    connection, cursor, trip, error = _open(trip_id)
    if error:
        return error
    try:
        # 已套用(還能復原)的那則要留著，不然就沒辦法復原了
        cursor.execute(
            "DELETE FROM trip_ai_messages WHERE trip_id=%s AND user_id=%s AND plan_status <> 'applied'",
            (trip_id, session["user_id"]),
        )
        connection.commit()
        return jsonify(ok=True)
    finally:
        cursor.close(); connection.close()
