from flask import Blueprint, flash, redirect, render_template, request, session, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式
from utils import delete_uploaded_image  # 匯入刪除已上傳圖片的共用函式

attraction_posts_admin_bp = Blueprint("attraction_posts_admin", __name__, url_prefix="/content-admin/attraction-posts")  # 建立景點相簿審核藍圖，網址前綴 /content-admin/attraction-posts

PAGE_SIZE = 20  # 定義列表頁每頁顯示筆數

STATUS_LABELS = {  # 定義審核狀態對應的中文顯示名稱
    "pending": "待審核",
    "approved": "已核准",
    "rejected": "已退回",
}


@attraction_posts_admin_bp.route("/")  # 設定景點相簿貼文列表頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def list_posts():  # 定義列表頁函式
    status = request.args.get("status", "pending").strip()  # 取得網址上的狀態篩選參數，預設待審核
    page = request.args.get("page", "1")  # 取得頁碼參數(字串)
    page = int(page) if page.isdigit() and int(page) > 0 else 1  # 驗證頁碼為正整數，否則預設第 1 頁

    if status not in STATUS_LABELS and status != "all":  # 如果狀態不合法也不是「全部」
        status = "pending"  # 強制改回預設值

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "content_admin/attraction_posts/list.html",
            posts=[], status=status, status_labels=STATUS_LABELS,
            page=1, total_pages=1, total=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        params = []  # 建立 SQL 參數清單
        where_clause = ""  # 預設沒有篩選條件(顯示全部)

        if status != "all":  # 如果不是要看全部
            where_clause = "WHERE p.review_status = %s"  # 加上依審核狀態篩選的條件
            params.append(status)  # 加入對應參數

        cursor.execute(f"SELECT COUNT(*) AS total FROM attraction_posts p {where_clause}", params)  # 查詢符合條件的貼文總筆數(用來算分頁)
        total = cursor.fetchone()["total"]  # 取出總筆數

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)  # 計算總頁數(無條件進位，至少 1 頁)
        page = min(page, total_pages)  # 如果頁碼超過總頁數，修正為最後一頁
        offset = (page - 1) * PAGE_SIZE  # 計算 SQL 要跳過的筆數

        cursor.execute(  # 查詢當頁的貼文清單，並關聯所屬景點名稱與貼文者姓名
            f"""
            SELECT p.post_id, p.caption, p.review_status, p.review_note, p.created_at,
                   a.attraction_id, a.name AS attraction_name,
                   u.full_name AS poster_name, u.nickname AS poster_nickname
            FROM attraction_posts p
            JOIN attractions a ON a.attraction_id = p.attraction_id
            JOIN users u ON u.user_id = p.user_id
            {where_clause}
            ORDER BY p.created_at ASC
            LIMIT %s OFFSET %s
            """,
            params + [PAGE_SIZE, offset]  # 加上分頁用的 LIMIT、OFFSET 參數
        )
        posts = cursor.fetchall()  # 取出當頁貼文清單

        if posts:  # 如果這頁有貼文，一次把這些貼文的照片都查出來，避免一筆一筆查造成 N+1
            post_ids = [p["post_id"] for p in posts]  # 取出這頁所有貼文 ID
            placeholders = ",".join(["%s"] * len(post_ids))  # 組成對應數量的佔位符
            cursor.execute(  # 查詢這些貼文底下的所有照片
                f"""
                SELECT post_id, image_path
                FROM attraction_post_images
                WHERE post_id IN ({placeholders})
                ORDER BY post_id, sort_order, image_id
                """,
                tuple(post_ids)
            )
            images_by_post = {}  # 建立「貼文 ID -> 照片路徑清單」的對照表
            for row in cursor.fetchall():  # 逐筆分類到對應的貼文底下
                images_by_post.setdefault(row["post_id"], []).append(row["image_path"])
            for post in posts:  # 把照片清單掛回每一筆貼文資料上
                post["images"] = images_by_post.get(post["post_id"], [])

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染列表頁面
        "content_admin/attraction_posts/list.html",
        posts=posts,  # 當頁貼文清單
        status=status,  # 目前篩選的狀態
        status_labels=STATUS_LABELS,  # 狀態對應的中文名稱
        page=page,  # 目前頁碼
        total_pages=total_pages,  # 總頁數
        total=total,  # 符合條件的總筆數
    )


