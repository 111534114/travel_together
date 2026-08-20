from datetime import date
from decimal import Decimal, InvalidOperation
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required
from db import get_db_connection


member_bp = Blueprint("member", __name__, url_prefix="/member")


def _connection_or_home():
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return None
    return connection


def _member_access(cursor, trip_id, user_id):
    cursor.execute("""
        SELECT t.*, tm.member_role, tm.join_status
        FROM trips t
        LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.user_id = %s
        WHERE t.trip_id = %s
    """, (user_id, trip_id))
    trip = cursor.fetchone()
    if not trip or trip["join_status"] != "accepted":
        return None
    return trip


def _can_edit(trip):
    return trip["member_role"] in ("owner", "editor")


def _parse_trip(form):
    values = {
        "trip_name": form.get("trip_name", "").strip(),
        "country": form.get("country", "").strip(),
        "city": form.get("city", "").strip(),
        "start_date": form.get("start_date", "").strip(),
        "end_date": form.get("end_date", "").strip(),
        "people_count": form.get("people_count", "1").strip(),
        "total_budget": form.get("total_budget", "0").strip(),
        "currency": form.get("currency", "TWD").strip().upper(),
        "introduction": form.get("introduction", "").strip(),
        "visibility": form.get("visibility", "private").strip(),
    }
    errors = []
    if not all(values[k] for k in ("trip_name", "country", "city", "start_date", "end_date")):
        errors.append("請填寫行程名稱、目的地與旅遊日期。")
    try:
        start, end = date.fromisoformat(values["start_date"]), date.fromisoformat(values["end_date"])
        if end < start:
            errors.append("結束日期不能早於開始日期。")
    except ValueError:
        errors.append("請輸入正確的日期。")
    try:
        values["people_count"] = int(values["people_count"])
        if values["people_count"] < 1:
            raise ValueError
    except ValueError:
        errors.append("旅遊人數至少要 1 人。")
    try:
        values["total_budget"] = Decimal(values["total_budget"])
        if values["total_budget"] < 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append("預算必須是大於或等於 0 的金額。")
    if values["visibility"] not in ("private", "public", "link_only"):
        values["visibility"] = "private"
    if len(values["currency"]) != 3:
        values["currency"] = "TWD"
    return values, errors


@member_bp.route("/")
@login_required("member")
def dashboard():
    connection = _connection_or_home()
    if connection is None:
        return render_template("member/dashboard.html", trips=[], invitations=[], stats={})
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT t.*, tm.member_role,
                   (SELECT COUNT(*) FROM itineraries i WHERE i.trip_id=t.trip_id) AS itinerary_count,
                   (SELECT COUNT(*) FROM trip_members tm2 WHERE tm2.trip_id=t.trip_id AND tm2.join_status='accepted') AS member_count
            FROM trip_members tm JOIN trips t ON t.trip_id = tm.trip_id
            WHERE tm.user_id=%s AND tm.join_status='accepted'
            ORDER BY t.start_date ASC, t.created_at DESC
        """, (user_id,))
        trips = cursor.fetchall()
        cursor.execute("""
            SELECT ti.*, t.trip_name, t.start_date, t.end_date, u.full_name AS inviter_name
            FROM trip_invitations ti JOIN trips t ON t.trip_id=ti.trip_id
            JOIN users u ON u.user_id=ti.inviter_id
            WHERE ti.invitee_id=%s AND ti.status='pending' ORDER BY ti.created_at DESC
        """, (user_id,))
        invitations = cursor.fetchall()
        stats = {"total": len(trips), "upcoming": sum(t["start_date"] >= date.today() for t in trips),
                 "planning": sum(t["status"] == "planning" for t in trips), "pending": len(invitations)}
    finally:
        cursor.close(); connection.close()
    return render_template("member/dashboard.html", trips=trips, invitations=invitations, stats=stats)


@member_bp.route("/trips/new", methods=["GET", "POST"])
@login_required("member")
def create_trip():
    if request.method == "POST":
        form, errors = _parse_trip(request.form)
        if errors:
            for error in errors: flash(error, "error")
            return render_template("member/trip_form.html", trip=form, mode="create")
        connection = _connection_or_home()
        if connection is None: return redirect(url_for("member.dashboard"))
        cursor = connection.cursor()
        try:
            cursor.execute("""INSERT INTO trips (owner_id,trip_name,country,city,start_date,end_date,people_count,total_budget,currency,introduction,visibility,status,share_token)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning',%s)""",
                           (session["user_id"], form["trip_name"], form["country"], form["city"], form["start_date"], form["end_date"], form["people_count"], form["total_budget"], form["currency"], form["introduction"] or None, form["visibility"], secrets.token_urlsafe(16)))
            trip_id = cursor.lastrowid
            cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())", (trip_id, session["user_id"]))
            connection.commit()
            flash("已建立新行程，現在可以邀請旅伴並安排每日活動。", "success")
            return redirect(url_for("member.trip_detail", trip_id=trip_id))
        except Exception:
            connection.rollback(); flash("建立行程失敗，請再試一次。", "error")
        finally:
            cursor.close(); connection.close()
    return render_template("member/trip_form.html", trip=None, mode="create")


