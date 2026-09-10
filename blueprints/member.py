from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal, InvalidOperation
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required
from db import get_db_connection
from utils import get_cities, get_countries


member_bp = Blueprint("member", __name__, url_prefix="/member")


def _connection_or_home():
    connection = get_db_connection()
    if connection is None:
        flash("目前無法連線資料庫，請稍後再試。", "error")
        return None
    return connection


def _member_access(cursor, trip_id, user_id):
    cursor.execute("""
        SELECT t.*, co.name AS country, ci.name AS city, tm.member_role, tm.join_status
        FROM trips t
        JOIN countries co ON co.country_id = t.country_id
        JOIN cities ci ON ci.city_id = t.city_id
        LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id AND tm.user_id = %s
        WHERE t.trip_id = %s
    """, (user_id, trip_id))
    trip = cursor.fetchone()
    if not trip or trip["join_status"] != "accepted":
        return None
    return trip


def _can_edit(trip):
    return trip["member_role"] in ("owner", "editor")


def _load_votes(cursor, trip_id, user_id):
    cursor.execute("""
        SELECT v.*, u.full_name AS creator_name, u.nickname AS creator_nickname,
               (SELECT COUNT(*) FROM vote_records vr WHERE vr.vote_id=v.vote_id) AS total_votes
        FROM votes v JOIN users u ON u.user_id=v.created_by
        WHERE v.trip_id=%s ORDER BY v.created_at DESC
    """, (trip_id,))
    votes = cursor.fetchall()

    for v in votes:
        cursor.execute("""
            SELECT o.option_id, o.option_text, o.sort_order,
                   (SELECT COUNT(*) FROM vote_records vr WHERE vr.option_id=o.option_id) AS vote_count
            FROM vote_options o WHERE o.vote_id=%s ORDER BY o.sort_order
        """, (v["vote_id"],))
        v["options"] = cursor.fetchall()

        cursor.execute("SELECT option_id, approval_choice FROM vote_records WHERE vote_id=%s AND user_id=%s", (v["vote_id"], user_id))
        my_vote = cursor.fetchone()
        v["my_option_id"] = my_vote["option_id"] if my_vote else None
        v["my_approval_choice"] = my_vote["approval_choice"] if my_vote else None

        if v["vote_type"] == "approval":
            cursor.execute("""
                SELECT approval_choice, COUNT(*) AS c FROM vote_records
                WHERE vote_id=%s AND approval_choice IS NOT NULL GROUP BY approval_choice
            """, (v["vote_id"],))
            tally = {row["approval_choice"]: row["c"] for row in cursor.fetchall()}
            v["agree_count"] = tally.get("agree", 0)
            v["disagree_count"] = tally.get("disagree", 0)
            v["neutral_count"] = tally.get("neutral", 0)

    return votes


def _load_comments(cursor, trip_id):
    cursor.execute("""
        SELECT c.*, u.full_name, u.nickname
        FROM comments c JOIN users u ON u.user_id = c.user_id
        WHERE c.trip_id=%s AND c.itinerary_id IS NULL AND c.proposal_id IS NULL AND c.status='visible'
        ORDER BY c.created_at ASC
    """, (trip_id,))
    rows = cursor.fetchall()

    replies_by_parent = {}
    for r in rows:
        if r["parent_comment_id"] is not None:
            replies_by_parent.setdefault(r["parent_comment_id"], []).append(r)

    top_level = [r for r in rows if r["parent_comment_id"] is None]
    for c in top_level:
        c["replies"] = replies_by_parent.get(c["comment_id"], [])

    return top_level


def _load_expenses(cursor, trip_id):
    cursor.execute("""
        SELECT e.*, u.full_name AS payer_name, u.nickname AS payer_nickname
        FROM expenses e JOIN users u ON u.user_id = e.payer_id
        WHERE e.trip_id=%s ORDER BY e.expense_date DESC, e.created_at DESC
    """, (trip_id,))
    expenses = cursor.fetchall()

    for e in expenses:
        cursor.execute("""
            SELECT es.*, u.full_name, u.nickname
            FROM expense_splits es JOIN users u ON u.user_id = es.user_id
            WHERE es.expense_id=%s ORDER BY es.user_id
        """, (e["expense_id"],))
        e["splits"] = cursor.fetchall()

    return expenses


