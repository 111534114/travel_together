import re
import secrets

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from activity_log import log_action
from auth import login_required
from content_admin_permissions import ACTION_LABELS, CONTENT_ADMIN_ACTIONS, CONTENT_ADMIN_MODULES
from db import get_db_connection


content_admin_accounts_bp = Blueprint("content_admin_accounts", __name__)


@content_admin_accounts_bp.app_context_processor
def account_form_context():
    return {"admin_account_csrf": _csrf_token()}


def _csrf_token():
    return session.setdefault("admin_account_csrf", secrets.token_urlsafe(32))


def _check_csrf():
    if not secrets.compare_digest(request.form.get("csrf", ""), _csrf_token()):
        abort(400)


def _valid_password(password):
    return bool(re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)\S{9,}", password))


def _profile_values(creating=False):
    values = {
        "username": request.form.get("username", "").strip(),
        "full_name": request.form.get("full_name", "").strip(),
        "nickname": request.form.get("nickname", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip(),
    }
    if creating and not re.fullmatch(r"[A-Za-z0-9]{1,9}", values["username"]):
        return values, "帳號需為 1 至 9 碼英文或數字。"
    if not re.fullmatch(r"[A-Za-z一-龥][A-Za-z一-龥\s]*", values["full_name"]):
        return values, "姓名只能包含中英文字與空白。"
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]) or len(values["email"]) > 150:
        return values, "請輸入有效的電子郵件。"
    if len(values["nickname"]) > 100 or len(values["phone"]) > 30:
        return values, "暱稱或電話超過長度限制。"
    return values, None


def _selected_modules():
    selected = set(request.form.getlist("modules"))
    if not selected <= CONTENT_ADMIN_MODULES.keys():
        abort(400)
    return selected


def _save_denials(cursor, user_id, selected):
    cursor.execute("DELETE FROM content_admin_denials WHERE user_id = %s", (user_id,))
    denied = CONTENT_ADMIN_MODULES.keys() - selected
    if denied:
        cursor.executemany(
            "INSERT INTO content_admin_denials (user_id, module) VALUES (%s, %s)",
            [(user_id, module) for module in denied],
        )


def _selected_actions():
    selected = set(request.form.getlist("permissions"))
    available = {
        f"{module}:{action}"
        for module, actions in CONTENT_ADMIN_ACTIONS.items()
        for action in actions
    }
    if not selected <= available:
        abort(400)
    for module, actions in CONTENT_ADMIN_ACTIONS.items():
        if f"{module}:view" not in selected and any(
            f"{module}:{action}" in selected for action in actions if action != "view"
        ):
            abort(400)
    return selected


def _save_action_denials(cursor, user_id, selected):
    available = {
        f"{module}:{action}"
        for module, actions in CONTENT_ADMIN_ACTIONS.items()
        for action in actions
    }
    cursor.execute("DELETE FROM content_admin_denials WHERE user_id = %s", (user_id,))
    denied = available - selected
    if denied:
        cursor.executemany(
            "INSERT INTO content_admin_denials (user_id, module) VALUES (%s, %s)",
            [(user_id, permission) for permission in sorted(denied)],
        )


def _content_admin(cursor, user_id):
    cursor.execute(
        "SELECT user_id, username, full_name, nickname, email, phone, role, status "
        "FROM users WHERE user_id = %s AND role = 'content_admin'",
        (user_id,),
    )
    user = cursor.fetchone()
    if user is None:
        abort(404)
    return user


@content_admin_accounts_bp.route("/system-admin/content-admins/new", methods=["GET", "POST"])
@login_required("system_admin")
def new_account():
    user = {}
    selected = set(CONTENT_ADMIN_MODULES)
    if request.method == "POST":
        _check_csrf()
        user, error = _profile_values(creating=True)
        selected = _selected_modules()
        password = request.form.get("password", "")
        if not error and not _valid_password(password):
            error = "密碼至少 9 碼，且需包含英文與數字。"
        if not error and password != request.form.get("confirm_password", ""):
            error = "兩次密碼不一致。"
        if error:
            flash(error, "error")
        else:
            connection = get_db_connection()
            if connection is None:
                abort(503)
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT user_id FROM users WHERE username = %s OR email = %s LIMIT 1",
                    (user["username"], user["email"]),
                )
                if cursor.fetchone():
                    flash("帳號或電子郵件已被使用。", "error")
                else:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, full_name, nickname, email, phone, role, status) "
                        "VALUES (%s, %s, %s, %s, %s, %s, 'content_admin', 'active')",
                        (user["username"], generate_password_hash(password), user["full_name"],
                         user["nickname"] or None, user["email"], user["phone"] or None),
                    )
                    user_id = cursor.lastrowid
                    _save_denials(cursor, user_id, selected)
                    log_action(cursor, "create_content_admin", "user", user_id,
                               f"新增內容管理員：{user['username']}")
                    connection.commit()
                    flash("內容管理員帳號已建立。", "success")
                    return redirect(url_for("admin_user_detail", user_id=user_id))
            except Error:
                connection.rollback()
                flash("建立失敗，請檢查帳號、電子郵件及資料庫設定。", "error")
            finally:
                cursor.close()
                connection.close()
    return render_template("admin_content_account_form.html", user=user, creating=True,
                           modules=CONTENT_ADMIN_MODULES, selected=selected, csrf=_csrf_token())


