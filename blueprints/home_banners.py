"""首頁圖片跑馬燈（輪播圖）：系統管理員後台維護，首頁讀取啟用中的圖片輪播。"""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from activity_log import log_action
from auth import login_required
from db import get_db_connection
from utils import delete_uploaded_image, save_uploaded_image

home_banners_bp = Blueprint("home_banners", __name__, url_prefix="/system-admin/home-banners")

UPLOAD_SUBFOLDER = "banners"  # 圖片存到 static/uploads/banners
MAX_TITLE_LENGTH = 100
MAX_LINK_LENGTH = 500


FOCUS_MISSING_HINT = "請執行 database/migrate_1109_home_banner_focus.sql 才能儲存顯示位置"


def _is_missing_focus_column(error):
    return getattr(error, "errno", None) == 1054 and "focus_" in str(error)


def _with_focus_defaults(rows):
    """還沒加 focus_x / focus_y 欄位的舊資料庫，補上預設置中，樣板不用另外判斷。"""
    for row in rows:
        if row.get("focus_x") is None:
            row["focus_x"] = 50
        if row.get("focus_y") is None:
            row["focus_y"] = 50
    return rows


def _parse_focus(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 50


def fetch_active_banners(cursor):
    """首頁用：回傳啟用中的輪播圖。資料表尚未建立時回傳空清單，不影響首頁其他區塊。"""
    try:
        try:
            cursor.execute("""
                SELECT banner_id, image_path, title, link_url, focus_x, focus_y
                FROM home_banners
                WHERE is_active = 1
                ORDER BY sort_order ASC, banner_id ASC
            """)
        except Exception as error:
            if not _is_missing_focus_column(error):
                raise
            cursor.execute("""
                SELECT banner_id, image_path, title, link_url
                FROM home_banners
                WHERE is_active = 1
                ORDER BY sort_order ASC, banner_id ASC
            """)
        return _with_focus_defaults(cursor.fetchall())
    except Exception as error:
        print("首頁輪播圖查詢失敗（是否尚未執行 migrate_1109_home_banners.sql？）：", error)
        return []


def _clean_link(value):
    """只接受站內路徑（/ 開頭）或 http(s) 網址，避免 javascript: 之類的連結。"""
    link = (value or "").strip()[:MAX_LINK_LENGTH]
    if not link:
        return None
    if link.startswith("/") and not link.startswith("//"):
        return link
    if link.lower().startswith(("http://", "https://")):
        return link
    raise ValueError("連結網址請填 http(s):// 開頭的網址，或 / 開頭的站內路徑")


def _parse_sort_order(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@home_banners_bp.route("/", methods=["GET"])
@login_required("system_admin")
def manage_banners():
    banners = []
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("admin_home_banners.html", banners=[])
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT b.*, u.full_name AS creator_name
            FROM home_banners b
            LEFT JOIN users u ON u.user_id = b.created_by
            ORDER BY b.sort_order ASC, b.banner_id ASC
        """)
        banners = _with_focus_defaults(cursor.fetchall())
    except Exception as error:
        print("讀取首頁輪播圖失敗：", error)
        flash("讀取輪播圖失敗，請確認已執行 database/migrate_1109_home_banners.sql", "error")
    finally:
        cursor.close()
        connection.close()
    return render_template("admin_home_banners.html", banners=banners)


@home_banners_bp.route("/create", methods=["POST"])
@login_required("system_admin")
def create_banner():
    """新增輪播圖，可一次選多張：每張圖片各自建立一筆，排序從填寫的數字開始往後遞增。

    後台頁面批量上傳時會逐張送出並帶 ajax=1，這時回傳 JSON 讓前端顯示每張的結果；
    沒有 JavaScript 時則一次送出全部檔案，結果用 flash 訊息顯示。
    """
    ajax = request.form.get("ajax") == "1"

    def respond(created, failed):
        if ajax:
            return jsonify(created=created, failed=failed)
        if created:
            flash(f"已新增 {created} 張輪播圖", "success")
        if failed:
            flash("以下圖片未上傳：" + "、".join(failed), "error")
        return redirect(url_for("home_banners.manage_banners"))

    files = [f for f in request.files.getlist("image") if f and f.filename]
    try:
        link_url = _clean_link(request.form.get("link_url"))
    except ValueError as error:
        return respond(0, [str(error)])
    if not files:
        return respond(0, ["請選擇要上傳的圖片"])

    title = (request.form.get("title") or "").strip()[:MAX_TITLE_LENGTH] or None
    sort_order = _parse_sort_order(request.form.get("sort_order"))
    is_active = 1 if request.form.get("is_active") else 0

    connection = get_db_connection()
    if connection is None:
        return respond(0, ["資料庫連線失敗"])
    cursor = connection.cursor()
    created, failed = 0, []
    try:
        for file_storage in files:
            image_path = None
            try:
                image_path = save_uploaded_image(file_storage, UPLOAD_SUBFOLDER)
                cursor.execute("""
                    INSERT INTO home_banners (image_path, title, link_url, sort_order, is_active, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (image_path, title, link_url, sort_order, is_active, session.get("user_id")))
                banner_id = cursor.lastrowid
                log_action(cursor, "create_home_banner", "home_banner", banner_id,
                           f"新增首頁輪播圖：{title or file_storage.filename}")
                connection.commit()
                created += 1
                sort_order += 1
            except ValueError as error:
                failed.append(f"{file_storage.filename}（{error}）")
            except Exception as error:
                connection.rollback()
                delete_uploaded_image(image_path)
                print("新增首頁輪播圖失敗：", error)
                failed.append(f"{file_storage.filename}（儲存失敗）")
    finally:
        cursor.close()
        connection.close()
    return respond(created, failed)


@home_banners_bp.route("/<int:banner_id>/update", methods=["POST"])
@login_required("system_admin")
def update_banner(banner_id):
    try:
        link_url = _clean_link(request.form.get("link_url"))
        new_image_path = save_uploaded_image(request.files.get("image"), UPLOAD_SUBFOLDER)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("home_banners.manage_banners"))

    title = (request.form.get("title") or "").strip()[:MAX_TITLE_LENGTH] or None
    sort_order = _parse_sort_order(request.form.get("sort_order"))
    is_active = 1 if request.form.get("is_active") else 0
    focus_x = _parse_focus(request.form.get("focus_x"))
    focus_y = _parse_focus(request.form.get("focus_y"))

    connection = get_db_connection()
    if connection is None:
        delete_uploaded_image(new_image_path)
        flash("資料庫連線失敗", "error")
        return redirect(url_for("home_banners.manage_banners"))
    cursor = connection.cursor(dictionary=True)
    old_image_path = None
    try:
        cursor.execute("SELECT image_path FROM home_banners WHERE banner_id = %s", (banner_id,))
        row = cursor.fetchone()
        if row is None:
            delete_uploaded_image(new_image_path)
            flash("找不到這張輪播圖", "error")
            return redirect(url_for("home_banners.manage_banners"))
        image_path = new_image_path or row["image_path"]
        focus_saved = True
        try:
            cursor.execute("""
                UPDATE home_banners
                SET image_path = %s, title = %s, link_url = %s, sort_order = %s, is_active = %s,
                    focus_x = %s, focus_y = %s
                WHERE banner_id = %s
            """, (image_path, title, link_url, sort_order, is_active, focus_x, focus_y, banner_id))
        except Exception as error:
            if not _is_missing_focus_column(error):
                raise
            focus_saved = False
            cursor.execute("""
                UPDATE home_banners
                SET image_path = %s, title = %s, link_url = %s, sort_order = %s, is_active = %s
                WHERE banner_id = %s
            """, (image_path, title, link_url, sort_order, is_active, banner_id))
        log_action(cursor, "update_home_banner", "home_banner", banner_id,
                   f"更新首頁輪播圖：{title or image_path}" + ("（更換圖片）" if new_image_path else ""))
        connection.commit()
        if new_image_path:
            old_image_path = row["image_path"]
        flash("輪播圖已更新", "success")
        if not focus_saved:
            flash(FOCUS_MISSING_HINT, "error")
    except Exception as error:
        connection.rollback()
        delete_uploaded_image(new_image_path)
        print("更新首頁輪播圖失敗：", error)
        flash("更新輪播圖失敗", "error")
    finally:
        cursor.close()
        connection.close()
    if old_image_path:
        delete_uploaded_image(old_image_path)
    return redirect(url_for("home_banners.manage_banners"))


@home_banners_bp.route("/<int:banner_id>/delete", methods=["POST"])
@login_required("system_admin")
def delete_banner(banner_id):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("home_banners.manage_banners"))
    cursor = connection.cursor(dictionary=True)
    image_path = None
    try:
        cursor.execute("SELECT image_path, title FROM home_banners WHERE banner_id = %s", (banner_id,))
        row = cursor.fetchone()
        if row is None:
            flash("找不到這張輪播圖", "error")
            return redirect(url_for("home_banners.manage_banners"))
        cursor.execute("DELETE FROM home_banners WHERE banner_id = %s", (banner_id,))
        log_action(cursor, "delete_home_banner", "home_banner", banner_id,
                   f"刪除首頁輪播圖：{row['title'] or row['image_path']}")
        connection.commit()
        image_path = row["image_path"]
        flash("輪播圖已刪除", "success")
    except Exception as error:
        connection.rollback()
        print("刪除首頁輪播圖失敗：", error)
        flash("刪除輪播圖失敗", "error")
    finally:
        cursor.close()
        connection.close()
    if image_path:
        delete_uploaded_image(image_path)
    return redirect(url_for("home_banners.manage_banners"))