def _load_balance_summary(cursor, trip_id):
    cursor.execute("""
        SELECT u.user_id, u.full_name, u.nickname,
               COALESCE(SUM(CASE WHEN es.settlement_status='unpaid' THEN es.split_amount ELSE 0 END),0) AS unpaid_total
        FROM trip_members tm
        JOIN users u ON u.user_id = tm.user_id
        LEFT JOIN expense_splits es ON es.user_id = tm.user_id
            AND es.expense_id IN (SELECT expense_id FROM expenses WHERE trip_id=%s)
        WHERE tm.trip_id=%s AND tm.join_status='accepted'
        GROUP BY u.user_id, u.full_name, u.nickname
        HAVING unpaid_total > 0
        ORDER BY unpaid_total DESC
    """, (trip_id, trip_id))
    return cursor.fetchall()


def _parse_trip(form):
    values = {
        "trip_name": form.get("trip_name", "").strip(),
        "country_id": form.get("country_id", "").strip(),
        "city_id": form.get("city_id", "").strip(),
        "start_date": form.get("start_date", "").strip(),
        "end_date": form.get("end_date", "").strip(),
        "people_count": form.get("people_count", "1").strip(),
        "total_budget": form.get("total_budget", "0").strip(),
        "currency": form.get("currency", "TWD").strip().upper(),
        "introduction": form.get("introduction", "").strip(),
        "visibility": form.get("visibility", "private").strip(),
    }
    errors = []
    if not all(values[k] for k in ("trip_name", "country_id", "city_id", "start_date", "end_date")):
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
        return render_template("member/dashboard.html", trips=[], invitations=[], stats={}, announcements=[])
    cursor = connection.cursor(dictionary=True)
    try:
        user_id = session["user_id"]
        cursor.execute("""
            SELECT t.*, co.name AS country, ci.name AS city, tm.member_role,
                   (SELECT COUNT(*) FROM itineraries i WHERE i.trip_id=t.trip_id) AS itinerary_count,
                   (SELECT COUNT(*) FROM trip_members tm2 WHERE tm2.trip_id=t.trip_id AND tm2.join_status='accepted') AS member_count
            FROM trip_members tm
            JOIN trips t ON t.trip_id = tm.trip_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
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
        cursor.execute("""
            SELECT announcement_id, title, content, is_pinned, publish_at, created_at
            FROM announcements
            WHERE status = 'published'
              AND (publish_at IS NULL OR publish_at <= NOW())
            ORDER BY is_pinned DESC, publish_at DESC, created_at DESC
            LIMIT 6
        """)
        announcements = cursor.fetchall()
        stats = {"total": len(trips), "upcoming": sum(t["start_date"] >= date.today() for t in trips),
                 "planning": sum(t["status"] == "planning" for t in trips), "pending": len(invitations)}
    finally:
        cursor.close(); connection.close()
    return render_template("member/dashboard.html", trips=trips, invitations=invitations, stats=stats, announcements=announcements)


@member_bp.route("/attractions")
@login_required("member")
def browse_attractions():
    keyword = request.args.get("keyword", "").strip()
    country_id = request.args.get("country_id", "").strip()
    city_id = request.args.get("city_id", "").strip()
    favorites_only = request.args.get("favorites_only") == "1"

    connection = _connection_or_home()
    if connection is None:
        return render_template("member/attractions.html", attractions=[], countries=[], cities=[],
                                keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only)
    cursor = connection.cursor(dictionary=True)
    try:
        conditions = ["a.status = 'active'"]
        params = [session["user_id"]]

        if keyword:
            conditions.append("(a.name LIKE %s OR a.address LIKE %s)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if country_id:
            conditions.append("a.country_id = %s")
            params.append(country_id)
        if city_id:
            conditions.append("a.city_id = %s")
            params.append(city_id)
        if favorites_only:
            conditions.append("f.favorite_id IS NOT NULL")

        where_clause = " AND ".join(conditions)
        cursor.execute(f"""
            SELECT a.attraction_id, a.name, a.address, a.ticket_price, a.image_path,
                   cat.category_name, co.name AS country, ci.name AS city,
                   (f.favorite_id IS NOT NULL) AS is_favorited
            FROM attractions a
            LEFT JOIN categories cat ON cat.category_id = a.category_id
            JOIN countries co ON co.country_id = a.country_id
            JOIN cities ci ON ci.city_id = a.city_id
            LEFT JOIN favorites f ON f.attraction_id = a.attraction_id AND f.user_id = %s
            WHERE {where_clause}
            ORDER BY a.attraction_id DESC
        """, params)
        attractions = cursor.fetchall()
        countries = get_countries(cursor)
        cities = get_cities(cursor)
    finally:
        cursor.close(); connection.close()

    return render_template("member/attractions.html", attractions=attractions, countries=countries, cities=cities,
                            keyword=keyword, country_id=country_id, city_id=city_id, favorites_only=favorites_only)


@member_bp.route("/attractions/<int:attraction_id>/favorite", methods=["POST"])
@login_required("member")
def toggle_favorite(attraction_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.browse_attractions"))
    cursor = connection.cursor()
    try:
        user_id = session["user_id"]
        cursor.execute("SELECT favorite_id FROM favorites WHERE user_id=%s AND attraction_id=%s", (user_id, attraction_id))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("DELETE FROM favorites WHERE favorite_id=%s", (existing[0],))
            connection.commit()
            flash("已取消收藏。", "success")
        else:
            cursor.execute("INSERT INTO favorites (user_id, target_type, attraction_id) VALUES (%s,'attraction',%s)", (user_id, attraction_id))
            connection.commit()
            flash("已加入收藏。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()

    next_url = request.form.get("next", "")
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("member.browse_attractions")
    return redirect(next_url)


@member_bp.route("/trips/new", methods=["GET", "POST"])
@login_required("member")
def create_trip():
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        if request.method == "POST":
            form, errors = _parse_trip(request.form)
            if errors:
                for error in errors: flash(error, "error")
                return render_template("member/trip_form.html", trip=form, mode="create", countries=countries, cities=cities)
            try:
                cursor.execute("""INSERT INTO trips (owner_id,trip_name,country_id,city_id,start_date,end_date,people_count,total_budget,currency,introduction,visibility,status,share_token)
                                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planning',%s)""",
                               (session["user_id"], form["trip_name"], form["country_id"], form["city_id"], form["start_date"], form["end_date"], form["people_count"], form["total_budget"], form["currency"], form["introduction"] or None, form["visibility"], secrets.token_urlsafe(16)))
                trip_id = cursor.lastrowid
                cursor.execute("INSERT INTO trip_members (trip_id,user_id,member_role,join_status,joined_at) VALUES (%s,%s,'owner','accepted',NOW())", (trip_id, session["user_id"]))
                connection.commit()
                flash("已建立新行程，現在可以邀請旅伴並安排每日活動。", "success")
                return redirect(url_for("member.trip_detail", trip_id=trip_id))
            except Exception:
                connection.rollback(); flash("建立行程失敗，請再試一次。", "error")
        return render_template("member/trip_form.html", trip=None, mode="create", countries=countries, cities=cities)
    finally:
        cursor.close(); connection.close()


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
        votes = _load_votes(cursor, trip_id, session["user_id"])
        comments = _load_comments(cursor, trip_id)
        expenses = _load_expenses(cursor, trip_id)
        balance_summary = _load_balance_summary(cursor, trip_id)
        cursor.execute("SELECT COALESCE(SUM(amount),0) AS actual FROM expenses WHERE trip_id=%s AND expense_type='actual'", (trip_id,)); actual = cursor.fetchone()["actual"]
    finally:
        cursor.close(); connection.close()
    return render_template("member/trip_detail.html", trip=trip, itinerary=itinerary, members=members, proposals=proposals, votes=votes, comments=comments, expenses=expenses, balance_summary=balance_summary, actual=actual, can_edit=_can_edit(trip), is_owner=trip["member_role"] == "owner", now=datetime.now())


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
        countries = get_countries(cursor)
        cities = get_cities(cursor)
        if request.method == "POST":
            form, errors = _parse_trip(request.form)
            if errors:
                for error in errors: flash(error, "error")
                form["trip_id"] = trip_id; return render_template("member/trip_form.html", trip=form, mode="edit", countries=countries, cities=cities)
            cursor.execute("""UPDATE trips SET trip_name=%s,country_id=%s,city_id=%s,start_date=%s,end_date=%s,people_count=%s,total_budget=%s,currency=%s,introduction=%s,visibility=%s WHERE trip_id=%s""", (form["trip_name"],form["country_id"],form["city_id"],form["start_date"],form["end_date"],form["people_count"],form["total_budget"],form["currency"],form["introduction"] or None,form["visibility"],trip_id))
            connection.commit(); flash("行程資料已更新。", "success"); return redirect(url_for("member.trip_detail", trip_id=trip_id))
        return render_template("member/trip_form.html", trip=trip, mode="edit", countries=countries, cities=cities)
    finally:
        cursor.close(); connection.close()


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