@attraction_posts_admin_bp.route("/<int:post_id>/approve", methods=["POST"])  # 設定核准貼文的路由，網址帶入貼文 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def approve_post(post_id):  # 定義核准貼文函式
    back_status = request.form.get("status", "pending")  # 取得送出審核時所在的篩選狀態，處理完導回同一個篩選頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))  # 導回列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 嘗試更新資料
        cursor.execute("SELECT user_id, attraction_id FROM attraction_posts WHERE post_id=%s", (post_id,))  # 先查出貼文者跟所屬景點，等一下要送通知、組連結用
        post = cursor.fetchone()
        if not post:  # 如果貼文已經不存在(例如同時被別的管理員處理掉)
            flash("找不到這則貼文。", "error")
            return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))

        cursor.execute(  # 執行核准貼文的 SQL：更新審核狀態、審核者、審核時間，並清空之前的退回原因
            """
            UPDATE attraction_posts
            SET review_status = 'approved', reviewed_by = %s, reviewed_at = NOW(), review_note = NULL
            WHERE post_id = %s
            """,
            (session["user_id"], post_id)
        )
        cursor.execute(  # 通知貼文者：你的照片審核通過了
            """
            INSERT INTO notifications (user_id, notification_type, title, message, target_url)
            VALUES (%s, 'system', '景點相簿貼文已核准', '你分享的照片已經通過審核，現在大家都看得到了。', %s)
            """,
            (post["user_id"], url_for("member.attraction_detail", attraction_id=post["attraction_id"]) + "#album")
        )
        log_action(cursor, "approve_attraction_post", "attraction_post", post_id, "核准景點相簿貼文")  # 寫入操作紀錄
        connection.commit()  # 提交交易(審核狀態、通知與操作紀錄一起寫入)
        flash("貼文已核准，會顯示在景點相簿中。", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("核准景點相簿貼文失敗：", error)  # 在伺服器端印出錯誤內容
        flash("核准失敗，請再試一次。", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))  # 導回列表頁


@attraction_posts_admin_bp.route("/<int:post_id>/reject", methods=["POST"])  # 設定退回貼文的路由，網址帶入貼文 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def reject_post(post_id):  # 定義退回貼文函式
    back_status = request.form.get("status", "pending")  # 取得送出審核時所在的篩選狀態，處理完導回同一個篩選頁
    review_note = request.form.get("review_note", "").strip()  # 取得表單輸入的退回原因

    if not review_note:  # 如果沒有填寫退回原因
        flash("退回時請填寫原因，讓貼文者知道問題在哪。", "error")  # 顯示錯誤提示
        return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))  # 導回列表頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))  # 導回列表頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 嘗試更新資料
        cursor.execute("SELECT user_id, attraction_id FROM attraction_posts WHERE post_id=%s", (post_id,))  # 先查出貼文者跟所屬景點，等一下要送通知、組連結用
        post = cursor.fetchone()
        if not post:  # 如果貼文已經不存在(例如同時被別的管理員處理掉)
            flash("找不到這則貼文。", "error")
            return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))

        cursor.execute("SELECT image_path FROM attraction_post_images WHERE post_id=%s", (post_id,))  # 先查出這篇貼文底下所有照片的路徑，等一下要連同檔案一起刪除
        image_paths = [row["image_path"] for row in cursor.fetchall()]  # 整理成路徑清單

        cursor.execute(  # 執行退回貼文的 SQL：更新審核狀態、審核者、審核時間、退回原因
            """
            UPDATE attraction_posts
            SET review_status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), review_note = %s
            WHERE post_id = %s
            """,
            (session["user_id"], review_note, post_id)
        )

        if image_paths:  # 如果這篇貼文有照片
            cursor.execute("DELETE FROM attraction_post_images WHERE post_id=%s", (post_id,))  # 把照片紀錄從資料庫移除(貼文本身保留，讓貼文者看得到退回原因)

        cursor.execute(  # 通知貼文者：你的照片被退回了，附上原因
            """
            INSERT INTO notifications (user_id, notification_type, title, message, target_url)
            VALUES (%s, 'system', '景點相簿貼文被退回', %s, %s)
            """,
            (post["user_id"], f"你分享的照片沒有通過審核，原因：{review_note}",
             url_for("member.attraction_detail", attraction_id=post["attraction_id"]) + "#album")
        )

        log_action(cursor, "reject_attraction_post", "attraction_post", post_id, f"退回景點相簿貼文，原因：{review_note}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(審核狀態、照片刪除、通知與操作紀錄一起寫入)
        for path in image_paths:  # 資料庫確定寫入成功後，才真的把照片檔案從硬碟刪除
            delete_uploaded_image(path)
        flash("貼文已退回，照片已從伺服器移除。", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外
        connection.rollback()  # 回復交易
        print("退回景點相簿貼文失敗：", error)  # 在伺服器端印出錯誤內容
        flash("退回失敗，請再試一次。", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("attraction_posts_admin.list_posts", status=back_status))  # 導回列表頁