@home_banners_bp.route("/bulk-delete", methods=["POST"])
@login_required("system_admin")
def bulk_delete_banners():
    """批量刪除：勾選多張輪播圖一次刪除，圖片檔也一併刪掉。"""
    banner_ids = sorted({int(v) for v in request.form.getlist("banner_ids") if str(v).isdigit()})
    if not banner_ids:
        flash("請先勾選要刪除的輪播圖", "error")
        return redirect(url_for("home_banners.manage_banners"))

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("home_banners.manage_banners"))
    cursor = connection.cursor(dictionary=True)
    image_paths = []
    try:
        placeholders = ",".join(["%s"] * len(banner_ids))
        cursor.execute(f"SELECT banner_id, image_path, title FROM home_banners WHERE banner_id IN ({placeholders})",
                       tuple(banner_ids))
        rows = cursor.fetchall()
        if not rows:
            flash("找不到勾選的輪播圖，可能已經被刪除", "error")
            return redirect(url_for("home_banners.manage_banners"))
        found_ids = [row["banner_id"] for row in rows]
        placeholders = ",".join(["%s"] * len(found_ids))
        cursor.execute(f"DELETE FROM home_banners WHERE banner_id IN ({placeholders})", tuple(found_ids))
        for row in rows:
            log_action(cursor, "delete_home_banner", "home_banner", row["banner_id"],
                       f"批量刪除首頁輪播圖：{row['title'] or row['image_path']}")
        connection.commit()
        image_paths = [row["image_path"] for row in rows]
        flash(f"已刪除 {len(rows)} 張輪播圖", "success")
    except Exception as error:
        connection.rollback()
        print("批量刪除首頁輪播圖失敗：", error)
        flash("批量刪除失敗", "error")
    finally:
        cursor.close()
        connection.close()
    for path in image_paths:  # 資料庫確定刪除後才刪圖片檔
        delete_uploaded_image(path)
    return redirect(url_for("home_banners.manage_banners"))