@member_bp.route("/trips/<int:trip_id>/votes", methods=["POST"])
@login_required("member")
def add_vote(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        title = request.form.get("title", "").strip()
        vote_type = request.form.get("vote_type", "approval")
        if vote_type not in ("approval", "single_choice"): vote_type = "approval"
        deadline_at = request.form.get("deadline_at", "").strip().replace("T", " ")
        option_texts = [text.strip() for text in request.form.getlist("option_text") if text.strip()]

        if not trip: flash("你沒有查看此行程的權限。", "error")
        elif not title or not deadline_at: flash("請填寫投票標題與截止時間。", "error")
        elif vote_type == "single_choice" and len(option_texts) < 2: flash("單選投票至少需要填寫 2 個選項。", "error")
        else:
            cursor.execute("""INSERT INTO votes (trip_id,created_by,title,vote_type,deadline_at)
                              VALUES (%s,%s,%s,%s,%s)""", (trip_id, session["user_id"], title, vote_type, deadline_at))
            vote_id = cursor.lastrowid
            if vote_type == "single_choice":
                for idx, text in enumerate(option_texts, 1):
                    cursor.execute("INSERT INTO vote_options (vote_id,option_text,sort_order) VALUES (%s,%s,%s)", (vote_id, text, idx))
            connection.commit()
            flash("投票已建立。", "success")
    except Exception:
        connection.rollback(); flash("建立投票失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/votes/<int:vote_id>/cast", methods=["POST"])
@login_required("member")
def cast_vote(trip_id, vote_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        if not trip:
            flash("你沒有查看此行程的權限。", "error")
            return redirect(url_for("member.dashboard"))

        cursor.execute("SELECT * FROM votes WHERE vote_id=%s AND trip_id=%s", (vote_id, trip_id))
        vote = cursor.fetchone()

        if not vote:
            flash("找不到這個投票。", "error")
        elif vote["status"] != "open" or vote["deadline_at"] < datetime.now():
            flash("這個投票已經結束了。", "error")
        else:
            cursor.execute("SELECT vote_record_id FROM vote_records WHERE vote_id=%s AND user_id=%s", (vote_id, session["user_id"]))
            existing = cursor.fetchone()

            if existing and not vote["allow_change"]:
                flash("這個投票不允許更改，你已經投過票了。", "error")
            elif vote["vote_type"] == "approval":
                choice = request.form.get("approval_choice")
                if choice not in ("agree", "disagree", "neutral"):
                    flash("請選擇有效的投票選項。", "error")
                elif existing:
                    cursor.execute("UPDATE vote_records SET approval_choice=%s, option_id=NULL WHERE vote_record_id=%s", (choice, existing["vote_record_id"]))
                    connection.commit(); flash("已更新你的投票。", "success")
                else:
                    cursor.execute("INSERT INTO vote_records (vote_id,user_id,approval_choice) VALUES (%s,%s,%s)", (vote_id, session["user_id"], choice))
                    connection.commit(); flash("已送出你的投票。", "success")
            else:
                option_id = request.form.get("option_id", "")
                cursor.execute("SELECT option_id FROM vote_options WHERE option_id=%s AND vote_id=%s", (option_id, vote_id))
                if not cursor.fetchone():
                    flash("請選擇有效的選項。", "error")
                elif existing:
                    cursor.execute("UPDATE vote_records SET option_id=%s, approval_choice=NULL WHERE vote_record_id=%s", (option_id, existing["vote_record_id"]))
                    connection.commit(); flash("已更新你的投票。", "success")
                else:
                    cursor.execute("INSERT INTO vote_records (vote_id,user_id,option_id) VALUES (%s,%s,%s)", (vote_id, session["user_id"], option_id))
                    connection.commit(); flash("已送出你的投票。", "success")
    except Exception:
        connection.rollback(); flash("投票失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/votes/<int:vote_id>/close", methods=["POST"])
@login_required("member")
def close_vote(trip_id, vote_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM votes WHERE vote_id=%s AND trip_id=%s", (vote_id, trip_id))
        vote = cursor.fetchone()

        if not trip or not vote:
            flash("找不到這個投票。", "error")
        elif vote["created_by"] != session["user_id"] and trip["member_role"] != "owner":
            flash("只有發起人或行程建立者可以結束投票。", "error")
        else:
            cursor.execute("UPDATE votes SET status='closed' WHERE vote_id=%s", (vote_id,))
            connection.commit()
            flash("投票已結束。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#proposals")


@member_bp.route("/trips/<int:trip_id>/comments", methods=["POST"])
@login_required("member")
def add_comment(trip_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        content = request.form.get("content", "").strip()
        parent_id = request.form.get("parent_comment_id", "").strip() or None

        if not trip: flash("你沒有查看此行程的權限。", "error")
        elif not content: flash("留言內容不能是空的。", "error")
        else:
            if parent_id:
                cursor.execute("SELECT comment_id FROM comments WHERE comment_id=%s AND trip_id=%s", (parent_id, trip_id))
                if not cursor.fetchone():
                    parent_id = None
            cursor.execute("""INSERT INTO comments (trip_id,user_id,parent_comment_id,content)
                              VALUES (%s,%s,%s,%s)""", (trip_id, session["user_id"], parent_id, content))
            connection.commit()
            flash("留言已送出。", "success")
    except Exception:
        connection.rollback(); flash("留言失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#discussion")


@member_bp.route("/trips/<int:trip_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required("member")
def delete_comment(trip_id, comment_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("SELECT * FROM comments WHERE comment_id=%s AND trip_id=%s", (comment_id, trip_id))
        comment = cursor.fetchone()

        if not trip or not comment:
            flash("找不到這則留言。", "error")
        elif comment["user_id"] != session["user_id"] and trip["member_role"] != "owner":
            flash("只有留言者本人或行程建立者可以刪除留言。", "error")
        else:
            cursor.execute("UPDATE comments SET status='deleted' WHERE comment_id=%s", (comment_id,))
            connection.commit()
            flash("留言已刪除。", "success")
    except Exception:
        connection.rollback(); flash("刪除失敗，請再試一次。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#discussion")


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
        scope = request.form.get("scope", "shared")
        if scope not in ("shared", "personal"): scope = "shared"

        if not trip or not _can_edit(trip): flash("你沒有管理費用的權限。", "error")
        elif not name or amount is None or not request.form.get("expense_date"): flash("請完整填寫費用名稱、金額與日期。", "error")
        else:
            payer_id = session["user_id"]
            cursor.execute("""INSERT INTO expenses (trip_id,created_by,payer_id,expense_name,expense_type,scope,amount,currency,expense_date,note)
                              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (trip_id, payer_id, payer_id, name, request.form.get("expense_type", "actual"), scope, amount, trip["currency"], request.form["expense_date"], request.form.get("note", "").strip() or None))
            expense_id = cursor.lastrowid

            if scope == "shared":
                cursor.execute("SELECT user_id FROM trip_members WHERE trip_id=%s AND join_status='accepted'", (trip_id,))
                member_ids = sorted(row["user_id"] for row in cursor.fetchall())
                if member_ids:
                    member_count = len(member_ids)
                    base_share = (amount / member_count).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                    remainder_cents = int(((amount - base_share * member_count) * 100).to_integral_value())
                    for idx, uid in enumerate(member_ids):
                        share = base_share + (Decimal("0.01") if idx < remainder_cents else Decimal("0"))
                        status = "paid" if uid == payer_id else "unpaid"
                        cursor.execute(
                            "INSERT INTO expense_splits (expense_id,user_id,split_amount,settlement_status,paid_at) VALUES (%s,%s,%s,%s,%s)",
                            (expense_id, uid, share, status, datetime.now() if status == "paid" else None)
                        )

            connection.commit(); flash("費用已記錄，並自動平均分攤給旅程成員。" if scope == "shared" else "費用已記錄。", "success")
    except Exception:
        connection.rollback(); flash("儲存費用失敗。", "error")
    finally:
        cursor.close(); connection.close()
    return redirect(url_for("member.trip_detail", trip_id=trip_id) + "#budget")


@member_bp.route("/trips/<int:trip_id>/splits/<int:split_id>/mark-paid", methods=["POST"])
@login_required("member")
def mark_split_paid(trip_id, split_id):
    connection = _connection_or_home()
    if connection is None: return redirect(url_for("member.dashboard"))
    cursor = connection.cursor(dictionary=True)
    try:
        trip = _member_access(cursor, trip_id, session["user_id"])
        cursor.execute("""
            SELECT es.*, e.payer_id, e.trip_id
            FROM expense_splits es JOIN expenses e ON e.expense_id = es.expense_id
            WHERE es.split_id=%s
        """, (split_id,))
        split = cursor.fetchone()

        if not trip or not split or split["trip_id"] != trip_id:
            flash("找不到這筆分帳紀錄。", "error")
        elif session["user_id"] not in (split["user_id"], split["payer_id"]) and trip["member_role"] != "owner":
            flash("只有本人、代墊者或行程建立者可以標記付款狀態。", "error")
        else:
            new_status = "unpaid" if split["settlement_status"] == "paid" else "paid"
            cursor.execute(
                "UPDATE expense_splits SET settlement_status=%s, paid_at=%s WHERE split_id=%s",
                (new_status, datetime.now() if new_status == "paid" else None, split_id)
            )
            connection.commit()
            flash("已更新付款狀態。", "success")
    except Exception:
        connection.rollback(); flash("操作失敗，請再試一次。", "error")
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


@member_bp.route("/profile/password", methods=["GET", "POST"])
@login_required("member")
def change_password():
    if request.method == "GET":
        return render_template("member/change_password.html")

    current=request.form.get("current_password",""); new=request.form.get("new_password",""); confirm=request.form.get("confirm_password","")
    if len(new)<6 or new != confirm: flash("新密碼至少 6 碼，且兩次輸入必須一致。", "error"); return redirect(url_for("member.change_password"))
    connection=_connection_or_home()
    if connection is None: return redirect(url_for("member.change_password"))
    cursor=connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash FROM users WHERE user_id=%s",(session["user_id"],)); user=cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"],current): flash("目前密碼不正確。", "error"); return redirect(url_for("member.change_password"))
        else: cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",(generate_password_hash(new),session["user_id"])); connection.commit(); flash("密碼已更新。", "success")
    finally: cursor.close(); connection.close()
    return redirect(url_for("member.profile"))
