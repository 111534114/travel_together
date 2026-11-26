from functools import wraps  # 匯入 wraps，用來保留被裝飾函式原本的名稱與說明文件

from flask import flash, redirect, request, session, url_for  # 匯入 Flask 的導向、session、產生網址功能

from content_admin_permissions import require_content_admin_module


def remember_next_page():
    """沒登入就被擋下來時，記住原本要去的頁面，登入後帶回去(app.redirect_by_role)。
    只記一般瀏覽的頁面(GET、要看網頁的請求)；背景 API、表單送出不記，避免登入後跳到一串資料或重送表單。"""
    if request.method != "GET" or "text/html" not in request.headers.get("Accept", ""):
        return
    path = request.full_path if request.query_string else request.path
    if path.startswith("/") and not path.startswith("//"):
        session["pending_next"] = path[:500]
        flash("請先登入，登入後會帶你回到剛剛的頁面。", "success")


def login_required(role=None):  # 定義裝飾器工廠函式：可指定必須符合的角色(role)，不指定則只檢查是否登入
    def decorator(view):  # 定義實際的裝飾器，接收要保護的路由函式(view)
        @wraps(view)  # 保留原本 view 函式的名稱等資訊，避免 Flask 路由註冊時混淆
        def wrapped(*args, **kwargs):  # 定義包裝後的函式，取代原本的 view
            if "user_id" not in session:  # 如果 session 裡沒有登入者 ID
                remember_next_page()  # 記住原本要去的頁面，登入後帶回來
                return redirect(url_for("login"))  # 導向登入頁

            if role and session.get("role") != role:  # 如果有指定角色，且登入者角色不符合
                return redirect(url_for("login"))  # 導向登入頁

            if role == "content_admin":
                require_content_admin_module()

            return view(*args, **kwargs)  # 通過檢查，執行原本的路由函式並回傳結果

        return wrapped  # 回傳包裝後的函式，取代原本的 view

    return decorator  # 回傳裝飾器本身，供 @login_required(...) 使用