@content_admin_accounts_bp.route("/system-admin/content-admins/<int:user_id>/edit", methods=["GET", "POST"])
@login_required("system_admin")
def edit_account(user_id):
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    try:
        user = _content_admin(cursor, user_id)
        if request.method == "POST":
            _check_csrf()
            values, error = _profile_values()
            values["username"] = user["username"]
            if error:
                flash(error, "error")
                user.update(values)
            else:
                cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id != %s LIMIT 1",
                               (values["email"], user_id))
                if cursor.fetchone():
                    flash("電子郵件已被使用。", "error")
                    user.update(values)
                else:
                    cursor.execute(
                        "UPDATE users SET full_name=%s, nickname=%s, email=%s, phone=%s WHERE user_id=%s",
                        (values["full_name"], values["nickname"] or None, values["email"],
                         values["phone"] or None, user_id),
                    )
                    log_action(cursor, "update_content_admin", "user", user_id,
                               f"更新內容管理員資料：{user['username']}")
                    connection.commit()
                    flash("內容管理員資料已更新。", "success")
                    return redirect(url_for("admin_user_detail", user_id=user_id))
    except Error:
        connection.rollback()
        flash("更新資料失敗。", "error")
        return redirect(url_for("admin_user_detail", user_id=user_id))
    finally:
        cursor.close()
        connection.close()
    return render_template("admin_content_account_form.html", user=user, creating=False,
                           csrf=_csrf_token())


@content_admin_accounts_bp.route("/system-admin/content-admins/<int:user_id>/reset-password", methods=["POST"])
@login_required("system_admin")
def reset_password(user_id):
    _check_csrf()
    password = request.form.get("password", "")
    if not _valid_password(password) or password != request.form.get("confirm_password", ""):
        flash("密碼至少 9 碼、包含英文與數字，且兩次輸入需相同。", "error")
        return redirect(url_for("admin_user_detail", user_id=user_id))
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    try:
        user = _content_admin(cursor, user_id)
        cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s",
                       (generate_password_hash(password), user_id))
        log_action(cursor, "reset_content_admin_password", "user", user_id,
                   f"重設內容管理員密碼：{user['username']}")
        connection.commit()
        flash("密碼已重設，請安全地告知該管理員。", "success")
    except Error:
        connection.rollback()
        flash("重設密碼失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_user_detail", user_id=user_id))


@content_admin_accounts_bp.route("/system-admin/content-admins/<int:user_id>/permissions", methods=["GET", "POST"])
@login_required("system_admin")
def update_permissions(user_id):
    if request.method == "POST":
        _check_csrf()
        selected = _selected_actions() if request.form.get("permission_matrix") == "1" else _selected_modules()
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    try:
        user = _content_admin(cursor, user_id)
        if request.method == "GET":
            cursor.execute("SELECT module FROM content_admin_denials WHERE user_id = %s", (user_id,))
            denied = {row["module"] for row in cursor.fetchall()}
            selected = {
                f"{module}:{action}"
                for module, actions in CONTENT_ADMIN_ACTIONS.items()
                for action in actions
                if module not in denied
                and f"{module}:view" not in denied
                and f"{module}:{action}" not in denied
            }
            return render_template(
                "admin_content_permissions.html", user=user, modules=CONTENT_ADMIN_MODULES,
                actions=CONTENT_ADMIN_ACTIONS, action_labels=ACTION_LABELS,
                selected=selected, csrf=_csrf_token(),
            )
        if request.form.get("permission_matrix") == "1":
            _save_action_denials(cursor, user_id, selected)
        else:
            _save_denials(cursor, user_id, selected)
        log_action(cursor, "update_content_admin_permissions", "user", user_id,
                   f"更新內容管理員權限：{user['username']}；允許：{', '.join(sorted(selected)) or '無'}")
        connection.commit()
        flash("管理權限已更新。", "success")
    except Error:
        connection.rollback()
        flash("更新管理權限失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    if request.form.get("permission_matrix") == "1":
        return redirect(url_for("content_admin_accounts.update_permissions", user_id=user_id))
    return redirect(url_for("admin_user_detail", user_id=user_id))


@content_admin_accounts_bp.route("/content-admin/account/password", methods=["GET", "POST"])
@login_required("content_admin")
def change_own_password():
    if request.method == "POST":
        _check_csrf()
        password = request.form.get("password", "")
        if not _valid_password(password) or password != request.form.get("confirm_password", ""):
            flash("新密碼至少 9 碼、包含英文與數字，且兩次輸入需相同。", "error")
            return redirect(url_for("content_admin_accounts.change_own_password"))
        connection = get_db_connection()
        if connection is None:
            abort(503)
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT password_hash FROM users WHERE user_id=%s", (session["user_id"],))
            user = cursor.fetchone()
            if not user or not user["password_hash"] or not check_password_hash(
                user["password_hash"], request.form.get("current_password", "")
            ):
                flash("目前密碼不正確。", "error")
            else:
                cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
                               (generate_password_hash(password), session["user_id"]))
                connection.commit()
                session.clear()
                flash("密碼已更新，請重新登入。", "success")
                return redirect(url_for("login"))
        finally:
            cursor.close()
            connection.close()
    return render_template("content_admin/change_password.html", csrf=_csrf_token())
