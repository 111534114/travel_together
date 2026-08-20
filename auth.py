from functools import wraps  # 匯入 wraps，用來保留被裝飾函式原本的名稱與說明文件

from flask import redirect, session, url_for  # 匯入 Flask 的導向、session、產生網址功能


def login_required(role=None):  # 定義裝飾器工廠函式：可指定必須符合的角色(role)，不指定則只檢查是否登入
    def decorator(view):  # 定義實際的裝飾器，接收要保護的路由函式(view)
        @wraps(view)  # 保留原本 view 函式的名稱等資訊，避免 Flask 路由註冊時混淆
        def wrapped(*args, **kwargs):  # 定義包裝後的函式，取代原本的 view
            if "user_id" not in session:  # 如果 session 裡沒有登入者 ID
                return redirect(url_for("login"))  # 導向登入頁

            if role and session.get("role") != role:  # 如果有指定角色，且登入者角色不符合
                return redirect(url_for("login"))  # 導向登入頁

            return view(*args, **kwargs)  # 通過檢查，執行原本的路由函式並回傳結果

        return wrapped  # 回傳包裝後的函式，取代原本的 view

    return decorator  # 回傳裝飾器本身，供 @login_required(...) 使用