@member_bp.route("/trips/<int:trip_id>")
@login_required("member")
def trip_detail(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看此行程的權限。", "error"); return redirect(url_for("member.dashboard"))
        cursor.execute("""SELECT i.*, u.nickname, u.full_name FROM itineraries i JOIN users u ON u.user_id=i.created_by
                          WHERE i.trip_id=%s ORDER BY i.itinerary_date,i.start_time,i.sort_order""", (trip_id,)); itinerary = cursor.fetchall()
        cursor.execute("""SELECT tm.*, u.full_name,u.nickname,u.username FROM trip_members tm JOIN users u ON u.user_id=tm.user_id
                          WHERE tm.trip_id=%s ORDER BY FIELD(tm.member_role,'owner','editor','viewer'),u.full_name""", (trip_id,)); members = cursor.fetchall()
        cursor.execute("""SELECT p.*,u.full_name AS proposer_name FROM proposals p JOIN users u ON u.user_id=p.proposer_id
                          WHERE p.trip_id=%s ORDER BY p.created_at DESC""", (trip_id,)); proposals = cursor.fetchall()
        cursor.execute("SELECT * FROM votes WHERE trip_id=%s ORDER BY deadline_at DESC", (trip_id,)); votes = cursor.fetchall()
        cursor.execute("""SELECT e.*, u.full_name AS payer_name FROM expenses e JOIN users u ON u.user_id=e.payer_id
                          WHERE e.trip_id=%s ORDER BY e.expense_date DESC,e.created_at DESC""", (trip_id,)); expenses = cursor.fetchall()
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS actual FROM expenses WHERE trip_id=%s AND expense_type='actual'", (trip_id,)); actual = cursor.fetchone()["actual"]
    finally:
        cursor.close(); connection.close()
    return render_template("member/trip_detail.html", trip=trip, itinerary=itinerary, members=members, proposals=proposals, votes=votes, expenses=expenses, actual=actual, can_edit=_can_edit(trip), is_owner=trip["member_role"] == "owner")


@member_bp.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required("member")
def edit_trip(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or trip["member_role"] != "owner":
            flash("只有行程建立者可以修改整份行程。", "error"); return redirect(url_for("member.dashboard"))
        if request.method == "POST":
            form, errors = _parse_trip(request.form)
            if errors:
                for error in errors: flash(error, "error")
                form["trip_id"] = trip_id; return render_template("member/trip_form.html", trip=form, mode="edit")
            cursor.execute("""UPDATE trips SET trip_name=%s,country=%s,city=%s,start_date=%s,end_date=%s,people_count=%s,total_budget=%s,currency=%s,introduction=%s,visibility=%s WHERE trip_id=%s""", (form["trip_name"],form["country"],form["city"],form["start_date"],form["end_date"],form["people_count"],form["total_budget"],form["currency"],form["introduction"] or None,form["visibility"],trip_id))
            connection.commit(); flash("行程資料已更新。", "success"); return redirect(url_for("member.trip_detail", trip_id=trip_id))
    finally:
        cursor.close(); connection.close()
    return render_template("member/trip_form.html", trip=trip, mode="edit")


@member_bp.route("/trips/<int:trip_id>/itinerary", methods=["POST"])
@login_required("member")
def add_itinerary(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip or not _can_edit(trip):
            flash("你沒有編輯行程項目的權限。", "error"); return redirect(url_for("member.dashboard"))
        title = request.form.get("title", "").strip(); item_type=request.form.get("item_type", "other")
        day = request.form.get("itinerary_date", ""); start=request.form.get("start_time") or None; end=request.form.get("end_time") or None
        if not title or not day: flash("請填寫項目名稱與日期。", "error")
        elif end and start and end < start: flash("結束時間不能早於開始時間。", "error")
        else:
            cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s", (trip_id,day)); order=cursor.fetchone()["next_order"]
            cursor.execute("""INSERT INTO itineraries (trip_id,created_by,itinerary_date,item_type,title,start_time,end_time,address,transport_method,estimated_cost,notes,sort_order)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id,session["user_id"],day,item_type,title,start,end,request.form.get("address","").strip() or None,request.form.get("transport_method","").strip() or None,request.form.get("estimated_cost") or 0,request.form.get("notes","").strip() or None,order))
            connection.commit(); flash("已加入每日行程。", "success")
    except Exception:
        connection.rollback(); flash("儲存行程項目失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#itinerary")


@member_bp.route("/trips/<int:trip_id>/proposals", methods=["POST"])
@login_required("member")
def add_proposal(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        title = request.form.get("title", "").strip()
        proposal_type = request.form.get("proposal_type", "other")
        if not trip: flash("你沒有查看此行程的權限。", "error")
        elif not title: flash("請填寫提案名稱。", "error")
        elif proposal_type not in ("attraction", "restaurant", "accommodation", "activity", "transport", "date", "other"): flash("提案類型無效。", "error")
        else:
            cursor.execute("""INSERT INTO proposals (trip_id,proposer_id,proposal_type,title,location,description,estimated_cost,proposed_date,content_review_status)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'not_required')""", (trip_id, session["user_id"], proposal_type, title, request.form.get("location", "").strip() or None, request.form.get("description", "").strip() or None, request.form.get("estimated_cost") or 0, request.form.get("proposed_date") or None))
            connection.commit(); flash("提案已送出，旅伴現在可以一起討論。", "success")
    except Exception:
        connection.rollback(); flash("送出提案失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/expenses", methods=["POST"])
@login_required("member")
def add_expense(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        name = request.form.get("expense_name", "").strip(); amount = request.form.get("amount", "")
        try:
            amount = Decimal(amount)
            if amount < 0: raise InvalidOperation
        except (InvalidOperation, ValueError):
            amount = None
        if not trip or not _can_edit(trip): flash("你沒有管理費用的權限。", "error")
        elif not name or amount is None or not request.form.get("expense_date"): flash("請完整填寫費用名稱、金額與日期。", "error")
        else:
            cursor.execute("""INSERT INTO expenses (trip_id,created_by,payer_id,expense_name,expense_type,scope,amount,currency,expense_date,note)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id, session["user_id"], session["user_id"], name, request.form.get("expense_type", "actual"), request.form.get("scope", "shared"), amount, trip["currency"], request.form["expense_date"], request.form.get("note", "").strip() or None))
            connection.commit(); flash("費用已記錄。", "success")
    except Exception:
        connection.rollback(); flash("儲存費用失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#budget")


@member_bp.route("/trips/<int:trip_id>/invite", methods=["POST"])
@login_required("member")
def invite_member(trip_id):
    username=request.form.get("username", "").strip(); role=request.form.get("assigned_role", "viewer")
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        trip=_member_access(cursor,trip_id,session["user_id"])
        if not trip or trip["member_role"] != "owner": flash("只有建立者可以邀請成員。", "error")
        elif role not in ("editor","viewer"): flash("請選擇有效的成員權限。", "error")
        else:
            cursor.execute("SELECT user_id,email FROM users WHERE username=%s AND role='member' AND status='active'", (username,)); invitee=cursor.fetchone()
            if not invitee: flash("找不到可邀請的一般會員帳號。", "error")
            else:
                cursor.execute("SELECT trip_member_id FROM trip_members WHERE trip_id=%s AND user_id=%s",(trip_id,invitee["user_id"]))
                if cursor.fetchone(): flash("此會員已經在行程中或已有邀請紀錄。", "error")
                else:
                    code=secrets.token_urlsafe(8)
                    cursor.execute("INSERT INTO trip_invitations (trip_id,inviter_id,invitee_id,invitee_email,invite_code,assigned_role) VALUES (%s,%s,%s,%s,%s,%s)",(trip_id,session["user_id"],invitee["user_id"],invitee["email"],code,role))
                    cursor.execute("INSERT INTO notifications (user_id,trip_id,notification_type,title,message,target_url) VALUES (%s,%s,'invitation','收到旅程邀請',%s,%s)",(invitee["user_id"],trip_id,f"你被邀請加入「{trip['trip_name']}」",url_for('member.dashboard')))
                    connection.commit(); flash("邀請已送出。", "success")
    except Exception:
        connection.rollback(); flash("送出邀請失敗。", "error")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail",trip_id=trip_id)+"#members")


@member_bp.route("/invitations/<int:invitation_id>/<action>", methods=["POST"])
@login_required("member")
def respond_invitation(invitation_id, action):
    if action not in ("accept","reject"): return redirect(url_for("member.dashboard"))
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM trip_invitations WHERE invitation_id=%s AND invitee_id=%s AND status='pending'",(invitation_id,session["user_id"])); invite=cursor.fetchone()
        if not invite: flash("找不到有效邀請。", "error")
        elif action == "reject":
            cursor.execute("UPDATE trip_invitations SET status='rejected',responded_at=NOW() WHERE invitation_id=%s",(invitation_id,)); connection.commit(); flash("已拒絕邀請。", "success")
        else:
            cursor.execute("UPDATE trip_invitations SET status='accepted',responded_at=NOW() WHERE invitation_id=%s",(invitation_id,))
            cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,%s,'accepted',NOW())",(invite["trip_id"],session["user_id"],invite["assigned_role"]))
            connection.commit(); flash("已加入旅程！", "success")
    except Exception:
        connection.rollback(); flash("處理邀請失敗。", "error")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.dashboard"))


