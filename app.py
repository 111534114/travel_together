from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from config import DB_CONFIG

app = Flask(__name__)

# Session 加密金鑰，之後可以改成更複雜的字串
app.secret_key = "travel-together-secret-key"


def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)

        if connection.is_connected():
            return connection

    except Exception as error:
        print("資料庫連線失敗：", error)

    return None



def redirect_by_role(role):
    if role == "member":
        return redirect(url_for("member_home"))

    if role == "content_admin":
        return redirect(url_for("content_admin_home"))

    if role == "system_admin":
        return redirect(url_for("system_admin_home"))

    session.clear()
    flash("帳號角色設定錯誤。", "error")
    return redirect(url_for("login"))


@app.route("/")
def index():
    if "user_id" in session:
        return redirect_by_role(session.get("role"))

    return redirect(url_for("visitor"))


@app.route("/visitor")
def visitor():
    return render_template("visitor.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect_by_role(session.get("role"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("請輸入帳號和密碼。", "error")
            return render_template("login.html")

        connection = get_db_connection()

        if connection is None:
            flash("資料庫連線失敗，請稍後再試。", "error")
            return render_template("login.html")

        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT user_id, username, password_hash,
                       full_name, nickname, role, status
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,)
            )

            user = cursor.fetchone()

        finally:
            cursor.close()
            connection.close()

        if user is None:
            flash("帳號或密碼錯誤。", "error")
            return render_template("login.html")

        if user["status"] != "active":
            flash("此帳號目前已停用，無法登入。", "error")
            return render_template("login.html")

        if not check_password_hash(user["password_hash"], password):
            flash("帳號或密碼錯誤。", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["user_id"]
        session["username"] = user["username"]
        session["full_name"] = user["full_name"]
        session["nickname"] = user["nickname"]
        session["role"] = user["role"]

        return redirect_by_role(user["role"])

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        full_name = request.form.get("full_name", "").strip()
        nickname = request.form.get("nickname", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not full_name or not email or not password:
            flash("請填寫所有必填欄位。", "error")
            return render_template("register.html")

        if len(username) < 4:
            flash("帳號至少需要4個字元。", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("密碼至少需要6個字元。", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("兩次輸入的密碼不一致。", "error")
            return render_template("register.html")

        connection = get_db_connection()

        if connection is None:
            flash("資料庫連線失敗，請稍後再試。", "error")
            return render_template("register.html")

        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT user_id
                FROM users
                WHERE username = %s OR email = %s
                LIMIT 1
                """,
                (username, email)
            )

            existing_user = cursor.fetchone()

            if existing_user:
                flash("帳號或電子郵件已被使用。", "error")
                return render_template("register.html")

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, full_name, nickname,
                 email, role, status)
                VALUES (%s, %s, %s, %s, %s, 'member', 'active')
                """,
                (
                    username,
                    password_hash,
                    full_name,
                    nickname or None,
                    email
                )
            )

            connection.commit()

        except Exception as error:
            connection.rollback()
            print("註冊失敗：", error)
            flash("註冊失敗，請稍後再試。", "error")
            return render_template("register.html")

        finally:
            cursor.close()
            connection.close()

        flash("註冊成功，請使用新帳號登入。", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/member")
def member_home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "member":
        return redirect_by_role(session.get("role"))

    return render_template("member_home.html")


@app.route("/content-admin")
def content_admin_home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "content_admin":
        return redirect_by_role(session.get("role"))

    return render_template("content_admin_home.html")


@app.route("/system-admin")
def system_admin_home():

    # 檢查是否登入
    if "user_id" not in session:
        return redirect(url_for("login"))

    # 只有 system_admin 可以進入
    if session.get("role") != "system_admin":
        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "system_admin_home.html",
            member_count=0,
            trip_count=0,
            public_trip_count=0,
            report_count=0
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # 一般會員數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
        """)

        member_count = cursor.fetchone()["total"]

        # 所有行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
        """)

        trip_count = cursor.fetchone()["total"]

        # 公開行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
            WHERE visibility = 'public'
        """)

        public_trip_count = cursor.fetchone()["total"]

        # 待處理檢舉
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM reports
            WHERE status = 'pending'
        """)

        report_count = cursor.fetchone()["total"]

        # 最近加入會員
        cursor.execute("""
            SELECT user_id,
                   username,
                   full_name,
                   email,
                   status,
                   created_at
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT 5
        """)

        recent_users = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "system_admin_home.html",
        member_count=member_count,
        trip_count=trip_count,
        public_trip_count=public_trip_count,
        report_count=report_count,
        recent_users=recent_users
    )
@app.route("/system-admin/users")
def admin_users():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("login"))

    keyword = request.args.get("keyword", "").strip()

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("admin_users.html", users=[])

    cursor = connection.cursor(dictionary=True)

    try:

        if keyword:

            search = "%" + keyword + "%"

            cursor.execute("""
                SELECT user_id,
                       username,
                       full_name,
                       nickname,
                       email,
                       role,
                       status,
                       created_at
                FROM users
                WHERE role = 'member'
                AND status != 'deleted'
                AND (
                    username LIKE %s
                    OR full_name LIKE %s
                    OR email LIKE %s
                )
                ORDER BY user_id DESC
            """, (search, search, search))

        else:

            cursor.execute("""
                SELECT user_id,
                       username,
                       full_name,
                       nickname,
                       email,
                       role,
                       status,
                       created_at
                FROM users
                WHERE role = 'member'
                AND status != 'deleted'
                ORDER BY user_id DESC
            """)

        users = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin_users.html",
        users=users,
        keyword=keyword
    )

@app.route("/system-admin/users/<int:user_id>/disable", methods=["POST"])
def disable_user():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_users"))

    cursor = connection.cursor()

    try:

        cursor.execute("""
            UPDATE users
            SET status = 'disabled'
            WHERE user_id = %s
            AND role = 'member'
        """, (user_id,))

        connection.commit()

        flash("會員已停用", "success")

    except Exception as error:

        connection.rollback()

        print("停用會員失敗：", error)

        flash("停用會員失敗", "error")

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin_users"))
@app.route("/system-admin/users/<int:user_id>/enable", methods=["POST"])
def enable_user():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "system_admin":
        return redirect(url_for("login"))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_users"))

    cursor = connection.cursor()

    try:

        cursor.execute("""
            UPDATE users
            SET status = 'active'
            WHERE user_id = %s
            AND role = 'member'
        """, (user_id,))

        connection.commit()

        flash("會員已恢復", "success")

    except Exception as error:

        connection.rollback()

        print("恢復會員失敗：", error)

        flash("恢復會員失敗", "error")

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin_users"))
@app.route("/logout")
def logout():
    session.clear()
    flash("你已成功登出。", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)