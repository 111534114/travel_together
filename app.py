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

    except Error as error:
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

    return redirect(url_for("login"))


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

        except Error as error:
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
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "system_admin":
        return redirect_by_role(session.get("role"))

    return render_template("system_admin_home.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("你已成功登出。", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)