@member_bp.route("/profile", methods=["GET", "POST"])
@login_required("member")
def profile():
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id,username,full_name,nickname,email,created_at,status FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if request.method == "POST":
            nickname=request.form.get("nickname","").strip(); email=request.form.get("email","").strip()
            if not email: flash("電子郵件不可空白。", "error")
            else:
                cursor.execute("SELECT user_id FROM users WHERE email=%s AND user_id<>%s",(email,session["user_id"])); existing=cursor.fetchone()
                if existing: flash("此電子郵件已被使用。", "error")
                else:
                    cursor.execute("UPDATE users SET nickname=%s,email=%s WHERE user_id=%s",(nickname or None,email,session["user_id"])); connection.commit(); session["nickname"]=nickname; flash("個人資料已更新。", "success"); return redirect(url_for("member.profile"))
    finally: cursor.close(); connection.close()
    return render_template("member/profile.html", user=user)


@member_bp.route("/profile/password", methods=["POST"])
@login_required("member")
def change_password():
    current=request.form.get("current_password",""); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
    if len(new)<6 or new != confirm: flash("新密碼至少 6 碼，且兩次輸入必須一致。", "error"); return redirect(url_for("member.profile"))
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.profile"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"],current): flash("目前密碼不正確。", "error")
        else: cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",(generate_password_hash(new),session["user_id"])); connection.commit(); flash("密碼已更新。", "success")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.profile"))
